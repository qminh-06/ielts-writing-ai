"""Database repository — typed functions for all DB operations.

All functions use plain sqlite3 (no ORM).
Status transitions are enforced here; invalid transitions raise ValueError.
"""

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Valid status transitions
_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["ai_done", "grading_failed"],
    "ai_done": ["reviewing", "grading_failed"],
    "reviewing": ["approved", "grading_failed", "ai_done"],  # ai_done for regrade
    "approved": ["emailed", "grading_failed"],
    "emailed": [],
    "grading_failed": ["pending"],  # allow retry
}


@contextmanager
def _get_conn(db_path: str) -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection and always close it after its transaction."""
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(db_path: str, schema_path: str | None = None) -> None:
    """Initialize database schema from SQL file.

    Args:
        db_path: Path to the SQLite database file.
        schema_path: Path to schema.sql. Defaults to db/schema.sql.
    """
    if schema_path is None:
        schema_path = str(Path(__file__).parent / "schema.sql")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with _get_conn(db_path) as conn:
        conn.executescript(Path(schema_path).read_text())
        review_columns = conn.execute("PRAGMA table_info(reviews)").fetchall()
        approved_column = next(row for row in review_columns if row["name"] == "approved_at")
        if approved_column["notnull"]:
            conn.executescript(
                """CREATE TABLE reviews_migrated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    essay_id INTEGER NOT NULL REFERENCES essays(id),
                    final_bands_json TEXT NOT NULL,
                    examiner_comment TEXT NOT NULL,
                    approved_at TEXT,
                    action TEXT NOT NULL DEFAULT 'accept'
                );
                INSERT INTO reviews_migrated
                    (id, essay_id, final_bands_json, examiner_comment, approved_at, action)
                SELECT id, essay_id, final_bands_json, examiner_comment, approved_at, 'accept'
                FROM reviews;
                DROP TABLE reviews;
                ALTER TABLE reviews_migrated RENAME TO reviews;"""
            )
        elif not any(row["name"] == "action" for row in review_columns):
            conn.execute("ALTER TABLE reviews ADD COLUMN action TEXT NOT NULL DEFAULT 'accept'")
    logger.info("Database initialized at %s", db_path)


def create_essay(
    db_path: str,
    candidate_email: str,
    prompt_text: str,
    essay_text: str,
) -> int:
    """Create a new essay record and return its ID.

    Args:
        db_path: SQLite database path.
        candidate_email: Candidate's email address.
        prompt_text: IELTS writing prompt/question.
        essay_text: Candidate's essay text.

    Returns:
        The ID of the newly created essay.
    """
    with _get_conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO essays (candidate_email, prompt_text, essay_text) VALUES (?, ?, ?)",
            (candidate_email, prompt_text, essay_text),
        )
        essay_id = cur.lastrowid
    logger.info("Created essay id=%s for %s", essay_id, candidate_email)
    return essay_id


def get_essay(db_path: str, essay_id: int) -> dict[str, Any] | None:
    """Fetch a single essay by ID.

    Args:
        db_path: SQLite database path.
        essay_id: Essay ID.

    Returns:
        Essay dict or None if not found.
    """
    with _get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM essays WHERE id = ?", (essay_id,)).fetchone()
    return dict(row) if row else None


def list_essays(db_path: str) -> list[dict[str, Any]]:
    """List all essays ordered by created_at descending.

    Args:
        db_path: SQLite database path.

    Returns:
        List of essay dicts.
    """
    with _get_conn(db_path) as conn:
        rows = conn.execute("SELECT * FROM essays ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def set_status(db_path: str, essay_id: int, new_status: str) -> None:
    """Update essay status, enforcing allowed transitions.

    Args:
        db_path: SQLite database path.
        essay_id: Essay ID.
        new_status: Target status.

    Raises:
        ValueError: If the transition is not allowed.
        LookupError: If essay_id does not exist.
    """
    essay = get_essay(db_path, essay_id)
    if essay is None:
        raise LookupError(f"Essay id={essay_id} not found")
    current = essay["status"]
    allowed = _TRANSITIONS.get(current, [])
    if new_status not in allowed:
        raise ValueError(
            f"Invalid status transition for essay {essay_id}: {current!r} → {new_status!r}. "
            f"Allowed: {allowed}"
        )
    with _get_conn(db_path) as conn:
        conn.execute("UPDATE essays SET status = ? WHERE id = ?", (new_status, essay_id))
    logger.info("Essay %s status: %s → %s", essay_id, current, new_status)


def save_ai_result(db_path: str, essay_id: int, version: int, result_json: str) -> int:
    """Save an AI grading result.

    Args:
        db_path: SQLite database path.
        essay_id: Essay ID.
        version: Grading version (increments on regrade).
        result_json: Serialized GradingResult JSON.

    Returns:
        ID of the new ai_results record.
    """
    with _get_conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO ai_results (essay_id, version, result_json) VALUES (?, ?, ?)",
            (essay_id, version, result_json),
        )
    return cur.lastrowid


def list_ai_results(db_path: str, essay_id: int) -> list[dict[str, Any]]:
    """List all AI results for an essay (newest first).

    Args:
        db_path: SQLite database path.
        essay_id: Essay ID.

    Returns:
        List of ai_results dicts.
    """
    with _get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM ai_results WHERE essay_id = ? ORDER BY version DESC",
            (essay_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def save_review(
    db_path: str,
    essay_id: int,
    final_bands_json: str,
    examiner_comment: str,
    action: str = "accept",
) -> int:
    """Save examiner review decision.

    Args:
        db_path: SQLite database path.
        essay_id: Essay ID.
        final_bands_json: JSON dict of final band scores per criterion.
        examiner_comment: Examiner's overall comment.

    Returns:
        ID of the new reviews record.
    """
    with _get_conn(db_path) as conn:
        if action == "draft":
            conn.execute("DELETE FROM reviews WHERE essay_id = ? AND action = 'draft'", (essay_id,))
            cur = conn.execute(
                "INSERT INTO reviews (essay_id, final_bands_json, examiner_comment, approved_at, action) "
                "VALUES (?, ?, ?, NULL, 'draft')",
                (essay_id, final_bands_json, examiner_comment),
            )
        else:
            cur = conn.execute(
                "INSERT INTO reviews (essay_id, final_bands_json, examiner_comment, action) "
                "VALUES (?, ?, ?, ?)",
                (essay_id, final_bands_json, examiner_comment, action),
            )
    return cur.lastrowid


def save_regrade_request(
    db_path: str, essay_id: int, criterion: str, feedback: str, from_version: int, to_version: int
) -> int:
    """Persist a completed re-grade request and its version link."""
    with _get_conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO regrade_requests (essay_id, criterion, feedback, from_version, to_version) "
            "VALUES (?, ?, ?, ?, ?)",
            (essay_id, criterion, feedback, from_version, to_version),
        )
    return cur.lastrowid


def list_regrade_requests(db_path: str, essay_id: int) -> list[dict[str, Any]]:
    """List an essay's re-grade history in creation order."""
    with _get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM regrade_requests WHERE essay_id = ? ORDER BY id", (essay_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def get_review_record(db_path: str, essay_id: int) -> dict[str, Any] | None:
    """Return the latest approved review, if any."""
    with _get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM reviews WHERE essay_id = ? AND action = 'accept' "
            "ORDER BY id DESC LIMIT 1",
            (essay_id,),
        ).fetchone()
    return dict(row) if row else None


def get_review_draft(db_path: str, essay_id: int) -> dict[str, Any] | None:
    """Return the current editable review draft, if any."""
    with _get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM reviews WHERE essay_id = ? AND action = 'draft' "
            "ORDER BY id DESC LIMIT 1",
            (essay_id,),
        ).fetchone()
    return dict(row) if row else None


def record_email(
    db_path: str,
    essay_id: int,
    to_email: str,
    status: str,
    error: str | None = None,
) -> int:
    """Record an email send attempt.

    Args:
        db_path: SQLite database path.
        essay_id: Essay ID.
        to_email: Recipient email.
        status: 'sent' | 'failed' | 'dry_run'.
        error: Error message if status='failed'.

    Returns:
        ID of the new emails record.
    """
    sent_at = "datetime('now')" if status == "sent" else None
    with _get_conn(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO emails (essay_id, to_email, status, error, sent_at) VALUES (?, ?, ?, ?, ?)",
            (essay_id, to_email, status, error, sent_at),
        )
    return cur.lastrowid


def claim_email_send(db_path: str, essay_id: int, to_email: str) -> int:
    """Atomically reserve an email send attempt for an approved essay."""
    with _get_conn(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        essay = conn.execute("SELECT status FROM essays WHERE id = ?", (essay_id,)).fetchone()
        if essay is None:
            raise LookupError(f"Essay id={essay_id} not found")
        if essay["status"] != "approved":
            raise ValueError("Email can only be sent when essay status is 'approved'.")
        existing = conn.execute(
            "SELECT id FROM emails WHERE essay_id = ? AND status IN ('sending', 'sent') LIMIT 1",
            (essay_id,),
        ).fetchone()
        if existing:
            raise ValueError("An email is already sending or has already been sent for this essay.")
        cur = conn.execute(
            "INSERT INTO emails (essay_id, to_email, status) VALUES (?, ?, 'sending')",
            (essay_id, to_email),
        )
    return cur.lastrowid


def complete_email_send(db_path: str, email_id: int) -> None:
    """Atomically mark a claimed email sent and its approved essay emailed."""
    with _get_conn(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        attempt = conn.execute(
            "SELECT essay_id FROM emails WHERE id = ? AND status = 'sending'", (email_id,)
        ).fetchone()
        if attempt is None:
            raise ValueError("Email attempt is not in the sending state.")
        essay_id = attempt["essay_id"]
        cursor = conn.execute(
            "UPDATE essays SET status = 'emailed' WHERE id = ? AND status = 'approved'",
            (essay_id,),
        )
        if cursor.rowcount != 1:
            raise ValueError("Essay must remain approved until its email is sent.")
        cursor = conn.execute(
            "UPDATE emails SET status = 'sent', sent_at = datetime('now'), error = NULL "
            "WHERE id = ? AND status = 'sending'",
            (email_id,),
        )
        if cursor.rowcount != 1:
            raise ValueError("Email attempt could not be completed.")


def fail_email_send(db_path: str, email_id: int, error: str) -> None:
    """Mark a claimed email attempt as failed with a sanitized error."""
    with _get_conn(db_path) as conn:
        conn.execute(
            "UPDATE emails SET status = 'failed', error = ? WHERE id = ?", (error, email_id)
        )


def list_email_attempts(db_path: str, essay_id: int | None = None) -> list[dict[str, Any]]:
    """List email attempts, optionally for one essay, newest first."""
    with _get_conn(db_path) as conn:
        if essay_id is None:
            rows = conn.execute("SELECT * FROM emails ORDER BY id DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM emails WHERE essay_id = ? ORDER BY id DESC", (essay_id,)
            ).fetchall()
    return [dict(row) for row in rows]


def log_llm_call(
    db_path: str,
    essay_id: int | None,
    step: str,
    latency_ms: float,
    input_tokens: int,
    output_tokens: int,
    retries: int = 0,
    status: str = "ok",
    error: str | None = None,
) -> int:
    """Log a single LLM or retrieval call.

    Args:
        db_path: SQLite database path.
        essay_id: Essay ID (can be None for non-essay calls).
        step: Pipeline step name (e.g. 'grade', 'retrieve_rubric').
        latency_ms: Call latency in milliseconds.
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        retries: Number of retries made.
        status: 'ok' | 'error'.
        error: Error message if status='error'.

    Returns:
        ID of the new llm_calls record.
    """
    with _get_conn(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO llm_calls
               (essay_id, step, latency_ms, input_tokens, output_tokens, retries, status, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (essay_id, step, latency_ms, input_tokens, output_tokens, retries, status, error),
        )
    return cur.lastrowid


def list_llm_calls(db_path: str, essay_id: int | None = None) -> list[dict[str, Any]]:
    """List LLM call logs, optionally filtered by essay.

    Args:
        db_path: SQLite database path.
        essay_id: Optional essay ID to filter by.

    Returns:
        List of llm_calls dicts, newest first.
    """
    with _get_conn(db_path) as conn:
        if essay_id is not None:
            rows = conn.execute(
                "SELECT * FROM llm_calls WHERE essay_id = ? ORDER BY ts DESC",
                (essay_id,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM llm_calls ORDER BY ts DESC").fetchall()
    return [dict(r) for r in rows]
