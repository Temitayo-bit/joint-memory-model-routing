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
