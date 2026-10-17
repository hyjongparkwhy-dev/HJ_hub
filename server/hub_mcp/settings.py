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
    # Headline names for watchlist stocks ("GOOG:구글,알파벳;META:메타") and words for the owner's neighbourhood.
    news_aliases: tuple[tuple[str, tuple[str, ...]], ...] = ()
    news_areas: tuple[str, ...] = ()


def parse_aliases(text: str | None) -> tuple[tuple[str, tuple[str, ...]], ...]:
    pairs = []
    for entry in (text or "").split(";"):
        symbol, _, names = entry.partition(":")
        words = tuple(w.strip() for w in names.split(",") if w.strip())
        if symbol.strip() and words:
            pairs.append((symbol.strip().upper(), words))
    return tuple(pairs)


def parse_words(text: str | None) -> tuple[str, ...]:
    return tuple(w.strip() for w in (text or "").split(",") if w.strip())


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
        get("RICHRICH_DATABASE_URL"),
        get("APT_DATABASE_URL"),
        get("APT_HOME_KEY"),
        band,
        get("HUB_OWNER_CONTEXT"),
        parse_aliases(get("HUB_NEWS_ALIASES")),
        parse_words(get("HUB_NEWS_AREAS")),
    )
