"""RAG retriever for IELTS rubric descriptors.

Supports:
- In-memory keyword fallback (USE_MOCK_RAG=true) for tests/CI without model downloads
- ChromaDB persistent store for production (USE_MOCK_RAG=false)
"""
import json
import logging
from pathlib import Path
from typing import Any

from ielts_ai.config import get_settings
from ielts_ai.schemas import Criterion, RubricChunk

logger = logging.getLogger(__name__)

_DEFAULT_RUBRIC_FILE = (
    Path(__file__).parent.parent.parent.parent
    / "data"
    / "rubric"
    / "ielts_task2_band_descriptors.jsonl"
)


def _load_jsonl_chunks(rubric_path: Path | None = None) -> list[RubricChunk]:
    """Load rubric chunks from jsonl file."""
    path = rubric_path or _DEFAULT_RUBRIC_FILE
    chunks: list[RubricChunk] = []
    if not path.exists():
        logger.warning("Rubric file not found: %s", path)
        return chunks

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                chunks.append(RubricChunk.model_validate(data))
    return chunks


def search_rubric_mock(
    criterion: Criterion,
    query: str,
    top_k: int = 3,
    rubric_path: Path | None = None,
) -> list[RubricChunk]:
    """In-memory keyword search over rubric jsonl fallback for tests/CI."""
    chunks = _load_jsonl_chunks(rubric_path)
    filtered = [c for c in chunks if c.criterion == criterion]
    if not filtered:
        # Fallback to any chunk for that criterion or generic placeholder
        return [
            RubricChunk(
                criterion=criterion,
                band=7,
                text=f"Sample mock descriptor for {criterion.value} band 7.",
                source="MOCK_FALLBACK",
            )
        ]

    # Keyword match scoring
    query_words = set(query.lower().split())
    scored = []
    for c in filtered:
        text_words = set(c.text.lower().split())
        score = len(query_words.intersection(text_words))
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:top_k]]


def search_rubric(
    criterion: Criterion,
    query: str,
    top_k: int = 3,
) -> list[RubricChunk]:
    """Search rubric descriptors by criterion and query.

    Uses in-memory keyword matching if USE_MOCK_RAG=true (default),
    otherwise queries ChromaDB.

    # TODO(B2): Implement ChromaDB querying when USE_MOCK_RAG=false.
    """
    settings = get_settings()
    if settings.use_mock_rag:
        return search_rubric_mock(criterion, query, top_k=top_k)

    # TODO(B2): ChromaDB query implementation
    try:
        import chromadb

        client = chromadb.PersistentClient(path=settings.chroma_dir)
        collection = client.get_or_create_collection("ielts_rubric")
        results: Any = collection.query(
            query_texts=[query],
            n_results=top_k,
            where={"criterion": criterion.value},
        )
        chunks: list[RubricChunk] = []
        if results and "documents" in results and results["documents"]:
            for doc, meta in zip(results["documents"][0], results["metadatas"][0], strict=False):
                chunks.append(
                    RubricChunk(
                        criterion=Criterion(meta["criterion"]),
                        band=int(meta["band"]),
                        text=doc,
                        source=str(meta.get("source", "ChromaDB")),
                    )
                )
        return chunks if chunks else search_rubric_mock(criterion, query, top_k=top_k)
    except Exception as exc:
        logger.warning("ChromaDB search failed, falling back to mock search: %s", exc)
        return search_rubric_mock(criterion, query, top_k=top_k)
