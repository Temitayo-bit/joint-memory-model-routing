"""Deterministic 48-cell schedules with bounded repeats and seeded shuffle."""

from __future__ import annotations

import random
from typing import Any, Dict, List, Mapping, Sequence

from experiments.text_baseline.constants import CONDITIONS, MAX_REPEATS
from experiments.text_baseline.hashing import sha256_json


class ScheduleError(ValueError):
    """Invalid repeat count or schedule input."""


def build_cells(
    questions: Sequence[Mapping[str, Any]],
    repeats: int = 1,
    seed: int = 0,
) -> List[Dict[str, Any]]:
    if repeats < 1 or repeats > MAX_REPEATS:
        raise ScheduleError("repeats must be between 1 and %s" % MAX_REPEATS)
    if len(questions) != 12:
        raise ScheduleError("schedule requires exactly 12 questions")
    cells: List[Dict[str, Any]] = []
    for repeat_index in range(repeats):
        for question in questions:
            for condition in CONDITIONS:
                cells.append(
                    {
                        "repeat_index": repeat_index,
                        "question_id": question["id"],
                        "question_text": question["text"],
                        "question_category": question["category"],
                        "condition": condition,
                    }
                )
    rng = random.Random(seed)
    rng.shuffle(cells)
    return cells


def expected_cell_count(repeats: int) -> int:
    return 12 * len(CONDITIONS) * repeats


def schedule_hash(cells: Sequence[Mapping[str, Any]]) -> str:
    compact = [
        {
            "repeat_index": cell["repeat_index"],
            "question_id": cell["question_id"],
            "condition": cell["condition"],
        }
        for cell in cells
    ]
    return sha256_json(compact)
