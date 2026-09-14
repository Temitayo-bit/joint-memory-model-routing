from __future__ import annotations

import math
import unittest
import uuid

from experiments.text_baseline.live_client import LiveClientError, build_live_request, validate_embedding


def _unit(dims: int = 384):
    values = [0.0] * dims
    values[0] = 1.0
    return values


class LiveClientTests(unittest.TestCase):
    def test_memory_condition_requires_normalized_embedding(self) -> None:
        request_id = str(uuid.uuid4())
        snapshot_id = str(uuid.uuid4())
        body = build_live_request(request_id, snapshot_id, "What tea?", "S1", _unit())
        self.assertEqual(set(body), {"request_id", "snapshot_id", "question", "condition", "embedding"})
        self.assertAlmostEqual(math.sqrt(sum(x * x for x in body["embedding"])), 1.0)

    def test_no_memory_rejects_embedding(self) -> None:
        with self.assertRaises(LiveClientError):
            build_live_request(str(uuid.uuid4()), str(uuid.uuid4()), "q", "S0", _unit())

    def test_rejects_whitespace_question(self) -> None:
        with self.assertRaises(LiveClientError):
            build_live_request(str(uuid.uuid4()), str(uuid.uuid4()), "   ", "S0")

    def test_rejects_client_secrets_and_settings(self) -> None:
        with self.assertRaises(LiveClientError):
            build_live_request(
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                "q",
                "S0",
                extra={"model_url": "https://example.invalid"},
            )
        with self.assertRaises(LiveClientError):
            build_live_request(
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                "q",
                "S0",
                extra={"min_p": 0.1},
            )
        with self.assertRaises(LiveClientError):
            validate_embedding([0.1] * 10)
        with self.assertRaises(LiveClientError):
            validate_embedding([0.0] * 384)

    def test_generation_seed_allow_list(self) -> None:
        body = build_live_request(
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            "q",
            "S0",
            generation_seed=43,
        )
        self.assertEqual(body["generation_seed"], 43)
        with self.assertRaises(LiveClientError):
            build_live_request(
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                "q",
                "S0",
                generation_seed=99,
            )
        with self.assertRaises(LiveClientError):
            build_live_request(
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                "q",
                "S0",
                extra={"seed": 42},
            )


if __name__ == "__main__":
    unittest.main()
