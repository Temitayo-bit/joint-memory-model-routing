from __future__ import annotations

import unittest

from experiments.text_baseline.constants import TOP_K_EVIDENCE
from experiments.text_baseline.fixtures import DATA_DIR, load_memory, load_questions
from experiments.text_baseline.retrieval import (
    rank_all_lexical,
    retrieve_for_condition,
    v1_plainto_and_lexical_rank,
)


class RetrievalV2HistoricalTests(unittest.TestCase):
    """Historical pilot_hybrid_v2 (no stopwords) checks retained for regression context."""

    def setUp(self) -> None:
        self.questions = {q["id"]: q for q in load_questions(DATA_DIR)}
        self.memory = load_memory(DATA_DIR)

    def test_v2_without_stopwords_still_non_zero_lexical(self) -> None:
        q09 = self.questions["Q09"]["text"]
        ranked = rank_all_lexical(q09, self.memory["items"], apply_stopwords=False)
        self.assertTrue(all(row["v1_and_rank"] == 0.0 for row in ranked))
        self.assertTrue(any(row["lexical_rank"] > 0.0 for row in ranked))
        m05 = next(row for row in ranked if row["id"] == "M05")
        self.assertGreater(m05["lexical_rank"], 0.0)

    def test_q09_hybrid_recovers_when_vector_alone_ranks_m05_fifth(self) -> None:
        """Reproduce the observed v1 failure mode: M05 fifth by vector, top-k=4."""
        items = self.memory["items"]
        vector_scores = {item["id"]: 0.10 for item in items}
        for item_id, score in (
            ("M03", 0.800),
            ("M07", 0.795),
            ("P05", 0.790),
            ("M02", 0.785),
            ("M05", 0.780),
        ):
            vector_scores[item_id] = score

        vector_order = sorted(
            ((vector_scores[item["id"]], item["id"]) for item in items),
            key=lambda row: (-row[0], row[1]),
        )
        self.assertEqual([row[1] for row in vector_order[:4]], ["M03", "M07", "P05", "M02"])
        self.assertEqual(vector_order[4][1], "M05")

        hybrid = retrieve_for_condition(
            "S1",
            self.questions["Q09"]["text"],
            self.memory,
            vector_similarity_by_id=vector_scores,
        )
        hybrid_ids = [item["id"] for item in hybrid]
        self.assertIn("M05", hybrid_ids)
        self.assertEqual(len(hybrid_ids), TOP_K_EVIDENCE)
        m05 = next(item for item in hybrid if item["id"] == "M05")
        self.assertGreater(m05["lexical_rank"], 0.0)
        self.assertEqual(m05["vector_similarity"], 0.780)

    def test_v1_and_simulator_matches_empty_subset_expectation(self) -> None:
        short = "Python harness"
        long_q = self.questions["Q09"]["text"]
        doc = "The local experiment harness for this project is written in Python."
        self.assertEqual(v1_plainto_and_lexical_rank(long_q, doc), 0.0)
        self.assertEqual(v1_plainto_and_lexical_rank(short, doc), 1.0)


if __name__ == "__main__":
    unittest.main()
