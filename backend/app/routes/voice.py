from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..services.elevenlabs_service import synthesize_speech
from ..services.llm_service import generate_action_reply
from ..services.command_processor import VoiceCommandProcessor

voice_bp = Blueprint("voice", __name__)


@voice_bp.post("/process")
@jwt_required()
def process_voice():
    payload = request.get_json() or {}
    transcript = payload.get("transcript") or payload.get("text")
    include_audio = bool(payload.get("include_audio", True))

    if not transcript:
        return jsonify({"success": False, "message": "Transcript is required"}), 400

    user_id = get_jwt_identity()
    processor = VoiceCommandProcessor(user_id=user_id)

    action, reply = generate_action_reply(transcript)
    command_result = None

    # Delegate to richer processor when intent is clear
    if action == "schedule_meeting":
        command_result = processor.create_calendar_event(transcript)
    elif "weather" in transcript.lower():
        command_result = processor.get_weather(location="current location")

    if command_result:
        reply = command_result.get("user_message", reply)

    audio_base64 = None
    audio_error = None

    if include_audio:
        audio_base64 = synthesize_speech(reply)
        if audio_base64 is None:
            audio_error = "tts_unavailable"

    return jsonify(
        {
            "success": True,
            "action": action,
            "message": reply,
            "command_result": command_result,
            "audio_base64": audio_base64,
            "audio_error": audio_error,
        }
    )
