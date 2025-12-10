import json
import logging
from typing import Tuple
import os

from flask import current_app
import google.generativeai as genai

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful voice meeting assistant."
    " Respond ONLY in raw JSON format (no markdown formatting) with keys 'action' and 'reply'."
    " action should be one of ['schedule_meeting', 'fetch_calendar', 'general_response']."
    " reply should be concise and user-friendly."
)


def _get_model():
    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key:
        logger.info("GEMINI_API_KEY not configured; skipping LLM call")
        return None

    genai.configure(api_key=api_key)

    # Prefer explicit model from env; otherwise fall back through a safe list.
    configured_model = os.getenv("GEMINI_MODEL") or current_app.config.get("GEMINI_MODEL")
    fallback_models = [
        "gemini-1.5-flash-8b",  # widely available
        "gemini-1.5-flash",     # legacy name
        "gemini-1.0-pro",       # older stable
    ]

    model_names = [configured_model] if configured_model else []
    model_names.extend([m for m in fallback_models if m not in model_names])

    last_error = None
    for name in model_names:
        try:
            return genai.GenerativeModel(name, system_instruction=SYSTEM_PROMPT)
        except Exception as exc:  # pragma: no cover
            last_error = exc
            logger.warning("Failed to init Gemini model '%s': %s", name, exc)

    # If everything fails, surface a clear log but keep app alive.
    if last_error:
        logger.error("All Gemini model attempts failed: %s", last_error)
    return None


def generate_action_reply(user_text: str) -> Tuple[str, str]:
    model = _get_model()
    if not model:
        return "general_response", "AI is not configured."

    try:
        # Generate content
        response = model.generate_content(
            user_text,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                response_mime_type="application/json",  # Enforces JSON output
            ),
        )

        content = response.text

    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Gemini generation failed: %s", exc)
        return "general_response", "I could not process that request."

    # Parse JSON
    action = "general_response"
    reply = "I understood, but couldn't generate a structured response."

    try:
        data = json.loads(content)
        if isinstance(data, dict):
            action = data.get("action") or action
            reply = data.get("reply") or reply
    except json.JSONDecodeError:
        # Fallback if JSON fails, though response_mime_type usually prevents this
        reply = content.strip()

    return action, reply
