"""Hybrid fixture retrieval (pilot_hybrid_v2_1).

Local harness uses the same snapshot-local IDF token overlap as
``retrieve_pilot_memory`` for lexical ranks, including the fixed PostgreSQL 17
English Snowball stopword filter. Vectors are not applied locally unless a
caller supplies similarities for hybrid tests; this remains plumbing
validation, not the measured semantic retrieval system.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

from experiments.text_baseline.constants import (
    ENGLISH_STOPWORDS,
    MEMORY_CONDITIONS,
    NO_MEMORY_CONDITIONS,
    RETRIEVAL_CONFIG,
    TOP_K_EVIDENCE,
)

_TOKEN = re.compile(r"[a-z0-9]+")


class RetrievalError(ValueError):
    """Invalid condition or fixture input for retrieval."""


def tokenize(text: str, *, apply_stopwords: bool = True) -> List[str]:
    tokens = _TOKEN.findall(text.lower())
    if apply_stopwords:
        return [token for token in tokens if token not in ENGLISH_STOPWORDS]
    return tokens


def token_set(text: str, *, apply_stopwords: bool = True) -> Set[str]:
    return set(tokenize(text, apply_stopwords=apply_stopwords))


def document_frequencies(
    documents: Sequence[str],
    *,
    apply_stopwords: bool = True,
) -> Counter:
    df: Counter = Counter()
    for document in documents:
        for token in token_set(document, apply_stopwords=apply_stopwords):
            df[token] += 1
    return df


def idf_weight(token: str, df: Mapping[str, float], n_docs: int) -> float:
    return math.log((n_docs + 1.0) / (float(df.get(token, 0)) + 1.0)) + 1.0


def snapshot_idf_lexical_rank(
    query: str,
    document: str,
    df: Mapping[str, float],
    n_docs: int,
    *,
    apply_stopwords: bool = True,
) -> float:
    """Fraction of query IDF mass overlapping the document (v2.1 lexical term)."""
    query_tokens = token_set(query, apply_stopwords=apply_stopwords)
    if not query_tokens or n_docs <= 0:
        return 0.0
    denom = sum(idf_weight(token, df, n_docs) for token in query_tokens)
    if denom <= 0.0:
        return 0.0
    doc_tokens = token_set(document, apply_stopwords=apply_stopwords)
    numer = sum(idf_weight(token, df, n_docs) for token in query_tokens if token in doc_tokens)
    return numer / denom


def v1_plainto_and_lexical_rank(query: str, document: str) -> float:
    """Simulate v1 plainto_tsquery AND collapse: non-zero only if every query token appears."""
    query_tokens = token_set(query, apply_stopwords=False)
    if not query_tokens:
        return 0.0
    doc_tokens = token_set(document, apply_stopwords=False)
    if query_tokens.issubset(doc_tokens):
        return 1.0
    return 0.0


def _rank_items(
    question_text: str,
    items: Sequence[Mapping[str, Any]],
    top_k: int,
    vector_similarity_by_id: Optional[Mapping[str, float]] = None,
) -> List[Dict[str, Any]]:
    documents = [str(item["content"]) for item in items]
    n_docs = len(documents)
    df = document_frequencies(documents)
    ranked: List[Dict[str, Any]] = []
    for item in items:
        lexical = snapshot_idf_lexical_rank(question_text, str(item["content"]), df, n_docs)
        vector = 0.0
        if vector_similarity_by_id is not None:
            vector = float(vector_similarity_by_id.get(str(item["id"]), 0.0))
        combined = lexical + vector
        ranked.append(
            {
                "id": item["id"],
                "kind": item["kind"],
                "content": item["content"],
                "lexical_rank": lexical,
                "vector_similarity": vector,
                "combined_score": combined,
            }
        )
    ranked.sort(key=lambda row: (-row["combined_score"], row["id"]))
    return ranked[:top_k]


def retrieve_for_condition(
    condition: str,
    question_text: str,
    memory: Mapping[str, Any],
    top_k: int = TOP_K_EVIDENCE,
    vector_similarity_by_id: Optional[Mapping[str, float]] = None,
) -> List[Dict[str, Any]]:
    if condition in NO_MEMORY_CONDITIONS:
        return []
    if condition not in MEMORY_CONDITIONS:
        raise RetrievalError("unknown condition")
    items = memory["items"]
    return _rank_items(question_text, items, top_k, vector_similarity_by_id)


def evidence_payload(evidence: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    payload = dict(RETRIEVAL_CONFIG)
    payload["items"] = [
        {"id": item["id"], "kind": item["kind"], "content": item["content"]}
        for item in evidence
    ]
    return payload


def evidence_hash(evidence: Sequence[Mapping[str, Any]]) -> str:
    from experiments.text_baseline.hashing import sha256_json

    return sha256_json(evidence_payload(evidence))


def rank_all_lexical(
    question_text: str,
    items: Sequence[Mapping[str, Any]],
    *,
    apply_stopwords: bool = True,
) -> List[Dict[str, Any]]:
    """Full lexical ranking for tests (no top-k cut)."""
    documents = [str(item["content"]) for item in items]
    n_docs = len(documents)
    df = document_frequencies(documents, apply_stopwords=apply_stopwords)
    ranked = []
    for item in items:
        lexical = snapshot_idf_lexical_rank(
            question_text,
            str(item["content"]),
            df,
            n_docs,
            apply_stopwords=apply_stopwords,
        )
        ranked.append(
            {
                "id": item["id"],
                "kind": item["kind"],
                "content": item["content"],
                "lexical_rank": lexical,
                "v1_and_rank": v1_plainto_and_lexical_rank(question_text, str(item["content"])),
            }
        )
    ranked.sort(key=lambda row: (-row["lexical_rank"], row["id"]))
    return ranked


def rank_all_hybrid(
    question_text: str,
    items: Sequence[Mapping[str, Any]],
    vector_similarity_by_id: Mapping[str, float],
    *,
    apply_stopwords: bool = True,
) -> List[Dict[str, Any]]:
    """Full hybrid ranking for tests (no top-k cut).

    Set ``apply_stopwords=False`` to reproduce historical pilot_hybrid_v2
    lexical ranks without the v2.1 English Snowball filter.
    """
    documents = [str(item["content"]) for item in items]
    n_docs = len(documents)
    df = document_frequencies(documents, apply_stopwords=apply_stopwords)
    ranked: List[Dict[str, Any]] = []
    for item in items:
        item_id = str(item["id"])
        lexical = snapshot_idf_lexical_rank(
            question_text,
            str(item["content"]),
            df,
            n_docs,
            apply_stopwords=apply_stopwords,
        )
        vector = float(vector_similarity_by_id.get(item_id, 0.0))
        ranked.append(
            {
                "id": item_id,
                "kind": item["kind"],
                "content": item["content"],
                "lexical_rank": lexical,
                "vector_similarity": vector,
                "combined_score": lexical + vector,
            }
        )
    ranked.sort(key=lambda row: (-row["combined_score"], row["id"]))
    return ranked
