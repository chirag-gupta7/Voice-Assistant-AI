import os
import pickle
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dateutil import parser
from .calendar_event_parser import create_event_manual_parse as manual_event_parser
logger = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/calendar"]
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOKEN_PATH = os.path.join(BASE_DIR, "token.pickle")
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
_cached_calendar_service = None


def _load_creds() -> Credentials:
    """Load and refresh credentials if possible; returns None when user action is required."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            with open(TOKEN_PATH, "rb") as token:
                creds = pickle.load(token)
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to load token.pickle: %s", exc)
            creds = None

    # Refresh if expired and refresh token exists
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_PATH, "wb") as token:
                pickle.dump(creds, token)
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to refresh Google creds: %s", exc)
            creds = None
            if os.path.exists(TOKEN_PATH):
                os.remove(TOKEN_PATH)

    return creds if creds and creds.valid else None


def get_auth_url(redirect_uri: str = None) -> Dict[str, Any]:
    """Generate an OAuth URL for the frontend to open when auth is required."""
    creds = _load_creds()
    if creds:
        return {"status": "authenticated", "creds": creds}

    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError("credentials.json not found in backend directory")

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
    flow.redirect_uri = redirect_uri or os.environ.get(
        "GOOGLE_REDIRECT_URI", "http://localhost:3000/oauth2callback"
    )

    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    return {"status": "needs_auth", "auth_url": auth_url}


def authenticate_google_calendar():
    """Return a calendar service if creds are already available; skip browser flows."""
    creds = _load_creds()
    if not creds:
        return None

    return build("calendar", "v3", credentials=creds, cache_discovery=False)
def get_calendar_service():
    global _cached_calendar_service
    if _cached_calendar_service is None:
        _cached_calendar_service = authenticate_google_calendar()
    return _cached_calendar_service
# --------------------------- Read helpers ---------------------------
def _normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    start = event.get("start", {})
    end = event.get("end", {})
    start_val = start.get("dateTime") or start.get("date")
    end_val = end.get("dateTime") or end.get("date")
    summary = event.get("summary") or "Untitled Event"
    is_all_day = "T" not in start_val if start_val else False
    if start_val and "T" in start_val:
        start_dt = datetime.fromisoformat(start_val.replace("Z", "+00:00"))
        date_str = start_dt.strftime("%B %d, %Y")
        start_time = start_dt.strftime("%I:%M %p")
    else:
        date_str = start_val
        start_time = None
    if end_val and "T" in end_val:
        end_dt = datetime.fromisoformat(end_val.replace("Z", "+00:00"))
        end_time = end_dt.strftime("%I:%M %p")
    else:
        end_time = None
    return {
        "id": event.get("id"),
        "summary": summary,
        "date": date_str,
        "start_time": start_time,
        "end_time": end_time,
        "is_all_day": is_all_day,
        "htmlLink": event.get("htmlLink"),
        "location": event.get("location"),
    }
def get_today_schedule() -> str:
    try:
        service = get_calendar_service()
        if service is None:
            return "Google Calendar authorization required"
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=today_start.isoformat() + "Z",
                timeMax=today_end.isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        if not events:
            return "No events scheduled for today"
        parts = []
        for evt in events:
            norm = _normalize_event(evt)
            when = "All day" if norm["is_all_day"] else norm.get("start_time")
            loc = f" at {norm['location']}" if norm.get("location") else ""
            parts.append(f"{norm['summary']} at {when}{loc}")
        return "; ".join(parts)
    except HttpError as exc:
        logger.error("Google Calendar API error: %s", exc)
        return "Unable to fetch calendar events"
    except Exception as exc:
        logger.error("Unexpected error fetching calendar: %s", exc)
        return "Unable to fetch calendar events"
def get_upcoming_events(days_ahead: int = 7) -> Dict[str, Any]:
    try:
        service = get_calendar_service()
        if service is None:
            return {"success": False, "error": "Google Calendar authorization required", "events": []}
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        end_time = now + timedelta(days=days_ahead)
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat(),
                timeMax=end_time.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = [_normalize_event(evt) for evt in events_result.get("items", [])]
        return {"success": True, "events": events}
    except Exception as exc:
        logger.error("Error fetching upcoming events: %s", exc)
        return {"success": False, "error": str(exc), "events": []}
def get_next_meeting() -> Dict[str, Any]:
    try:
        service = get_calendar_service()
        if service is None:
            return {"success": False, "error": "Google Calendar authorization required", "event": {}}
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now.isoformat(),
                maxResults=1,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        if not events:
            return {"success": True, "message": "No upcoming meetings", "event": {}}
        norm = _normalize_event(events[0])
        message = (
            f"Next meeting: {norm['summary']} on {norm.get('date')}"
            + (f" at {norm['start_time']}" if norm.get("start_time") else "")
        )
        return {"success": True, "event": norm, "message": message}
    except Exception as exc:
        logger.error("Error getting next meeting: %s", exc)
        return {"success": False, "error": str(exc)}
def get_free_time_today() -> Dict[str, Any]:
    try:
        service = get_calendar_service()
        if service is None:
            return {"success": False, "error": "Google Calendar authorization required", "free_slots": []}
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        start_of_day = now.replace(hour=9, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=17, minute=0, second=0, microsecond=0)
        events_result = (
            service.freebusy()
            .query(
                body={
                    "timeMin": start_of_day.isoformat(),
                    "timeMax": end_of_day.isoformat(),
                    "items": [{"id": "primary"}],
                }
            )
            .execute()
        )
        busy = events_result.get("calendars", {}).get("primary", {}).get("busy", [])
        free_slots: List[Dict[str, Any]] = []
        cursor = start_of_day
        for block in busy:
            busy_start = parser.isoparse(block["start"])
            busy_end = parser.isoparse(block["end"])
            if cursor < busy_start:
                delta = busy_start - cursor
                free_slots.append(
                    {
                        "start": cursor.strftime("%H:%M"),
                        "end": busy_start.strftime("%H:%M"),
                        "duration": int(delta.total_seconds() // 60),
                    }
                )
            cursor = max(cursor, busy_end)
        if cursor < end_of_day:
            delta = end_of_day - cursor
            free_slots.append(
                {
                    "start": cursor.strftime("%H:%M"),
                    "end": end_of_day.strftime("%H:%M"),
                    "duration": int(delta.total_seconds() // 60),
                }
            )
        return {"success": True, "free_slots": free_slots}
    except Exception as exc:
        logger.error("Error calculating free time: %s", exc)
        return {"success": False, "error": str(exc), "free_slots": []}
# --------------------------- Write helpers ---------------------------
def create_event_from_conversation(conversation_text: str) -> Dict[str, Any]:
    try:
        service = get_calendar_service()
        if service is None:
            return {"success": False, "error": "Google Calendar authorization required", "message": "Please authorize calendar access"}
        text = (conversation_text or "").strip()
        event = None
        try:
            event = (
                service.events()
                .quickAdd(calendarId="primary", text=text)
                .execute()
            )
        except HttpError as exc:
            if exc.resp.status == 400:
                logger.info("QuickAdd failed; falling back to manual parse: %s", exc)
                return manual_event_parser(text, get_calendar_service)
            raise
        norm = _normalize_event(event)
        message = (
            f"Event created: '{norm['summary']}' on {norm.get('date')}"
            + (f" at {norm['start_time']}" if norm.get("start_time") else "")
        )
        return {"success": True, "event": norm, "message": message}
    except Exception as exc:
        logger.error("Error creating event from conversation: %s", exc)
        return {"success": False, "error": str(exc), "message": "Could not create event"}
# Backward-compatible wrapper name expected elsewhere
create_event_manual_parse = manual_event_parser
def test_calendar_connection() -> Dict[str, Any]:
    try:
        service = get_calendar_service()
        service.calendarList().list(maxResults=1).execute()
        return {"success": True, "message": "Google Calendar is reachable"}
    except Exception as exc:
        logger.error("Calendar connection test failed: %s", exc)
        return {"success": False, "error": str(exc)}
__all__ = [
    "get_today_schedule",
    "get_upcoming_events",
    "get_next_meeting",
    "get_free_time_today",
    "create_event_from_conversation",
    "create_event_manual_parse",
    "test_calendar_connection",
    "get_calendar_service",
    "get_auth_url",
]
