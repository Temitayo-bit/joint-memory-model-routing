from __future__ import annotations

import json
import unittest
from pathlib import Path

from experiments.text_baseline.constants import (
    ENGLISH_STOPWORDS,
    RETRIEVAL_CONFIG,
    RETRIEVER_VERSION,
    STOPWORD_COUNT,
    STOPWORD_SET_ID,
    TOP_K_EVIDENCE,
)
from experiments.text_baseline.fixtures import DATA_DIR, load_memory, load_questions
from experiments.text_baseline.retrieval import (
    rank_all_hybrid,
    rank_all_lexical,
    retrieve_for_condition,
    v1_plainto_and_lexical_rank,
)
from experiments.text_baseline.run_builder import build_requests

Q09_SIMILARITIES = DATA_DIR / "q09_minilm_similarities.json"


class RetrievalV21Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.questions = {q["id"]: q for q in load_questions(DATA_DIR)}
        self.memory = load_memory(DATA_DIR)
        self.q09_sims = json.loads(Q09_SIMILARITIES.read_text(encoding="utf-8"))

    def test_stopword_set_is_postgresql_17_english_snowball(self) -> None:
        self.assertEqual(STOPWORD_COUNT, 127)
        self.assertEqual(len(ENGLISH_STOPWORDS), 127)
        self.assertEqual(RETRIEVAL_CONFIG["stopwords"], STOPWORD_SET_ID)
        self.assertEqual(RETRIEVAL_CONFIG["stopword_count"], 127)
        self.assertIn("REL_17_STABLE", RETRIEVAL_CONFIG["stopword_source"])
        self.assertIn("english.stop", RETRIEVAL_CONFIG["stopword_source"])

    def test_full_question_lexical_no_longer_collapses_to_zero(self) -> None:
        q09 = self.questions["Q09"]["text"]
        ranked = rank_all_lexical(q09, self.memory["items"])
        self.assertTrue(all(row["v1_and_rank"] == 0.0 for row in ranked))
        self.assertTrue(any(row["lexical_rank"] > 0.0 for row in ranked))
        m05 = next(row for row in ranked if row["id"] == "M05")
        self.assertGreater(m05["lexical_rank"], 0.0)

    def test_q09_python_harness_fact_in_top_k_evidence_lexical(self) -> None:
        evidence = retrieve_for_condition("S1", self.questions["Q09"]["text"], self.memory)
        ids = [item["id"] for item in evidence]
        self.assertEqual(len(evidence), TOP_K_EVIDENCE)
        self.assertIn("M05", ids)
        self.assertTrue(
            any("written in Python" in item["content"] for item in evidence),
        )

    def test_q09_hybrid_with_pinned_minilm_puts_python_fact_in_top_four(self) -> None:
        """Regression: real MiniLM Q09 vectors + v2.1 stopword IDF → M05 in top-4."""
        self.assertEqual(self.q09_sims["question_id"], "Q09")
        self.assertEqual(
            self.q09_sims["model_revision"],
            "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
        )
        self.assertEqual(
            self.q09_sims["source_bundle_sha256"],
            "54680c28ef4832dd95a29e68ee05765b44c1bbe0fa9f3f87c8431e16698e0432",
        )
        vector_scores = {
            item_id: float(score)
            for item_id, score in self.q09_sims["vector_similarity_by_id"].items()
        }

        # Without stopwords (historical v2 lexical), M05 remains fifth under these vectors.
        v2_lexical = {
            row["id"]: row["lexical_rank"]
            for row in rank_all_lexical(
                self.questions["Q09"]["text"],
                self.memory["items"],
                apply_stopwords=False,
            )
        }
        v2_hybrid = sorted(
            (
                (
                    v2_lexical[item_id] + vector_scores[item_id],
                    item_id,
                )
                for item_id in vector_scores
            ),
            key=lambda row: (-row[0], row[1]),
        )
        self.assertEqual(v2_hybrid[4][1], "M05")
        self.assertAlmostEqual(v2_hybrid[4][0], 0.3660115583, places=7)
        self.assertAlmostEqual(v2_hybrid[3][0], 0.3802433219, places=7)

        hybrid = rank_all_hybrid(
            self.questions["Q09"]["text"],
            self.memory["items"],
            vector_scores,
        )
        top_ids = [row["id"] for row in hybrid]
        self.assertEqual(top_ids[:5], ["M07", "M05", "M06", "P03", "P04"])
        self.assertIn("M05", top_ids[:TOP_K_EVIDENCE])
        m05 = next(row for row in hybrid if row["id"] == "M05")
        self.assertEqual(m05["id"], hybrid[1]["id"])
        self.assertAlmostEqual(m05["combined_score"], 0.367627325, places=9)

        evidence = retrieve_for_condition(
            "S1",
            self.questions["Q09"]["text"],
            self.memory,
            vector_similarity_by_id=vector_scores,
        )
        self.assertEqual([item["id"] for item in evidence], ["M07", "M05", "M06", "P03"])

    def test_memory_questions_retain_expected_coverage(self) -> None:
        expectations = {
            "Q01": {"M01"},
            "Q02": {"M02"},
            "Q03": {"M03"},
            "Q04": {"M04"},
            "Q10": {"M06"},
            "Q11": {"P04"},
            "Q12": {"M07"},
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

    def test_manifest_records_retriever_version_and_stopwords(self) -> None:
        bundle = build_requests(DATA_DIR, repeats=1, seed=0)
        retrieval = bundle["manifest"]["retrieval"]
        self.assertEqual(retrieval["retriever"], RETRIEVER_VERSION)
        self.assertEqual(retrieval["retriever"], "pilot_hybrid_v2_1")
        self.assertEqual(retrieval["limit"], TOP_K_EVIDENCE)
        self.assertEqual(retrieval["stopwords"], STOPWORD_SET_ID)
        self.assertEqual(retrieval["stopword_count"], 127)
        self.assertEqual(retrieval, RETRIEVAL_CONFIG)

    def test_v1_and_simulator_matches_empty_subset_expectation(self) -> None:
        short = "Python harness"
        long_q = self.questions["Q09"]["text"]
        doc = "The local experiment harness for this project is written in Python."
        self.assertEqual(v1_plainto_and_lexical_rank(long_q, doc), 0.0)
        self.assertEqual(v1_plainto_and_lexical_rank(short, doc), 1.0)

    def test_pinned_similarity_fixture_exists(self) -> None:
        self.assertTrue(Path(Q09_SIMILARITIES).is_file())


if __name__ == "__main__":
    unittest.main()
