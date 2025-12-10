import json
import logging
from typing import Optional, Tuple
import os

from flask import current_app
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

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

    # Using Gemini 1.5 Flash for speed and low latency (ideal for voice)
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT,
    )
    return model


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
