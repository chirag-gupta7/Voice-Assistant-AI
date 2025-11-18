from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from dateutil import parser as date_parser


DURATION_PATTERN = re.compile(r"(\d{1,3})\s?(minutes|min|hours|hrs|hour)", re.IGNORECASE)
TITLE_FALLBACK = "Voice Scheduled Meeting"


@dataclass
class VoiceCommand:
    transcript: str
    title: str
    start_time: datetime
    duration: int
    notes: str | None = None


def parse_voice_command(transcript: str) -> VoiceCommand | None:
    text = transcript.strip()
    if not text:
        return None

    duration = _extract_duration(text)
    start_time = _extract_datetime(text)
    title = _extract_title(text) or TITLE_FALLBACK

    return VoiceCommand(
        transcript=text,
        title=title,
        start_time=start_time,
        duration=duration,
        notes=text,
    )


def _extract_duration(text: str) -> int:
    match = DURATION_PATTERN.search(text)
    if not match:
        return 30

    value = int(match.group(1))
    unit = match.group(2).lower()

    if unit.startswith("hour") or unit in {"hrs", "hr"}:
        return value * 60

    return value


def _extract_datetime(text: str) -> datetime:
    try:
        parsed = date_parser.parse(text, fuzzy=True, default=datetime.utcnow())
        # Ensure future time preference
        if parsed < datetime.utcnow():
            parsed = parsed + timedelta(days=1)
        return parsed
    except (ValueError, OverflowError):
        return datetime.utcnow() + timedelta(hours=1)


def _extract_title(text: str) -> str:
    lowered = text.lower()
    keywords = ["with", "about", "regarding"]

    for keyword in keywords:
        if keyword in lowered:
            portion = text.split(keyword, maxsplit=1)[-1].strip()
            return portion.title()

    return text[:60].strip().title()
