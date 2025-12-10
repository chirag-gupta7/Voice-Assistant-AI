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
    metadata = meeting.extra_data or {}
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
        "location": metadata.get("location"),
        "notifications": metadata.get("notifications"),
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


def _build_form_sections(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a structured representation of the scheduling fields for UI/UX."""
    return {
        "sections": [
            {
                "id": "title",
                "label": "Title",
                "fields": [{"name": "title", "value": payload.get("title", ""), "required": True}],
            },
            {
                "id": "time",
                "label": "Time",
                "fields": [
                    {"name": "start", "value": payload.get("start"), "required": True},
                    {"name": "end", "value": payload.get("end")},
                    {
                        "name": "duration_minutes",
                        "value": payload.get("duration_minutes"),
                        "helper": "Used if end is not provided",
                    },
                    {"name": "time_zone", "value": payload.get("time_zone", "UTC")},
                ],
            },
            {
                "id": "details",
                "label": "Details",
                "fields": [
                    {"name": "description", "value": payload.get("description")},
                    {"name": "location", "value": payload.get("location")},
                ],
            },
            {
                "id": "notifications",
                "label": "Notifications",
                "fields": [
                    {
                        "name": "notifications",
                        "value": payload.get("notifications") or payload.get("reminders"),
                        "helper": "List of minutes before start, e.g. [30, 10]",
                    }
                ],
            },
        ]
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


@calendar_bp.get("/events/form")
@jwt_required()
def event_form_definition():
    """Expose field sections so the UI can render a structured meeting composer."""
    empty_payload: Dict[str, Any] = {
        "title": "",
        "description": "",
        "start": None,
        "end": None,
        "duration_minutes": 60,
        "location": "",
        "notifications": [30, 10],
        "time_zone": "UTC",
    }
    return jsonify({"sections": _build_form_sections(empty_payload)["sections"]})


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


@calendar_bp.post("/events")
@jwt_required()
def create_structured_event():
    """
    Create a meeting from structured (typed) input with support for notifications and location.
    Persists locally and mirrors to Google Calendar when an access token is provided.
    """
    user_id = get_jwt_identity()
    payload = request.get_json() or {}
    google_token = _get_google_access_token()

    title = (payload.get("title") or "").strip()
    description = payload.get("description")
    start_raw = payload.get("start")
    end_raw = payload.get("end")
    duration_minutes = int(payload.get("duration_minutes") or 60)
    location = payload.get("location")
    notifications = payload.get("notifications") or payload.get("reminders") or []
    time_zone = payload.get("time_zone") or "UTC"
    raw_text = payload.get("raw_text")  # Optional companion text command

    if not title or not start_raw:
        return jsonify({"success": False, "message": "title and start are required"}), 400

    try:
        start_time = parser.parse(start_raw)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid start timestamp"}), 400

    try:
        end_time = parser.parse(end_raw) if end_raw else start_time + timedelta(minutes=duration_minutes)
    except (ValueError, TypeError):
        return jsonify({"success": False, "message": "Invalid end timestamp"}), 400

    extra_data = {
        "location": location,
        "notifications": notifications,
        "time_zone": time_zone,
        "raw_text": raw_text,
        "entry_mode": "typed",
    }

    meeting = Meeting(
        title=title,
        description=description,
        start_time=start_time,
        duration_minutes=int((end_time - start_time).total_seconds() // 60),
        owner_id=user_id,
        extra_data=extra_data,
    )
    db.session.add(meeting)
    db.session.commit()

    google_event = None
    if google_token:
        reminder_overrides = []
        for minutes_before in notifications:
            try:
                minutes_val = int(minutes_before)
            except (TypeError, ValueError):
                continue
            reminder_overrides.append({"method": "popup", "minutes": minutes_val})

        google_event_payload: Dict[str, Any] = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_time.isoformat(), "timeZone": time_zone},
            "end": {"dateTime": end_time.isoformat(), "timeZone": time_zone},
        }

        if location:
            google_event_payload["location"] = location

        if reminder_overrides:
            google_event_payload["reminders"] = {"useDefault": False, "overrides": reminder_overrides}

        google_event = google_calendar.create_event(google_token, google_event_payload)

    response: Dict[str, Any] = {
        "success": True,
        "event": _meeting_to_event(meeting),
        "sections": _build_form_sections(payload)["sections"],
        "source": "google" if google_event else "local",
    }

    if google_event:
        response["google_event"] = _google_event_to_dict(google_event)

    return jsonify(response), 201
