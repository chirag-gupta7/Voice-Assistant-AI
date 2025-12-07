from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from dateutil import parser
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..extensions import db
from ..models import Meeting
from ..services import google_calendar

calendar_bp = Blueprint("calendar", __name__)


def _meeting_to_event(meeting: Meeting) -> Dict[str, Any]:
    return {
        "id": meeting.id,
        "title": meeting.title,
        "description": meeting.description,
        "start": meeting.start_time.isoformat() if meeting.start_time else None,
        "end": (
            (meeting.start_time + timedelta(minutes=meeting.duration_minutes)).isoformat()
            if meeting.start_time and meeting.duration_minutes
            else None
        ),
        "duration_minutes": meeting.duration_minutes,
        "source": "local",
    }


def _google_event_to_dict(event: Dict[str, Any]) -> Dict[str, Any]:
    start = event.get("start", {})
    end = event.get("end", {})
    start_time = start.get("dateTime") or start.get("date")
    end_time = end.get("dateTime") or end.get("date")

    return {
        "id": event.get("id"),
        "title": event.get("summary"),
        "description": event.get("description"),
        "start": start_time,
        "end": end_time,
        "location": event.get("location"),
        "source": "google",
    }


def _get_google_access_token() -> str:
    return (
        request.headers.get("X-Google-Access-Token")
        or request.args.get("google_access_token")
        or (request.get_json(silent=True) or {}).get("google_access_token")
        or ""
    )


@calendar_bp.get("/events")
@jwt_required()
def list_events():
    user_id = get_jwt_identity()
    google_token = _get_google_access_token()

    if google_token:
        google_events = google_calendar.list_upcoming_events(google_token)
        if google_events:
            return jsonify(
                {
                    "source": "google",
                    "events": [_google_event_to_dict(e) for e in google_events],
                }
            )

    # Fallback to local events
    window_start = datetime.now(timezone.utc) - timedelta(days=7)
    meetings = (
        Meeting.query.filter_by(owner_id=user_id)
        .filter(Meeting.start_time >= window_start)
        .order_by(Meeting.start_time.asc())
        .all()
    )

    return jsonify({"source": "local", "events": [_meeting_to_event(m) for m in meetings]})


@calendar_bp.post("/sync")
@jwt_required()
def sync_calendar():
    user_id = get_jwt_identity()
    payload = request.get_json() or {}
    google_token = _get_google_access_token()

    title = payload.get("title")
    description = payload.get("description")
    start_raw = payload.get("start")
    duration_minutes = payload.get("duration_minutes") or 60

    if not title or not start_raw:
        return jsonify({"success": False, "message": "title and start are required"}), 400

    try:
        start_time = parser.parse(start_raw)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid start timestamp"}), 400

    end_time = start_time + timedelta(minutes=int(duration_minutes))

    meeting = Meeting(
        title=title,
        description=description,
        start_time=start_time,
        duration_minutes=duration_minutes,
        owner_id=user_id,
    )
    db.session.add(meeting)
    db.session.commit()

    google_event = None
    if google_token:
        google_event_payload: Dict[str, Any] = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_time.isoformat()},
            "end": {"dateTime": end_time.isoformat()},
        }
        google_event = google_calendar.create_event(google_token, google_event_payload)

    response: Dict[str, Any] = {
        "success": True,
        "event": _meeting_to_event(meeting),
        "source": "google" if google_event else "local",
    }

    if google_event:
        response["google_event"] = _google_event_to_dict(google_event)

    return jsonify(response)
