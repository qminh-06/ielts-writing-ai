"""Tests for database operations and status transitions."""

import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from ielts_ai.db.repo import _get_conn, create_essay, get_essay, init_db, set_status


@pytest.fixture
def test_db(tmp_path: pytest.TempPathFactory) -> str:
    db_file = str(tmp_path / "test.db")
    init_db(db_file)
    return db_file


def test_db_status_transitions(test_db: str) -> None:
    essay_id = create_essay(test_db, "candidate@example.com", "Prompt?", "Essay content...")
    assert essay_id is not None

    essay = get_essay(test_db, essay_id)
    assert essay["status"] == "pending"

    # Valid transitions: pending -> ai_done -> reviewing -> approved -> emailed
    set_status(test_db, essay_id, "ai_done")
    assert get_essay(test_db, essay_id)["status"] == "ai_done"

    set_status(test_db, essay_id, "reviewing")
    assert get_essay(test_db, essay_id)["status"] == "reviewing"

    set_status(test_db, essay_id, "approved")
    assert get_essay(test_db, essay_id)["status"] == "approved"

    set_status(test_db, essay_id, "emailed")
    assert get_essay(test_db, essay_id)["status"] == "emailed"

    # Invalid transition from emailed
    with pytest.raises(ValueError, match="Invalid status transition"):
        set_status(test_db, essay_id, "pending")


def test_sqlite_connections_use_wal_and_wait_for_concurrent_writer(test_db: str) -> None:
    writer_started = Event()

    def second_writer() -> int:
        writer_started.set()
        return create_essay(test_db, "writer@example.com", "Prompt", "Essay")

    with ThreadPoolExecutor(max_workers=1) as pool:
        with _get_conn(test_db) as first:
            assert first.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
            assert first.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
            first.execute("BEGIN IMMEDIATE")
            future = pool.submit(second_writer)
            assert writer_started.wait(timeout=2)
            time.sleep(0.1)
            first.commit()
        essay_id = future.result(timeout=5)

    assert get_essay(test_db, essay_id)["candidate_email"] == "writer@example.com"


def test_init_db_migrates_existing_call_log_for_thinking_tokens(tmp_path) -> None:
    db_path = str(tmp_path / "legacy.db")
    connection = sqlite3.connect(db_path)
    connection.execute(
        """CREATE TABLE llm_calls (
            id INTEGER PRIMARY KEY,
            ts TEXT NOT NULL DEFAULT (datetime('now')),
            essay_id INTEGER,
            step TEXT NOT NULL,
            latency_ms REAL NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            retries INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'ok',
            error TEXT
        )"""
    )
    connection.commit()
    connection.close()

    init_db(db_path)
    init_db(db_path)
    with sqlite3.connect(db_path) as migrated:
        columns = {row[1] for row in migrated.execute("PRAGMA table_info(llm_calls)")}

    assert "thinking_tokens" in columns
