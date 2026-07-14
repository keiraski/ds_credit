from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
DEFAULT_MODEL = "gpt-4o-mini"


def _load_env_file(path: Path = ENV_FILE) -> None:
    """Прочитать .env (KEY=VALUE), не перетирая уже заданные переменные."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_env_file()

LLM_API_KEY: str = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL: str = os.getenv("LLM_MODEL", DEFAULT_MODEL).strip()
LLM_BASE_URL: str | None = os.getenv("LLM_BASE_URL", "").strip() or None


def llm_enabled() -> bool:
    """True, если задан ключ и можно пробовать LLM-режим."""
    return bool(LLM_API_KEY)
