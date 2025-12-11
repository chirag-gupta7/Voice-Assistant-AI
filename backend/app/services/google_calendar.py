import logging
import os
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from ..extensions import db
from ..models import User

logger = logging.getLogger(__name__)


def _build_service(access_token: str):
    """Create a Google Calendar service client using a raw access token."""
    if not access_token:
        return None

    try:
        creds = Credentials(token=access_token)
        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Failed to initialize Google Calendar service: %s", exc)
        return None


def list_upcoming_events(
    access_token: str, max_results: int = 10, days_ahead: int = 7
) -> List[Dict[str, Any]]:
    """Return upcoming events from the primary calendar."""
    service = _build_service(access_token)
    if not service:
        return []

    time_min = datetime.now(timezone.utc).isoformat()
    time_max = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat()

    try:
        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        return result.get("items", [])
    except HttpError as exc:
        logger.warning("Google Calendar list failed: %s", exc)
        return []


def create_event(access_token: str, event_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create an event in the user's primary calendar."""
    service = _build_service(access_token)
    if not service:
        return None

    try:
        created = (
            service.events()
            .insert(calendarId="primary", body=event_payload, sendUpdates="all")
            .execute()
        )
        return created
    except HttpError as exc:
        logger.warning("Google Calendar insert failed: %s", exc)
        return None


__all__ = ["list_upcoming_events", "create_event", "get_auth_url"]


def get_auth_url() -> str:
    """Generate a Google OAuth URL for the frontend to open."""
    creds_file = os.path.join(os.getcwd(), "credentials.json")
    flow = InstalledAppFlow.from_client_secrets_file(
        creds_file,
        scopes=["https://www.googleapis.com/auth/calendar.events"],
    )
    flow.redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:3000/oauth2callback")
    auth_url, _ = flow.authorization_url(prompt="consent")
    return auth_url


def get_service_for_user(user_id: str):
    """Return a calendar service using stored user credentials, or None if not connected."""
    user = User.query.get(user_id)
    if not user or not user.google_credentials:
        return None

    try:
        creds = Credentials.from_authorized_user_info(user.google_credentials)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            user.google_credentials = json.loads(creds.to_json())
            db.session.commit()

        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to load calendar creds for user %s: %s", user_id, exc)
        return None
