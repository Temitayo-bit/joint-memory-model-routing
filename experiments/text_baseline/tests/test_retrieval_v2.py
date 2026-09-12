from __future__ import annotations

import unittest

from experiments.text_baseline.constants import RETRIEVAL_CONFIG, RETRIEVER_VERSION, TOP_K_EVIDENCE
from experiments.text_baseline.fixtures import DATA_DIR, load_memory, load_questions
from experiments.text_baseline.retrieval import (
    rank_all_lexical,
    retrieve_for_condition,
    v1_plainto_and_lexical_rank,
)
from experiments.text_baseline.run_builder import build_requests


class RetrievalV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.questions = {q["id"]: q for q in load_questions(DATA_DIR)}
        self.memory = load_memory(DATA_DIR)

    def test_full_question_lexical_no_longer_collapses_to_zero(self) -> None:
        q09 = self.questions["Q09"]["text"]
        ranked = rank_all_lexical(q09, self.memory["items"])
        self.assertTrue(all(row["v1_and_rank"] == 0.0 for row in ranked))
        self.assertTrue(any(row["lexical_rank"] > 0.0 for row in ranked))
        m05 = next(row for row in ranked if row["id"] == "M05")
        self.assertGreater(m05["lexical_rank"], 0.0)

    def test_q09_python_harness_fact_in_top_k_evidence(self) -> None:
        evidence = retrieve_for_condition("S1", self.questions["Q09"]["text"], self.memory)
        ids = [item["id"] for item in evidence]
        self.assertEqual(len(evidence), TOP_K_EVIDENCE)
        self.assertIn("M05", ids)
        self.assertTrue(
            any("written in Python" in item["content"] for item in evidence),
        )

    def test_q09_hybrid_recovers_when_vector_alone_ranks_m05_fifth(self) -> None:
        """Reproduce the observed v1 failure mode: M05 fifth by vector, top-k=4."""
        items = self.memory["items"]
        # Low-lexical distractors beat M05 on vector alone; M05 is fifth.
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

    def test_memory_questions_retain_expected_coverage(self) -> None:
        expectations = {
            "Q01": {"M01"},
            "Q02": {"M02"},
            "Q03": {"M03"},
            "Q04": {"M04"},
            "Q10": {"M06"},
        }
        for question_id, required in expectations.items():
            evidence = retrieve_for_condition(
                "S1",
                self.questions[question_id]["text"],
                self.memory,
            )
            ids = {item["id"] for item in evidence}
            self.assertTrue(
                required.issubset(ids),
                msg="%s missing %s from %s" % (question_id, required - ids, ids),
            )

    def test_manifest_records_retriever_version_and_limit(self) -> None:
        bundle = build_requests(DATA_DIR, repeats=1, seed=0)
        retrieval = bundle["manifest"]["retrieval"]
        self.assertEqual(retrieval["retriever"], RETRIEVER_VERSION)
        self.assertEqual(retrieval["limit"], TOP_K_EVIDENCE)
        self.assertEqual(retrieval, RETRIEVAL_CONFIG)

    def test_v1_and_simulator_matches_empty_subset_expectation(self) -> None:
        short = "Python harness"
        long_q = self.questions["Q09"]["text"]
        doc = "The local experiment harness for this project is written in Python."
        self.assertEqual(v1_plainto_and_lexical_rank(long_q, doc), 0.0)
        self.assertEqual(v1_plainto_and_lexical_rank(short, doc), 1.0)


if __name__ == "__main__":
    unittest.main()
