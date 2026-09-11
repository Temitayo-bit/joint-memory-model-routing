from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.text_baseline.costs import CostError, allocated_processing_cost, market_generation_estimate
from experiments.text_baseline.fixtures import DATA_DIR
from experiments.text_baseline.import_responses import ImportError_, import_responses
from experiments.text_baseline.io_guard import OverwriteError, prepare_output_dir
from experiments.text_baseline.run_builder import build_requests, mock_record


def _success(request, **overrides):
    row = {
        "request_sha256": request["request_sha256"],
        "question_id": request["question_id"],
        "condition": request["condition"],
        "repeat_index": request["repeat_index"],
        "status": "success",
        "answer_text": "measured",
        "failure_code": None,
        "evidence_sha256": request["evidence_sha256"],
        "latency_ms": {
            "retrieval": 1.0,
            "model_http": 2.0,
            "end_to_end": 3.0,
            "first_token": None,
            "gateway": 0.5,
            "client": 0.25,
        },
        "tokens": {"input": 10, "output": 4, "source": "model_server"},
        "quality": None,
        "costs": {
            "market_generation_estimate": None,
            "allocated_processing_cost": None,
            "actual_rental_and_service_spend": None,
        },
    }
    row.update(overrides)
    return row


class MeasurementImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = build_requests(DATA_DIR, repeats=1, seed=0)
        self.sample = self.bundle["requests"][0]

    def test_mock_measurements_are_null(self) -> None:
        record = mock_record(self.sample)
        self.assertEqual(record["status"], "mock")
        self.assertIsNone(record["tokens"]["input"])
        self.assertIsNone(record["quality"])
        self.assertIsNone(record["costs"]["market_generation_estimate"])
        self.assertIsNone(record["costs"]["allocated_processing_cost"])
        self.assertIsNone(record["costs"]["actual_rental_and_service_spend"])
        self.assertTrue(all(value is None for value in record["latency_ms"].values()))

    def test_malformed_latency_and_prices_are_rejected(self) -> None:
        bad_latency = _success(self.sample)
        bad_latency["latency_ms"]["model_http"] = -1
        with self.assertRaises(ImportError_):
            import_responses(self.bundle, {"responses": [bad_latency]})
        first_token = _success(self.sample)
        first_token["latency_ms"]["first_token"] = 3
        with self.assertRaises(ImportError_):
            import_responses(self.bundle, {"responses": [first_token]})
        with self.assertRaises(CostError):
            market_generation_estimate(10, 4, -1, 2)
        with self.assertRaises(CostError):
            allocated_processing_cost("not-a-number", 1)

    def test_tokens_without_model_server_source_rejected(self) -> None:
        row = _success(self.sample)
        row["tokens"]["source"] = "guessed"
        with self.assertRaises(ImportError_):
            import_responses(self.bundle, {"responses": [row]})

    def test_duplicate_missing_failed_and_tampered(self) -> None:
        success = _success(self.sample)
        with self.assertRaises(ImportError_):
            import_responses(self.bundle, {"responses": [success, success]})
        imported = import_responses(self.bundle, {"responses": []})
        self.assertTrue(all(row["status"] == "missing" for row in imported["records"]))
        failed = _success(self.sample)
        failed["status"] = "failed"
        failed["answer_text"] = None
        failed["failure_code"] = "model_http_error"
        mixed = import_responses(self.bundle, {"responses": [failed]})
        self.assertEqual(mixed["records"][0]["status"], "failed")
        self.assertIsNone(mixed["records"][0]["answer_text"])
        tampered = _success(self.sample)
        tampered["request_sha256"] = "0" * 64
        with self.assertRaises(ImportError_):
            import_responses(self.bundle, {"responses": [tampered]})
        evidence = _success(self.sample)
        evidence["evidence_sha256"] = "0" * 64
        with self.assertRaises(ImportError_):
            import_responses(self.bundle, {"responses": [evidence]})

    def test_market_estimate_uses_documented_rates_only(self) -> None:
        row = _success(self.sample)
        rates = {self.sample["condition"]: {"input_per_million": 1000, "output_per_million": 2000}}
        imported = import_responses(self.bundle, {"responses": [row]}, market_rates=rates)
        self.assertEqual(imported["records"][0]["costs"]["market_generation_estimate"], 0.018)
        self.assertIsNone(imported["records"][0]["costs"]["actual_rental_and_service_spend"])

    def test_processing_allocation_is_separate(self) -> None:
        row = _success(self.sample)
        imported = import_responses(
            self.bundle,
            {"responses": [row]},
            session_processing_total=2.0,
        )
        self.assertEqual(imported["records"][0]["costs"]["allocated_processing_cost"], 2.0)
        self.assertIsNone(imported["records"][0]["costs"]["market_generation_estimate"])

    def test_truncated_and_tampered_request_lists_are_rejected(self) -> None:
        truncated = {
            "manifest": self.bundle["manifest"],
            "requests": self.bundle["requests"][:10],
        }
        with self.assertRaises(ImportError_):
            import_responses(truncated, {"responses": []})
        tampered = {
            "manifest": {**self.bundle["manifest"], "requests_sha256": "0" * 64},
            "requests": self.bundle["requests"],
        }
        with self.assertRaises(ImportError_):
            import_responses(tampered, {"responses": []})

    def test_invented_market_estimate_without_rates_is_rejected(self) -> None:
        row = _success(self.sample)
        row["costs"]["market_generation_estimate"] = 9.99
        with self.assertRaises(ImportError_):
            import_responses(self.bundle, {"responses": [row]})

    def test_overwrite_protection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out"
            prepare_output_dir(path)
            with self.assertRaises(OverwriteError):
                prepare_output_dir(path)


if __name__ == "__main__":
    unittest.main()
