from __future__ import annotations

import unittest

from experiments.text_baseline.constants import MEMORY_CONDITIONS, NO_MEMORY_CONDITIONS
from experiments.text_baseline.fixtures import DATA_DIR
from experiments.text_baseline.run_builder import build_requests


class IsolationAndEvidenceTests(unittest.TestCase):
    def test_no_memory_conditions_bypass_retrieval(self) -> None:
        bundle = build_requests(DATA_DIR, repeats=1, seed=0)
        for row in bundle["requests"]:
            if row["condition"] in NO_MEMORY_CONDITIONS:
                self.assertFalse(row["retrieval_invoked"])
                self.assertEqual(row["evidence"], [])
                self.assertIn("Memory evidence: none", row["messages"][1]["content"])

    def test_s1_and_l1_share_evidence_for_the_same_question(self) -> None:
        bundle = build_requests(DATA_DIR, repeats=2, seed=4)
        grouped = {}
        for row in bundle["requests"]:
            if row["condition"] in MEMORY_CONDITIONS:
                grouped.setdefault(row["question_id"], []).append(row)
        for question_id, rows in grouped.items():
            hashes = {row["evidence_sha256"] for row in rows}
            self.assertEqual(len(hashes), 1, question_id)
            contents = {tuple(item["id"] for item in rows[0]["evidence"])}
            for row in rows[1:]:
                contents.add(tuple(item["id"] for item in row["evidence"]))
            self.assertEqual(len(contents), 1)
            self.assertTrue(rows[0]["evidence"])
            kinds = {item["kind"] for item in rows[0]["evidence"]}
            self.assertTrue(kinds.issubset({"fact", "source_passage"}))

    def test_memory_and_no_memory_hashes_differ(self) -> None:
        bundle = build_requests(DATA_DIR, repeats=1, seed=0)
        by_q = {}
        for row in bundle["requests"]:
            by_q.setdefault(row["question_id"], {})[row["condition"]] = row
        for conditions in by_q.values():
            self.assertNotEqual(conditions["S0"]["evidence_sha256"], conditions["S1"]["evidence_sha256"])
            self.assertEqual(conditions["S0"]["evidence_sha256"], conditions["L0"]["evidence_sha256"])
            self.assertEqual(conditions["S1"]["evidence_sha256"], conditions["L1"]["evidence_sha256"])


if __name__ == "__main__":
    unittest.main()
