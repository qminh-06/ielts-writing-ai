"""Regression tests for duplicate grading and re-grade submissions."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from ielts_ai.db.repo import create_essay, init_db
from ielts_ai.schemas import Criterion
from ielts_ai.services.grading_service import GradingInProgressError, start_grading
from ielts_ai.services.review_service import ReviewValidationError, request_regrade


def test_second_grading_request_for_same_essay_is_ignored(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = str(tmp_path / "grade.db")
    init_db(db_path)
    monkeypatch.setenv("DB_PATH", db_path)
    essay_id = create_essay(
        db_path,
        "candidate@example.com",
        "Discuss education.",
        "Education supports resilient communities. " * 20,
    )
    entered = Event()
    release = Event()

    def blocked_grading(**kwargs):
        entered.set()
        assert release.wait(timeout=5)
        return {"result": None, "errors": [], "warnings": []}

    monkeypatch.setattr("ielts_ai.services.grading_service.run_grading", blocked_grading)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(start_grading, essay_id)
        assert entered.wait(timeout=2)
        try:
            with pytest.raises(GradingInProgressError):
                start_grading(essay_id)
        finally:
            release.set()
        assert future.result(timeout=5)["essay_id"] == essay_id


def test_second_regrade_request_for_same_essay_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = Event()
    release = Event()

    def blocked_regrade(essay_id: int, criterion: Criterion, feedback: str):
        entered.set()
        assert release.wait(timeout=5)
        return None

    monkeypatch.setattr("ielts_ai.services.review_service._request_regrade", blocked_regrade)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(request_regrade, 123, Criterion.TR, "Please reconsider this response.")
        assert entered.wait(timeout=2)
        try:
            with pytest.raises(ReviewValidationError, match="already in progress"):
                request_regrade(123, Criterion.TR, "Please reconsider this response.")
        finally:
            release.set()
        assert future.result(timeout=5) is None
