"""Settings for the my-hub MCP server: my-hub/.env, overridden by real environment variables."""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
HOME_BANDS = ("59", "74", "84", "large")


@dataclass(frozen=True)
class Settings:
    richrich_database_url: str | None
    apt_database_url: str | None
    apt_home_key: str | None
    apt_home_band: str | None
    # Who the data belongs to (e.g. where they live); kept in .env so the repository holds no personal details.
    owner_context: str | None = None


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_settings(env: Mapping[str, str] | None = None, env_file: Path = ENV_FILE) -> Settings:
    merged = {**read_env_file(env_file), **(os.environ if env is None else env)}

    def get(name: str) -> str | None:
        return merged.get(name, "").strip() or None

    band = get("APT_HOME_BAND")
    if band is not None and band not in HOME_BANDS:
        raise ValueError(f"APT_HOME_BAND must be one of {', '.join(HOME_BANDS)}")
    return Settings(
        get("RICHRICH_DATABASE_URL"), get("APT_DATABASE_URL"), get("APT_HOME_KEY"), band, get("HUB_OWNER_CONTEXT")
    )
