from __future__ import annotations

import argparse
import os
import sys
import urllib.error

from deepseek_client import call_deepseek, model_for
from deepseek_response import DeepSeekResponseError, extract_message_content


ROUTES = (
    "deepseek_idea",
    "deepseek_brief",
    "deepseek_generate",
    "deepseek_review",
    "deepseek_style_review",
    "deepseek_anti_ai_review",
    "deepseek_semantic_reader_review",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check DeepSeek configuration and optionally make a live minimal request.")
    parser.add_argument("--no-live", action="store_true", help="Only check local configuration and DEEPSEEK_API_KEY.")
    parser.add_argument("--model", default=model_for("deepseek_preflight"))
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    print("# DeepSeek Preflight")
    print()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    print(f"DEEPSEEK_API_KEY: {'set' if api_key else 'missing'}")
    for route in ROUTES:
        print(f"{route}: {model_for(route)}")
    print(f"preflight_model: {args.model}")

    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY is not set.", file=sys.stderr)
        return 2

    if args.no_live:
        print()
        print("status: READY_LOCAL")
        print("live_request: skipped")
        return 0

    payload = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": "You are a connectivity preflight. Reply with OK only."},
            {"role": "user", "content": "OK"},
        ],
        "temperature": 0,
        "max_tokens": 8,
        "stream": False,
    }
    try:
        response = call_deepseek(payload, api_key, timeout=args.timeout)
        content = extract_message_content(response)
    except urllib.error.HTTPError as exc:
        print(f"ERROR: DeepSeek HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"ERROR: DeepSeek request failed: {exc}", file=sys.stderr)
        return 1
    except DeepSeekResponseError as exc:
        print(f"ERROR: invalid DeepSeek response: {exc}", file=sys.stderr)
        return 1

    print()
    print("status: READY_LIVE")
    print(f"response_preview: {content[:40]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
