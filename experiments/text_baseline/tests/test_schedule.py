from __future__ import annotations

import unittest

from experiments.text_baseline.fixtures import DATA_DIR
from experiments.text_baseline.schedule import ScheduleError, build_cells
from experiments.text_baseline.run_builder import build_requests
from experiments.text_baseline.fixtures import load_questions


class ScheduleTests(unittest.TestCase):
    def test_same_seed_same_order(self) -> None:
        first = build_requests(DATA_DIR, repeats=1, seed=17)
        second = build_requests(DATA_DIR, repeats=1, seed=17)
        self.assertEqual(first["manifest"]["schedule_sha256"], second["manifest"]["schedule_sha256"])
        self.assertEqual(
            [row["request_sha256"] for row in first["requests"]],
            [row["request_sha256"] for row in second["requests"]],
        )

    def test_different_seeds_change_order(self) -> None:
        first = build_cells(load_questions(DATA_DIR), repeats=1, seed=1)
        second = build_cells(load_questions(DATA_DIR), repeats=1, seed=2)
        self.assertNotEqual(
            [(row["question_id"], row["condition"]) for row in first],
            [(row["question_id"], row["condition"]) for row in second],
        )

    def test_rejects_unbounded_repeats(self) -> None:
        with self.assertRaises(ScheduleError):
            build_cells(load_questions(DATA_DIR), repeats=6, seed=0)


if __name__ == "__main__":
    unittest.main()
