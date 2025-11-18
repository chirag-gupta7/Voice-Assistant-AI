from datetime import datetime, timedelta

from flask import Blueprint, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..models import Meeting

calendar_bp = Blueprint("calendar", __name__)


@calendar_bp.get("/events")
@jwt_required()
def list_events():
    user_id = get_jwt_identity()
    meetings = (
        Meeting.query.filter_by(owner_id=user_id)
        .filter(Meeting.start_time >= datetime.utcnow() - timedelta(days=7))
        .order_by(Meeting.start_time.asc())
        .all()
    )

    return jsonify({"events": [m.to_dict() for m in meetings]})


@calendar_bp.post("/sync")
@jwt_required()
def sync_calendar():
    # Placeholder for Google Calendar integration
    return jsonify({"success": True, "message": "Calendar sync request queued"})
