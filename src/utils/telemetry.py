from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional


@contextmanager
def time_step(
    logger: logging.Logger,
    step: str,
    *,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    message_id: Optional[str] = None,
    tags: Optional[Dict[str, Any]] = None,
):
    """
    Structured timing context manager.

    Logs a single JSON line with fields:
      event: "step_timing"
      step: step name (e.g., "fb.send_message")
      ms: elapsed milliseconds
      user_id, session_id, message_id: optional correlation fields
      ok: True/False depending on exception
      error: error string when ok=False
      tags: arbitrary extra fields (small flat dict)
    """
    start = time.perf_counter()
    err_str: Optional[str] = None
    try:
        yield
        ok = True
    except Exception as e:  # noqa: BLE001
        ok = False
        err_str = f"{type(e).__name__}: {e}"
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        payload: Dict[str, Any] = {
            "event": "step_timing",
            "step": step,
            "ms": round(elapsed_ms, 2),
            "ok": ok,
        }
        if user_id is not None:
            payload["user_id"] = str(user_id)
        if session_id is not None:
            payload["session_id"] = str(session_id)
        if message_id is not None:
            payload["message_id"] = str(message_id)
        if tags:
            # keep it shallow to avoid huge logs
            for k, v in list(tags.items())[:15]:
                payload[f"tag_{k}"] = v
        if not ok and err_str:
            payload["error"] = err_str

        try:
            # Log as structured JSON for easy ingestion, plus extra for processors
            logger.info("PERF %s", json.dumps(payload, ensure_ascii=False), extra=payload)
        except Exception:
            # Fallback to basic log if formatter/extras fail
            logger.info("PERF step=%s ms=%.2f ok=%s uid=%s sid=%s", step, elapsed_ms, ok, user_id, session_id)
