"""Shared identifiers for the four fixed text baselines."""

from typing import FrozenSet, Tuple

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
