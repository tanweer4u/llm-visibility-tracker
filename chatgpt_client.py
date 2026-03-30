"""
chatgpt_client.py
=================
Handles all OpenAI / ChatGPT API calls.
Model: gpt-4o.  API key read from OPENAI_API_KEY environment variable.
"""

import os
import logging

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a knowledgeable assistant helping Indian consumers understand car insurance. "
    "When asked about car insurance companies or comparisons, provide detailed, balanced, "
    "and factual information about the Indian market. List specific company names wherever relevant."
)


def _get_client():
    """Build and return an OpenAI client.  Raises ValueError if key is absent."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is not set. "
            "Please add it as a GitHub Secret (see README, section 'Setting up GitHub Secrets')."
        )
    from openai import OpenAI
    return OpenAI(api_key=api_key)


def get_chatgpt_response(prompt: str) -> str:
    """
    Query GPT-4o with *prompt* and return the response text.
    Raises an exception on any API error so the caller can log and continue.
    """
    client = _get_client()

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=1200,
        temperature=0.3,
    )

    if not response.choices:
        return "Unexpected response format: no choices returned by the API"

    content = (response.choices[0].message.content or "").strip()
    if not content:
        return "Unexpected response format: empty content in API response"

    return content


def test_connection() -> tuple[bool, str]:
    """
    Lightweight connectivity check.
    Returns (True, "Connection successful") or (False, plain-English error message).
    """
    try:
        client = _get_client()
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Reply with the single word OK."}],
            max_tokens=5,
        )
        if resp.choices:
            return True, "Connection successful"
        return False, "Empty response from API — unexpected format"
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        msg = str(e)
        if "401" in msg or "Unauthorized" in msg or "invalid_api_key" in msg:
            return False, (
                "401 Unauthorized — your OpenAI API key is wrong or has expired.\n"
                "  Fix: Go to https://platform.openai.com/api-keys, create a new key, "
                "and update the OPENAI_API_KEY secret in your GitHub repository."
            )
        if "429" in msg:
            return False, (
                "429 Rate Limited — you have exceeded your OpenAI usage quota.\n"
                "  Fix: Check your billing at https://platform.openai.com/account/billing"
            )
        if "insufficient_quota" in msg.lower():
            return False, (
                "Insufficient quota — your OpenAI account has no remaining credits.\n"
                "  Fix: Add payment at https://platform.openai.com/account/billing"
            )
        return False, f"Connection failed: {msg}"
