from __future__ import annotations

import unittest
from collections import Counter

from experiments.text_baseline.constants import CONDITIONS
from experiments.text_baseline.fixtures import DATA_DIR, load_questions
from experiments.text_baseline.run_builder import build_requests
from experiments.text_baseline.schedule import expected_cell_count


class CoverageTests(unittest.TestCase):
    def test_twelve_questions_and_four_conditions(self) -> None:
        bundle = build_requests(DATA_DIR, repeats=1, seed=0)
        self.assertEqual(len(load_questions(DATA_DIR)), 12)
        self.assertEqual(bundle["manifest"]["cell_count"], 48)
        self.assertEqual(bundle["manifest"]["expected_cell_count"], expected_cell_count(1))
        pairs = {(row["question_id"], row["condition"]) for row in bundle["requests"]}
        question_ids = {question["id"] for question in load_questions(DATA_DIR)}
        expected = {(qid, condition) for qid in question_ids for condition in CONDITIONS}
        self.assertEqual(pairs, expected)

    def test_two_repeats_are_bounded_and_complete(self) -> None:
        bundle = build_requests(DATA_DIR, repeats=2, seed=3)
        self.assertEqual(len(bundle["requests"]), 96)
        counts = Counter((row["question_id"], row["condition"]) for row in bundle["requests"])
        self.assertTrue(all(value == 2 for value in counts.values()))


if __name__ == "__main__":
    unittest.main()
