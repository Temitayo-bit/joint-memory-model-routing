from __future__ import annotations

import unittest
from collections import Counter

from experiments.text_baseline.constants import CONDITIONS, FIXED_GENERATION
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

    def test_exported_manifest_includes_fixed_generation_with_min_p(self) -> None:
        bundle = build_requests(DATA_DIR, repeats=1, seed=0)
        generation = bundle["manifest"]["fixed_generation"]
        self.assertEqual(generation, FIXED_GENERATION)
        self.assertEqual(generation["min_p"], 0)
        self.assertEqual(generation["temperature"], 0.7)
        self.assertEqual(generation["top_p"], 0.8)
        self.assertEqual(generation["top_k"], 20)
        self.assertEqual(generation["seed"], 42)
        self.assertEqual(generation["chat_template_kwargs"], {"enable_thinking": False})


if __name__ == "__main__":
    unittest.main()
