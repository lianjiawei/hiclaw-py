from __future__ import annotations

import json
from hiclaw.config import DATA_DIR, AGENT_PROVIDER


PROVIDER_STATE_FILE = DATA_DIR / "agent_provider.json"


def get_provider() -> str:
    if not PROVIDER_STATE_FILE.exists():
        return AGENT_PROVIDER.strip().lower()
    try:
        data = json.loads(PROVIDER_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AGENT_PROVIDER.strip().lower()
    provider = str(data.get("provider") or "").strip().lower()
    return provider or AGENT_PROVIDER.strip().lower()


def set_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    PROVIDER_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROVIDER_STATE_FILE.write_text(json.dumps({"provider": normalized}, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized
