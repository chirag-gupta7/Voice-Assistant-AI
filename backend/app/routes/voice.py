from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from ..services.elevenlabs_service import synthesize_speech
from ..services.llm_service import generate_action_reply

voice_bp = Blueprint("voice", __name__)


@voice_bp.post("/process")
@jwt_required()
def process_voice():
    payload = request.get_json() or {}
    transcript = payload.get("transcript") or payload.get("text")
    include_audio = bool(payload.get("include_audio", True))

    if not transcript:
        return jsonify({"success": False, "message": "Transcript is required"}), 400

    action, reply = generate_action_reply(transcript)
    audio_base64 = synthesize_speech(reply) if include_audio else None

    return jsonify(
        {
            "success": True,
            "action": action,
            "message": reply,
            "audio_base64": audio_base64,
        }
    )
