"""Shared identifiers for the four fixed text baselines."""

from typing import Any, Dict, FrozenSet, Tuple

CONDITIONS: Tuple[str, ...] = ("S0", "S1", "L0", "L1")
MEMORY_CONDITIONS: FrozenSet[str] = frozenset({"S1", "L1"})
NO_MEMORY_CONDITIONS: FrozenSet[str] = frozenset({"S0", "L0"})
QUESTION_CATEGORIES: Tuple[str, ...] = (
    "memory_answerable",
    "general_knowledge",
    "memory_and_general",
)
MAX_REPEATS = 5
TOP_K_EVIDENCE = 4
RETRIEVAL_LIMIT_CAP = 8
EMBEDDING_DIMS = 384
NORM_TOLERANCE = 1e-3
CANONICAL_JSON_SEPARATORS = (",", ":")

# Matches supabase/functions/text-baseline-pilot/constants.ts FIXED_GENERATION.
FIXED_GENERATION: Dict[str, Any] = {
    "stream": False,
    "max_tokens": 256,
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "min_p": 0,
    "seed": 42,
    "chat_template_kwargs": {"enable_thinking": False},
}

# pilot_hybrid_v2 — must stay aligned with retrieve_pilot_memory migration + Edge evidence.
RETRIEVER_VERSION = "pilot_hybrid_v2"
RETRIEVAL_CONFIG: Dict[str, Any] = {
    "retriever": RETRIEVER_VERSION,
    "lexical": "snapshot_idf_token_overlap",
    "vector": "cosine_similarity_1_minus_distance",
    "combined": "lexical_rank_plus_vector_similarity",
    "limit": TOP_K_EVIDENCE,
    "limit_cap": RETRIEVAL_LIMIT_CAP,
    "token_pattern": "[A-Za-z0-9]+",
    "idf": "ln((N+1)/(df+1))+1",
    "not_semantic_retrieval": True,
}
