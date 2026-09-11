"""Laptop coordinator for one supervised live text request. Does not deploy or call models."""

from __future__ import annotations

import math
import uuid
from typing import Any, Dict, List, Mapping, Optional, Sequence

from experiments.text_baseline.constants import CONDITIONS, EMBEDDING_DIMS, MEMORY_CONDITIONS, NORM_TOLERANCE

ALLOWED_BODY_KEYS = frozenset({"request_id", "snapshot_id", "question", "condition", "embedding"})
REJECTED_CLIENT_KEYS = frozenset(
    {
        "model_url",
        "base_url",
        "model",
        "model_id",
        "temperature",
        "top_p",
        "top_k",
        "seed",
        "max_tokens",
        "prompt",
        "messages",
        "owner_id",
        "reference_answer",
        "expected_answer",
        "bearer",
        "authorization",
        "revision",
        "quantization",
    }
)


class LiveClientError(ValueError):
    """Invalid live-path payload."""


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return False
    return True


def validate_embedding(values: Sequence[Any]) -> List[float]:
    if len(values) != EMBEDDING_DIMS:
        raise LiveClientError("embedding must have %s dimensions" % EMBEDDING_DIMS)
    floats: List[float] = []
    for item in values:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise LiveClientError("embedding values must be finite numbers")
        number = float(item)
        if not math.isfinite(number):
            raise LiveClientError("embedding values must be finite numbers")
        floats.append(number)
    norm = math.sqrt(sum(component * component for component in floats))
    if abs(norm - 1.0) > NORM_TOLERANCE:
        raise LiveClientError("embedding must be L2-normalized")
    return floats


def build_live_request(
    request_id: str,
    snapshot_id: str,
    question: str,
    condition: str,
    embedding: Optional[Sequence[Any]] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if extra:
        banned = REJECTED_CLIENT_KEYS.intersection(extra.keys()) | (
            set(extra.keys()) - ALLOWED_BODY_KEYS
        )
        if banned:
            raise LiveClientError("client must not send %s" % sorted(banned))
    if not _is_uuid(request_id) or not _is_uuid(snapshot_id):
        raise LiveClientError("request_id and snapshot_id must be UUIDs")
    if not question or not isinstance(question, str) or not question.strip():
        raise LiveClientError("question is required")
    if condition not in CONDITIONS:
        raise LiveClientError("condition must be S0, S1, L0, or L1")
    body: Dict[str, Any] = {
        "request_id": str(request_id),
        "snapshot_id": str(snapshot_id),
        "question": question.strip(),
        "condition": condition,
    }
    if condition in MEMORY_CONDITIONS:
        if embedding is None:
            raise LiveClientError("memory conditions require a 384-d unit embedding")
        body["embedding"] = validate_embedding(embedding)
    elif embedding is not None:
        raise LiveClientError("no-memory conditions must not include an embedding")
    return body
