"""Offline all-MiniLM-L6-v2 embedding bundle generator. Does not write to Supabase."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from experiments.text_baseline.constants import EMBEDDING_DIMS, NORM_TOLERANCE
from experiments.text_baseline.fixtures import DATA_DIR, load_memory, load_questions
from experiments.text_baseline.hashing import sha256_json
from experiments.text_baseline.live_client import LiveClientError, validate_embedding

DEFAULT_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
EncodeFn = Callable[[Sequence[str]], Sequence[Sequence[float]]]


class EmbeddingError(RuntimeError):
    """Embedding generation failure."""


def l2_normalize(values: Sequence[float]) -> List[float]:
    norm = math.sqrt(sum(component * component for component in values))
    if norm <= 0.0:
        raise EmbeddingError("cannot normalize a zero vector")
    return [float(component) / norm for component in values]


def validate_unit_embedding(values: Sequence[Any]) -> List[float]:
    try:
        return validate_embedding(values)
    except LiveClientError as exc:
        raise EmbeddingError(str(exc)) from exc


def default_sentence_transformer_encoder(model_id: str = DEFAULT_MODEL_ID) -> EncodeFn:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise EmbeddingError(
            "sentence-transformers is required for real embeddings; "
            "install it locally or pass encode_fn for offline tests"
        ) from exc

    model = SentenceTransformer(model_id)

    def _encode(texts: Sequence[str]) -> Sequence[Sequence[float]]:
        vectors = model.encode(list(texts), normalize_embeddings=True)
        return [list(map(float, row)) for row in vectors]

    return _encode


def build_embedding_bundle(
    data_dir: Path = DATA_DIR,
    *,
    encode_fn: Optional[EncodeFn] = None,
    model_id: str = DEFAULT_MODEL_ID,
) -> Dict[str, Any]:
    memory = load_memory(data_dir)
    questions = load_questions(data_dir)
    encoder = encode_fn or default_sentence_transformer_encoder(model_id)
    item_texts = [str(item["content"]) for item in memory["items"]]
    question_texts = [str(question["text"]) for question in questions]
    item_vectors = list(encoder(item_texts))
    question_vectors = list(encoder(question_texts))
    if len(item_vectors) != len(item_texts) or len(question_vectors) != len(question_texts):
        raise EmbeddingError("encoder returned the wrong number of vectors")
    def _unit(vector: Sequence[float]) -> List[float]:
        norm = math.sqrt(sum(component * component for component in vector))
        if abs(norm - 1.0) > NORM_TOLERANCE:
            return validate_unit_embedding(l2_normalize(vector))
        return validate_unit_embedding(vector)

    items = []
    for item, vector in zip(memory["items"], item_vectors):
        items.append(
            {
                "id": item["id"],
                "kind": item["kind"],
                "content": item["content"],
                "embedding": _unit(vector),
            }
        )
    question_rows = []
    for question, vector in zip(questions, question_vectors):
        question_rows.append(
            {
                "id": question["id"],
                "text": question["text"],
                "category": question["category"],
                "embedding": _unit(vector),
            }
        )
    bundle = {
        "not_a_research_result": True,
        "model_id": model_id,
        "dims": EMBEDDING_DIMS,
        "normalized": True,
        "memory_sha256": sha256_json(memory),
        "questions_sha256": sha256_json({"questions": questions}),
        "items": items,
        "questions": question_rows,
        "note": (
            "Local JSON bundle for Codex to load into Supabase later. "
            "This generator does not write to Supabase."
        ),
    }
    bundle["bundle_sha256"] = sha256_json(
        {
            "model_id": model_id,
            "dims": EMBEDDING_DIMS,
            "items": [{"id": row["id"], "embedding": row["embedding"]} for row in items],
            "questions": [{"id": row["id"], "embedding": row["embedding"]} for row in question_rows],
        }
    )
    return bundle
