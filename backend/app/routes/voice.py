import os
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from google_auth_oauthlib.flow import InstalledAppFlow

from ..services.elevenlabs_service import synthesize_speech
from ..services.llm_service import generate_action_reply
from ..services.command_processor import VoiceCommandProcessor
from ..services.google_calendar import get_auth_url

voice_bp = Blueprint("voice", __name__)


@voice_bp.get("/greeting")
@jwt_required()
def get_greeting():
    """Returns the audio for the initial greeting."""
    greeting_text = "Hello! I can help you schedule meetings or check your calendar. What would you like to do?"
    
    # Generate audio
    audio_base64 = synthesize_speech(greeting_text)
    
    if audio_base64 is None:
        return jsonify({"success": False, "message": "TTS unavailable"}), 500

    return jsonify({
        "success": True, 
        "message": greeting_text,
        "audio_base64": audio_base64
    })


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
    auth_url = None
    action_type = action

    # Delegate to richer processor when intent is clear
    if action == "schedule_meeting":
        command_result = processor.create_calendar_event(transcript)

        # If scheduling failed due to missing creds/connection, surface auth URL
        if command_result and not command_result.get("success"):
            err = (command_result.get("error") or "").lower()
            if "connect" in err or "cred" in err:
                auth_url = get_auth_url()
                reply = "I need permission to access your Google Calendar. Please click the button below to connect."
                action_type = "auth_required"
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
            "action": action_type,
            "message": reply,
            "command_result": command_result,
            "audio_base64": audio_base64,
            "audio_error": audio_error,
            "auth_url": auth_url,
        }
    )


@voice_bp.post("/google_callback")
@jwt_required()
def google_callback():
    payload = request.get_json() or {}
    code = payload.get("code")

    if not code:
        return jsonify({"success": False, "message": "No code provided"}), 400

    try:
        creds_file = os.path.join(os.getcwd(), "credentials.json")
        flow = InstalledAppFlow.from_client_secrets_file(
            creds_file,
            scopes=["https://www.googleapis.com/auth/calendar.events"],
            redirect_uri=os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:3000/oauth2callback"),
        )

        flow.fetch_token(code=code)
        creds = flow.credentials

        # Persist tokens for reuse
        token_path = os.path.join(os.getcwd(), "token.pickle")
        token_json_path = os.path.join(os.getcwd(), "token.json")
        try:
            with open(token_path, "wb") as token_file:
                import pickle

                pickle.dump(creds, token_file)
            with open(token_json_path, "w") as token_json_file:
                token_json_file.write(creds.to_json())
        except Exception:
            pass

        return jsonify({"success": True, "message": "Calendar connected"})

    except Exception as exc:  # pragma: no cover
        return jsonify({"success": False, "message": str(exc)}), 500
