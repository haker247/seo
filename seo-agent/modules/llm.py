"""
LLM-клиент SEO-завода: Cursor SDK по подписке Cursor.

Не chat-completions API, а одноразовый агент (`Agent.prompt`) с запретом
править файлы. Нужен `CURSOR_API_KEY` (Dashboard → API Keys / Integrations).

ENV:
    CURSOR_API_KEY  — ключ Cursor
    CURSOR_MODEL    — по умолчанию composer-2.5
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_CONTENT_FACTORY = Path(__file__).resolve().parent.parent.parent / "content-factory"
if str(_CONTENT_FACTORY) not in sys.path:
    sys.path.insert(0, str(_CONTENT_FACTORY))
try:
    import usage_ledger
except ImportError:
    usage_ledger = None

_NO_TOOLS = (
    "You are a text-only assistant. Do not edit files, do not run shell commands, "
    "do not call tools. Reply with ONLY the requested output — no preamble, "
    "no markdown fences unless the user asked for markdown."
)


def api_key() -> str:
    return os.environ.get("CURSOR_API_KEY", "").strip()


def configured() -> bool:
    return bool(api_key())


def model_id() -> str:
    return os.environ.get("CURSOR_MODEL", "composer-2.5").strip() or "composer-2.5"


def _cwd() -> str:
    ws = os.environ.get("GITHUB_WORKSPACE", "").strip()
    if ws:
        return ws
    return str(Path(__file__).resolve().parents[2])


def complete(system: str, user: str, *, note: str = "", max_tokens: int = 0) -> str:
    """Один текстовый ответ. max_tokens оставлен для совместимости вызовов."""
    del max_tokens
    key = api_key()
    if not key:
        raise RuntimeError("CURSOR_API_KEY не задан")

    from cursor_sdk import Agent, AgentOptions, CursorAgentError, LocalAgentOptions

    prompt = f"{_NO_TOOLS}\n\nSYSTEM:\n{system}\n\nUSER:\n{user}"
    model = model_id()
    try:
        result = Agent.prompt(
            prompt,
            AgentOptions(
                api_key=key,
                model=model,
                local=LocalAgentOptions(cwd=_cwd()),
            ),
        )
    except CursorAgentError as err:
        log.warning("Cursor SDK не стартовал: %s retryable=%s", err.message, err.is_retryable)
        raise

    if getattr(result, "status", None) == "error":
        raise RuntimeError(f"Cursor run failed: {getattr(result, 'id', '')}")

    if usage_ledger is not None:
        usage = getattr(result, "usage", None)
        usage_ledger.record(
            model=model,
            backend="cursor-sdk",
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_tokens=getattr(usage, "cache_read_tokens", 0) or 0,
            cache_creation_tokens=getattr(usage, "cache_write_tokens", 0) or 0,
            cost_usd=None,
            metered=False,
            run_id=str(getattr(result, "id", "") or "") or None,
            note=note,
        )

    return (getattr(result, "result", None) or "").strip()
