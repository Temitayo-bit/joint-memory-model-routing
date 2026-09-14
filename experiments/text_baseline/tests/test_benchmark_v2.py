"""Benchmark-v2 dataset contracts: counts, strata, seeds, leakage, imports."""

from __future__ import annotations

import copy
import unittest
from collections import Counter

from experiments.text_baseline.constants import (
    BENCHMARK_V2_GENERATION_SEEDS,
    BENCHMARK_V2_STRATA,
    CONDITIONS,
    FIXED_GENERATION,
)
from experiments.text_baseline.fixtures import (
    DATA_DIR,
    DATASETS_DIR,
    assert_split_disjointness,
    fixture_hashes,
    load_dataset_manifest,
    load_memory,
    load_questions,
    load_scoring_anchors,
)
from experiments.text_baseline.import_responses import ImportError_, import_responses
from experiments.text_baseline.prompts import prompt_contains_evidence_ids, prompt_contains_scoring_text
from experiments.text_baseline.run_builder import build_requests, request_digest
from experiments.text_baseline.schedule import build_cells, expected_cell_count
from experiments.text_baseline.retrieval import retrieve_for_condition


DEV_DIR = DATASETS_DIR / "benchmark-v2-dev"
EVAL_DIR = DATASETS_DIR / "benchmark-v2-eval"


class BenchmarkV2FixtureTests(unittest.TestCase):
    def test_dev_and_eval_counts_and_strata(self) -> None:
        for path, count, per_stratum in ((DEV_DIR, 16, 4), (EVAL_DIR, 48, 12)):
            manifest = load_dataset_manifest(path)
            assert manifest is not None
            questions = load_questions(path)
            self.assertEqual(manifest["question_count"], count)
            self.assertEqual(len(questions), count)
            self.assertEqual(len(load_scoring_anchors(path)["anchors"]), count)
            strata = Counter(question["stratum"] for question in questions)
            self.assertEqual(set(strata), set(BENCHMARK_V2_STRATA))
            self.assertTrue(all(value == per_stratum for value in strata.values()))
            self.assertEqual(tuple(manifest["allowed_generation_seeds"]), BENCHMARK_V2_GENERATION_SEEDS)

    def test_split_disjointness(self) -> None:
        assert_split_disjointness(DEV_DIR, EVAL_DIR)

    def test_fixture_hashes_are_stable_and_distinct(self) -> None:
        legacy = fixture_hashes(DATA_DIR)
        dev = fixture_hashes(DEV_DIR)
        evaluation = fixture_hashes(EVAL_DIR)
        self.assertEqual(legacy["memory_sha256"], fixture_hashes(DATA_DIR)["memory_sha256"])
        self.assertNotEqual(dev["questions_sha256"], evaluation["questions_sha256"])
        self.assertNotEqual(dev["memory_sha256"], evaluation["memory_sha256"])
        self.assertIn("manifest_sha256", dev)
        self.assertNotIn("manifest_sha256", legacy)

    def test_held_out_cardinality_is_576(self) -> None:
        bundle = build_requests(EVAL_DIR, repeats=1, seed=0)
        self.assertEqual(bundle["manifest"]["cell_count"], 576)
        self.assertEqual(bundle["manifest"]["expected_cell_count"], 576)
        self.assertEqual(
            expected_cell_count(1, question_count=48, generation_seed_count=3),
            576,
        )
        seeds = {row["generation_seed"] for row in bundle["requests"]}
        self.assertEqual(seeds, set(BENCHMARK_V2_GENERATION_SEEDS))
        pairs = {
            (row["question_id"], row["condition"], row["generation_seed"])
            for row in bundle["requests"]
        }
        question_ids = {question["id"] for question in load_questions(EVAL_DIR)}
        expected = {
            (qid, condition, seed)
            for qid in question_ids
            for condition in CONDITIONS
            for seed in BENCHMARK_V2_GENERATION_SEEDS
        }
        self.assertEqual(pairs, expected)

    def test_dev_cardinality_is_192(self) -> None:
        bundle = build_requests(DEV_DIR, repeats=1, seed=0)
        self.assertEqual(bundle["manifest"]["cell_count"], 192)
        self.assertEqual(bundle["manifest"]["expected_cell_count"], 192)

    def test_generation_seed_changes_digest_not_schedule_identity_fields(self) -> None:
        bundle = build_requests(DEV_DIR, repeats=1, seed=0)
        by_key = {}
        for row in bundle["requests"]:
            key = (row["question_id"], row["condition"], row["repeat_index"])
            by_key.setdefault(key, []).append(row)
        sample = next(rows for rows in by_key.values() if len(rows) == 3)
        digests = {row["request_sha256"] for row in sample}
        self.assertEqual(len(digests), 3)
        self.assertEqual({row["generation_seed"] for row in sample}, set(BENCHMARK_V2_GENERATION_SEEDS))

    def test_deterministic_schedule_ordering(self) -> None:
        first = build_requests(EVAL_DIR, repeats=1, seed=11)
        second = build_requests(EVAL_DIR, repeats=1, seed=11)
        self.assertEqual(first["manifest"]["schedule_sha256"], second["manifest"]["schedule_sha256"])
        self.assertEqual(
            [row["request_sha256"] for row in first["requests"]],
            [row["request_sha256"] for row in second["requests"]],
        )
        other = build_cells(
            load_questions(EVAL_DIR),
            repeats=1,
            seed=12,
            generation_seeds=BENCHMARK_V2_GENERATION_SEEDS,
        )
        self.assertNotEqual(
            [(row["question_id"], row["condition"], row["generation_seed"]) for row in first["requests"]],
            [(row["question_id"], row["condition"], row["generation_seed"]) for row in other],
        )

    def test_scoring_anchors_and_evidence_ids_do_not_leak_into_prompts(self) -> None:
        anchors = load_scoring_anchors(EVAL_DIR)
        memory_ids = [str(item["id"]) for item in load_memory(EVAL_DIR)["items"]]
        bundle = build_requests(EVAL_DIR, repeats=1, seed=0)
        for row in bundle["requests"]:
            self.assertFalse(prompt_contains_scoring_text(row["messages"], anchors))
            self.assertFalse(prompt_contains_evidence_ids(row["messages"], memory_ids))
            blob = "\n".join(message["content"] for message in row["messages"])
            self.assertNotIn("SCORING-ANCHOR", blob)
            self.assertNotIn("required_evidence_ids", blob)
            self.assertNotIn("diagnostic_tags", blob)
            for item in row["evidence"]:
                self.assertNotIn(str(item["id"]), blob)

    def test_import_rejects_mismatched_dataset_identity(self) -> None:
        bundle = build_requests(DEV_DIR, repeats=1, seed=0)
        bad = copy.deepcopy(bundle)
        bad["manifest"]["dataset_id"] = "wrong-dataset"
        with self.assertRaises(ImportError_):
            import_responses(bad, {"responses": []})

    def test_import_rejects_disallowed_generation_seed(self) -> None:
        bundle = build_requests(DEV_DIR, repeats=1, seed=0)
        bad = copy.deepcopy(bundle)
        bad["requests"][0]["generation_seed"] = 99
        bad["requests"][0]["request_sha256"] = request_digest(bad["requests"][0])
        digests = [row["request_sha256"] for row in bad["requests"]]
        from experiments.text_baseline.hashing import sha256_json
        from experiments.text_baseline.schedule import schedule_hash

        bad["manifest"]["requests_sha256"] = sha256_json(digests)
        schedule_cells = []
        for row in bad["requests"]:
            schedule_cells.append(
                {
                    "repeat_index": row["repeat_index"],
                    "question_id": row["question_id"],
                    "condition": row["condition"],
                    "generation_seed": row["generation_seed"],
                }
            )
        bad["manifest"]["schedule_sha256"] = schedule_hash(schedule_cells)
        with self.assertRaises(ImportError_):
            import_responses(bad, {"responses": []})

    def test_s0_l0_still_skip_retrieval(self) -> None:
        memory = load_memory(EVAL_DIR)
        question = load_questions(EVAL_DIR)[0]
        self.assertEqual(retrieve_for_condition("S0", question["text"], memory), [])
        self.assertEqual(retrieve_for_condition("L0", question["text"], memory), [])
        bundle = build_requests(EVAL_DIR, repeats=1, seed=0)
        for row in bundle["requests"]:
            if row["condition"] in {"S0", "L0"}:
                self.assertEqual(row["evidence"], [])
                self.assertFalse(row["retrieval_invoked"])

    def test_legacy_pilot_unchanged_cell_count_and_fixed_generation(self) -> None:
        bundle = build_requests(DATA_DIR, repeats=1, seed=0)
        self.assertEqual(len(load_questions(DATA_DIR)), 12)
        self.assertEqual(bundle["manifest"]["cell_count"], 48)
        self.assertEqual(bundle["manifest"]["expected_cell_count"], expected_cell_count(1))
        self.assertNotIn("generation_seed", bundle["requests"][0])
        self.assertEqual(bundle["manifest"]["fixed_generation"], FIXED_GENERATION)
        self.assertEqual(bundle["manifest"]["dataset_split"], "legacy")


if __name__ == "__main__":
    unittest.main()
