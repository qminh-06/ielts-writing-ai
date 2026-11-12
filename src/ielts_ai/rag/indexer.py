"""Indexer for building persistent ChromaDB store from rubric JSONL files.

# TODO(B2): Implement full chunking, embedding, and indexing logic.
"""
import json
import logging
from pathlib import Path

from ielts_ai.config import get_settings

logger = logging.getLogger(__name__)


def build_index(
    rubric_file: Path | str,
    chroma_dir: Path | str | None = None,
) -> int:
    """Read rubric JSONL and index into ChromaDB collection.

    # TODO(B2): Implement ChromaDB batch insertion with proper embeddings.
    """
    settings = get_settings()
    target_dir = str(chroma_dir or settings.chroma_dir)
    rubric_path = Path(rubric_file)

    if not rubric_path.exists():
        raise FileNotFoundError(f"Rubric file not found: {rubric_path}")

    logger.info("Indexing %s into ChromaDB at %s", rubric_path, target_dir)

    try:
        import chromadb

        client = chromadb.PersistentClient(path=target_dir)
        collection = client.get_or_create_collection("ielts_rubric")

        docs = []
        metas = []
        ids = []

        count = 0
        with open(rubric_path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                docs.append(item["text"])
                metas.append({
                    "criterion": item["criterion"],
                    "band": int(item["band"]),
                    "source": item.get("source", "official"),
                })
                ids.append(f"{item['criterion']}_band_{item['band']}_{i}")
                count += 1

        if ids:
            collection.upsert(ids=ids, documents=docs, metadatas=metas)

        logger.info("Indexed %d rubric chunks into ChromaDB", count)
        return count
    except ImportError:
        logger.warning("chromadb not installed or failed to import. Skipping persistent indexing.")
        return 0
