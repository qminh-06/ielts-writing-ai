"""LLM and retrieval call logger.

Usage as context manager:
    with log_call("grade", essay_id=1, db_path="data/app.db") as ctx:
        result = llm_client.complete_json(system, user)
        ctx.set_tokens(result.input_tokens, result.output_tokens)
"""

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class CallContext:
    """Mutable context passed to the caller to set token counts and retries."""

    def __init__(self) -> None:
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.retries: int = 0

    def set_tokens(self, input_tokens: int, output_tokens: int) -> None:
        """Set token counts from LLM response."""
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens

    def set_retries(self, retries: int) -> None:
        """Set retry count."""
        self.retries = retries


@contextmanager
def log_call(
    step: str,
    essay_id: int | None,
    db_path: str,
) -> Generator[CallContext, None, None]:
    """Context manager that logs an LLM or retrieval call to the DB.

    Records latency, token counts, retries, status, and error.

    Args:
        step: Pipeline step name (e.g. 'grade', 'retrieve_rubric').
        essay_id: Associated essay ID, or None.
        db_path: SQLite database path.

    Yields:
        CallContext: Use ctx.set_tokens() and ctx.set_retries() inside the block.
    """
    from ielts_ai.db.repo import log_llm_call

    ctx = CallContext()
    start = time.monotonic()
    error_msg: str | None = None
    status = "ok"

    try:
        yield ctx
    except Exception as exc:
        status = "error"
        error_msg = str(exc)
        logger.error("LLM call failed — step=%s essay_id=%s error=%s", step, essay_id, exc)
        raise
    finally:
        latency_ms = (time.monotonic() - start) * 1000
        try:
            log_llm_call(
                db_path=db_path,
                essay_id=essay_id,
                step=step,
                latency_ms=latency_ms,
                input_tokens=ctx.input_tokens,
                output_tokens=ctx.output_tokens,
                retries=ctx.retries,
                status=status,
                error=error_msg,
            )
        except Exception as log_exc:
            logger.error("Failed to log LLM call: %s", log_exc)
