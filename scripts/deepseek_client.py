from __future__ import annotations

import json
import urllib.request

from _common import ROOT

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_TIMEOUT_SECONDS = 180


def model_for(route: str, fallback: str = "deepseek-v4-pro") -> str:
    if yaml is None:
        return fallback
    path = ROOT / "ops" / "model_routing.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return fallback
    models = data.get("models") if isinstance(data, dict) else {}
    config = models.get(route) if isinstance(models, dict) else {}
    model = config.get("model") if isinstance(config, dict) else None
    return str(model) if model else fallback


def call_deepseek(payload: dict, api_key: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))
