"""Script to build persistent ChromaDB index from rubric JSONL files."""

import sys
from pathlib import Path

# Allow importing ielts_ai when running script directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ielts_ai.rag.indexer import build_index


def main() -> None:
    rubric_file = (
        Path(__file__).parent.parent / "data" / "rubric" / "ielts_task2_band_descriptors.jsonl"
    )
    count = build_index(rubric_file)
    print(f"Successfully indexed {count} rubric items.")


if __name__ == "__main__":
    main()
