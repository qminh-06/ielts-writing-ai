"""Time one synthetic essay grading run with the configured real Gemini provider."""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ielts_ai.config import get_settings  # noqa: E402
from ielts_ai.db.repo import create_essay, init_db, list_llm_calls  # noqa: E402
from ielts_ai.services.grading_service import start_grading  # noqa: E402


def main() -> None:
    """Grade one synthetic essay using a disposable database and print call timings."""
    eval_path = ROOT / "data" / "eval_set" / "synthetic_essays.json"
    essays = json.loads(eval_path.read_text(encoding="utf-8"))
    if not essays:
        raise RuntimeError("The synthetic evaluation set is empty.")
    item = essays[0]

    with tempfile.TemporaryDirectory(prefix="ielts-ai-timing-") as workdir:
        db_path = str(Path(workdir) / "timing.db")
        environment = {
            "DB_PATH": db_path,
            "LLM_PROVIDER": "real",
            "USE_MOCK_RAG": "true",
        }
        with patch.dict(os.environ, environment):
            settings = get_settings()
            init_db(settings.db_path)
            essay_id = create_essay(
                settings.db_path,
                "synthetic@example.invalid",
                item["prompt"],
                item["essay"],
            )
            started = time.perf_counter()
            result = start_grading(essay_id)
            total_seconds = time.perf_counter() - started
            calls = list_llm_calls(settings.db_path, essay_id)

    headers = (
        "step",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "thinking_tokens",
        "retries",
        "status",
        "error",
    )
    print("\t".join(headers))
    for call in calls:
        print("\t".join(str(call[key] if call[key] is not None else "") for key in headers))
    print(f"essay_status={result['status']}")
    print(f"total_wall_seconds={total_seconds:.3f}")
    if result["errors"]:
        print("grading_error=" + " | ".join(result["errors"]))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
