from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models import Meeting
from ..services.voice import parse_voice_command

voice_bp = Blueprint("voice", __name__)


@voice_bp.post("/process")
@jwt_required()
def process_voice():
    payload = request.get_json() or {}
    transcript = payload.get("transcript") or payload.get("text")

    if not transcript:
        return jsonify({"success": False, "message": "Transcript is required"}), 400

    command = parse_voice_command(transcript)
    if not command:
        return jsonify({"success": False, "message": "Unable to parse transcript"}), 400

    meeting = Meeting(
        title=command.title,
        description=command.notes,
        start_time=command.start_time,
        duration_minutes=command.duration,
        owner_id=get_jwt_identity(),
    )

    db.session.add(meeting)
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "meeting": meeting.to_dict(),
            "message": "Meeting scheduled",
        }
    )
