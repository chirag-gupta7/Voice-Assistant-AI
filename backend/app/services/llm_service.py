import json
import logging
from typing import Optional, Tuple

from flask import current_app
from openai import OpenAI

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a helpful voice meeting assistant."
    " Respond in JSON with keys 'action' and 'reply'."
    " action should be one of ['schedule_meeting','fetch_calendar','general_response']."
    " reply should be concise and user-friendly."
)


def _get_client() -> Optional[OpenAI]:
    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        logger.info("OPENAI_API_KEY not configured; skipping LLM call")
        return None
    try:
        return OpenAI(api_key=api_key)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Failed to init OpenAI client: %s", exc)
        return None


def generate_action_reply(user_text: str) -> Tuple[str, str]:
    client = _get_client()
    if not client:
        return "general_response", "AI is not configured."

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        content = completion.choices[0].message.content or ""
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("OpenAI chat completion failed: %s", exc)
        return "general_response", "I could not process that request."

    # Try to parse JSON; fall back to raw text.
    action = "general_response"
    reply = content.strip()
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            action = data.get("action") or action
            reply = data.get("reply") or reply
    except json.JSONDecodeError:
        pass

    return action, reply


__all__ = ["generate_action_reply"]
