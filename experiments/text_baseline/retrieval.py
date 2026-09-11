"""Lexical fixture retrieval.

This is plumbing validation for the harness, not the semantic retrieval system
that later experiments will measure.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Sequence

from experiments.text_baseline.constants import MEMORY_CONDITIONS, NO_MEMORY_CONDITIONS, TOP_K_EVIDENCE
from experiments.text_baseline.hashing import sha256_json

_TOKEN = re.compile(r"[a-z0-9]+")


class RetrievalError(ValueError):
    """Invalid condition or fixture input for retrieval."""


def tokenize(text: str) -> List[str]:
    return _TOKEN.findall(text.lower())


def lexical_overlap(query: str, document: str) -> float:
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return 0.0
    document_tokens = set(tokenize(document))
    return len(query_tokens & document_tokens) / float(len(query_tokens))


def _rank_items(question_text: str, items: Sequence[Mapping[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    ranked = []
    for item in items:
        score = lexical_overlap(question_text, str(item["content"]))
        ranked.append(
            {
                "id": item["id"],
                "kind": item["kind"],
                "content": item["content"],
                "lexical_overlap": score,
            }
        )
    ranked.sort(key=lambda row: (-row["lexical_overlap"], row["id"]))
    selected = ranked[:top_k]
    return selected


def retrieve_for_condition(
    condition: str,
    question_text: str,
    memory: Mapping[str, Any],
    top_k: int = TOP_K_EVIDENCE,
) -> List[Dict[str, Any]]:
    if condition in NO_MEMORY_CONDITIONS:
        return []
    if condition not in MEMORY_CONDITIONS:
        raise RetrievalError("unknown condition")
    items = memory["items"]
    return _rank_items(question_text, items, top_k)


def evidence_payload(evidence: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "retriever": "lexical_fixture_plumbing",
        "not_semantic_retrieval": True,
        "items": [
            {"id": item["id"], "kind": item["kind"], "content": item["content"]}
            for item in evidence
        ],
    }


def evidence_hash(evidence: Sequence[Mapping[str, Any]]) -> str:
    return sha256_json(evidence_payload(evidence))
