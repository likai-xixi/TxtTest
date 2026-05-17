from __future__ import annotations

from typing import Any


class DeepSeekResponseError(ValueError):
    pass


def extract_message_content(response: Any) -> str:
    if not isinstance(response, dict):
        raise DeepSeekResponseError("response root must be an object")

    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise DeepSeekResponseError("missing choices[0]")

    first = choices[0]
    if not isinstance(first, dict):
        raise DeepSeekResponseError("choices[0] must be an object")

    message = first.get("message")
    if not isinstance(message, dict):
        raise DeepSeekResponseError("missing choices[0].message")

    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise DeepSeekResponseError("missing choices[0].message.content")

    return content.strip()
