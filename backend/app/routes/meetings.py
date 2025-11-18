from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models import Meeting, User

meetings_bp = Blueprint("meetings", __name__)


@meetings_bp.get("")
@jwt_required()
def list_meetings():
    user_id = get_jwt_identity()
    meetings = (
        Meeting.query.filter_by(owner_id=user_id)
        .order_by(Meeting.start_time.asc())
        .all()
    )
    return jsonify({"meetings": [m.to_dict() for m in meetings]})


@meetings_bp.post("")
@jwt_required()
def create_meeting():
    payload = request.get_json() or {}
    user_id = get_jwt_identity()

    title = (payload.get("title") or "").strip()
    start_time = payload.get("start_time")
    duration = int(payload.get("duration", 30))
    description = payload.get("description")

    if not title or not start_time:
        return jsonify({"message": "Title and start_time are required"}), 400

    try:
        start_dt = datetime.fromisoformat(start_time)
    except ValueError:
        return jsonify({"message": "start_time must be ISO8601"}), 400

    meeting = Meeting(
        title=title,
        description=description,
        start_time=start_dt,
        duration_minutes=duration,
        owner_id=user_id,
    )

    db.session.add(meeting)
    db.session.commit()

    return jsonify({"meeting": meeting.to_dict()}), 201


@meetings_bp.put("/<meeting_id>")
@jwt_required()
def update_meeting(meeting_id: str):
    payload = request.get_json() or {}
    user_id = get_jwt_identity()

    meeting = Meeting.query.filter_by(id=meeting_id, owner_id=user_id).first_or_404()

    if "title" in payload:
        meeting.title = payload["title"].strip() or meeting.title
    if "description" in payload:
        meeting.description = payload["description"]
    if "duration" in payload:
        meeting.duration_minutes = int(payload["duration"])
    if "start_time" in payload:
        try:
            meeting.start_time = datetime.fromisoformat(payload["start_time"])
        except ValueError:
            return jsonify({"message": "start_time must be ISO8601"}), 400

    db.session.commit()

    return jsonify({"meeting": meeting.to_dict()})


@meetings_bp.delete("/<meeting_id>")
@jwt_required()
def delete_meeting(meeting_id: str):
    user_id = get_jwt_identity()
    meeting = Meeting.query.filter_by(id=meeting_id, owner_id=user_id).first_or_404()

    db.session.delete(meeting)
    db.session.commit()

    return jsonify({"deleted": meeting_id})
