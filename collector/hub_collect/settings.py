"""HUB_DATABASE_URL from the environment, falling back to my-hub/.env for local runs."""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def load_database_url(env: Mapping[str, str] | None = None, env_file: Path = ENV_FILE) -> str | None:
    source = os.environ if env is None else env
    value = source.get("HUB_DATABASE_URL", "").strip()
    if value:
        return value
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, rest = raw.strip().partition("=")
            if sep and key.strip() == "HUB_DATABASE_URL":
                return rest.strip().strip('"').strip("'") or None
    return None
