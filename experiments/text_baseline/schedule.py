"""Deterministic schedules with bounded repeats and seeded shuffle."""

from __future__ import annotations

import random
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from experiments.text_baseline.constants import CONDITIONS, MAX_REPEATS
from experiments.text_baseline.hashing import sha256_json


class ScheduleError(ValueError):
    """Invalid repeat count or schedule input."""


def build_cells(
    questions: Sequence[Mapping[str, Any]],
    repeats: int = 1,
    seed: int = 0,
    generation_seeds: Optional[Sequence[int]] = None,
) -> List[Dict[str, Any]]:
    if repeats < 1 or repeats > MAX_REPEATS:
        raise ScheduleError("repeats must be between 1 and %s" % MAX_REPEATS)
    if generation_seeds is None:
        # Legacy pilot: exactly twelve questions and no generation-seed dimension.
        if len(questions) != 12:
            raise ScheduleError("schedule requires exactly 12 questions")
        seed_values: Tuple[Optional[int], ...] = (None,)
    else:
        if not generation_seeds:
            raise ScheduleError("generation_seeds must be a non-empty sequence when provided")
        seed_values = tuple(int(value) for value in generation_seeds)
        if len(set(seed_values)) != len(seed_values):
            raise ScheduleError("generation_seeds must be unique")
    cells: List[Dict[str, Any]] = []
    for repeat_index in range(repeats):
        for question in questions:
            category = question.get("category")
            if category is None and "stratum" in question:
                category = question["stratum"]
            for condition in CONDITIONS:
                for generation_seed in seed_values:
                    cell: Dict[str, Any] = {
                        "repeat_index": repeat_index,
                        "question_id": question["id"],
                        "question_text": question["text"],
                        "question_category": category,
                        "condition": condition,
                    }
                    if "stratum" in question:
                        cell["question_stratum"] = question["stratum"]
                    if generation_seed is not None:
                        cell["generation_seed"] = generation_seed
                    cells.append(cell)
    rng = random.Random(seed)
    rng.shuffle(cells)
    return cells


def expected_cell_count(
    repeats: int = 1,
    *,
    question_count: int = 12,
    generation_seed_count: int = 1,
) -> int:
    if question_count < 1:
        raise ScheduleError("question_count must be >= 1")
    if repeats < 1 or repeats > MAX_REPEATS:
        raise ScheduleError("repeats must be between 1 and %s" % MAX_REPEATS)
    if generation_seed_count < 1:
        raise ScheduleError("generation_seed_count must be >= 1")
    return question_count * len(CONDITIONS) * generation_seed_count * repeats


def schedule_hash(cells: Sequence[Mapping[str, Any]]) -> str:
    compact = []
    for cell in cells:
        row: Dict[str, Any] = {
            "repeat_index": cell["repeat_index"],
            "question_id": cell["question_id"],
            "condition": cell["condition"],
        }
        if "generation_seed" in cell:
            row["generation_seed"] = cell["generation_seed"]
        compact.append(row)
    return sha256_json(compact)
