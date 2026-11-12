"""Tests for database operations and status transitions."""

import pytest

from ielts_ai.db.repo import create_essay, get_essay, init_db, set_status


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
