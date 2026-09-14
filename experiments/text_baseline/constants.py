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
BENCHMARK_V2_STRATA: Tuple[str, ...] = ("A", "B", "C", "D")
BENCHMARK_V2_GENERATION_SEEDS: Tuple[int, ...] = (42, 43, 44)
BENCHMARK_V2_DIAGNOSTIC_TAGS: FrozenSet[str] = frozenset(
    {
        "direct extraction",
        "multi-record composition",
        "temporal update",
        "conflict resolution",
        "constraint or arithmetic reasoning",
        "distractor resistance",
        "unsupported-information abstention",
    }
)
LEGACY_DATASET_ID = "synthetic-northriver-pilot-v1"
LEGACY_QUESTION_COUNT = 12
LEGACY_PER_CATEGORY = 4
MAX_REPEATS = 5
TOP_K_EVIDENCE = 4
RETRIEVAL_LIMIT_CAP = 8
EMBEDDING_DIMS = 384
NORM_TOLERANCE = 1e-3
CANONICAL_JSON_SEPARATORS = (",", ":")
MAX_REQUIRED_EVIDENCE_IDS = 2

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

# Fixed English stopword set derived from PostgreSQL 17 Snowball english.stop
# (REL_17_STABLE: src/backend/snowball/stopwords/english.stop). Applied before
# query/document token sets and document frequencies in pilot_hybrid_v2_1.
ENGLISH_STOPWORDS: FrozenSet[str] = frozenset(
    (
        "a",
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "did",
        "do",
        "does",
        "doing",
        "don",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "has",
        "have",
        "having",
        "he",
        "her",
        "here",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "itself",
        "just",
        "me",
        "more",
        "most",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "now",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "s",
        "same",
        "she",
        "should",
        "so",
        "some",
        "such",
        "t",
        "than",
        "that",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
    )
)
STOPWORD_SET_ID = "postgresql_17_english_snowball"
STOPWORD_SOURCE = (
    "https://raw.githubusercontent.com/postgres/postgres/REL_17_STABLE/"
    "src/backend/snowball/stopwords/english.stop"
)
STOPWORD_COUNT = len(ENGLISH_STOPWORDS)

# pilot_hybrid_v2_1 — must stay aligned with retrieve_pilot_memory migration + Edge evidence.
RETRIEVER_VERSION = "pilot_hybrid_v2_1"
RETRIEVAL_CONFIG: Dict[str, Any] = {
    "retriever": RETRIEVER_VERSION,
    "lexical": "snapshot_idf_token_overlap",
    "vector": "cosine_similarity_1_minus_distance",
    "combined": "lexical_rank_plus_vector_similarity",
    "limit": TOP_K_EVIDENCE,
    "limit_cap": RETRIEVAL_LIMIT_CAP,
    "token_pattern": "[A-Za-z0-9]+",
    "idf": "ln((N+1)/(df+1))+1",
    "stopwords": STOPWORD_SET_ID,
    "stopword_count": STOPWORD_COUNT,
    "stopword_source": STOPWORD_SOURCE,
    "not_semantic_retrieval": True,
}

if STOPWORD_COUNT != 127:  # pragma: no cover - constant integrity
    raise RuntimeError("ENGLISH_STOPWORDS must remain the 127-word PostgreSQL 17 list")
