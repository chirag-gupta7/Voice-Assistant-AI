import json
import logging
import os
from typing import Tuple

from flask import current_app
from huggingface_hub import InferenceClient

logger = logging.getLogger(__name__)

HF_MODEL = "meta-llama/Meta-Llama-3-8B-Instruct"

# Updated Prompt for better intent recognition
SYSTEM_PROMPT = (
    "You are a smart voice assistant. "
    "Your goal is to classify user intent into JSON actions."
    " Respond ONLY in valid JSON format with keys: 'action' and 'reply'.\n\n"
    "RULES:\n"
    "1. If the user mentions 'meet', 'book', 'schedule', 'appointment', or 'calendar', classify as 'schedule_meeting'.\n"
    "2. If the user asks for weather, classify as 'weather'.\n"
    "3. Otherwise, use 'general_response'.\n"
    "4. 'reply' should be a short, friendly response spoken to the user.\n\n"
    "Valid 'action' values: ['schedule_meeting', 'weather', 'general_response']"
)


def _get_client():
    api_key = current_app.config.get("HUGGINGFACE_API_KEY")
    if not api_key:
        logger.info("HUGGINGFACE_API_KEY not configured; skipping LLM call")
        return None
    return InferenceClient(token=api_key)


def generate_action_reply(user_text: str) -> Tuple[str, str]:
    client = _get_client()
    if not client:
        return "general_response", "AI is not configured."

    # Construct messages for Chat API
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    try:
        response = client.chat_completion(
            model=HF_MODEL,
            messages=messages,
            max_tokens=150,
            temperature=0.3,
        )

        # Extract the content from the response object
        content = response.choices[0].message.content

        # Clean up potential markdown formatting (```json ... ```)
        if "```" in content:
            content = content.replace("```json", "").replace("```", "")

        content = content.strip()

    except Exception as exc:
        logger.warning("Hugging Face generation failed: %s", exc)
        return "general_response", "I'm having trouble connecting to the brain."

    # Parse JSON
    action = "general_response"
    reply = "I understood, but couldn't generate a structured response."

    try:
        data = json.loads(content)
        if isinstance(data, dict):
            action = data.get("action") or action
            reply = data.get("reply") or reply
    except json.JSONDecodeError:
        logger.warning("Failed to parse JSON from HF: %s", content)
        reply = content  # Fallback: just speak the raw text

    return action, reply
