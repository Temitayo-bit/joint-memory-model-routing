from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path
from typing import Any, List, Mapping
from unittest import mock

from experiments.text_baseline.costs import active_inference_processing_cost
from experiments.text_baseline.embeddings import DEFAULT_MODEL_REVISION, build_embedding_bundle
from experiments.text_baseline.fixtures import DATA_DIR
from experiments.text_baseline.http_util import HttpTransportError, _read_bounded, post_json, redact_secrets
from experiments.text_baseline.import_responses import import_responses
from experiments.text_baseline.live_runner import (
    MODEL_BEARER_ENV,
    MODEL_BASE_URL_ENV,
    LARGE_MODEL_ID_ENV,
    SMALL_MODEL_ID_ENV,
    EDGE_URL_ENV,
    USER_JWT_ENV,
    LiveRunnerError,
    call_direct_model,
    filter_requests,
    run_live,
    stable_edge_request_id,
)
from experiments.text_baseline.run_builder import build_requests
from experiments.text_baseline.runpod_launch import PINNED_MODELS, VLLM_IMAGE, launch_bundle


def _fake_encoder(texts):
    vectors = []
    for index, _text in enumerate(texts):
        values = [0.0] * 384
        values[index % 384] = 1.0
        vectors.append(values)
    return vectors


class _FakeResponse:
    def __init__(self, payload: bytes, headers=None):
        self._payload = payload
        self._offset = 0
        self.headers = headers or {}

    def read(self, size: int = -1):
        if self._offset >= len(self._payload):
            return b""
        if size < 0:
            chunk = self._payload[self._offset :]
            self._offset = len(self._payload)
            return chunk
        chunk = self._payload[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


class LiveRunnerOfflineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = build_requests(DATA_DIR, repeats=1, seed=0)
        self.requests = self.bundle["requests"]

    def test_filter_by_condition_question_repeat_and_max(self) -> None:
        filtered = filter_requests(
            self.requests,
            conditions=["S0", "S1"],
            question_ids=["Q10"],
            repeats=[0],
            max_requests=1,
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["question_id"], "Q10")
        self.assertIn(filtered[0]["condition"], {"S0", "S1"})

    def test_active_inference_cost_matches_smoke_arithmetic(self) -> None:
        cost = active_inference_processing_cost(1733.479, 0.50)
        self.assertIsNotNone(cost)
        self.assertAlmostEqual(float(cost), 0.00024076097222222225)

    def test_resume_with_max_requests_advances(self) -> None:
        sample = [row for row in self.requests if row["condition"] == "S0"][:3]
        calls: List[Mapping[str, Any]] = []

        def post(url, body, headers, timeout_s=70, max_response_bytes=65536, secrets=None):
            calls.append({"url": url})
            return (
                200,
                {
                    "choices": [{"message": {"content": "answer-%s" % len(calls)}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                },
                10.0,
                b"{}",
            )

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run-max"
            env = {
                MODEL_BASE_URL_ENV: "https://model.example.invalid",
                MODEL_BEARER_ENV: "secret-bearer-token",
                SMALL_MODEL_ID_ENV: "small-model",
                LARGE_MODEL_ID_ENV: "large-model",
            }
            with mock.patch.dict("os.environ", env, clear=False):
                run_live(sample, out, transport="direct", max_requests=1, hourly_rate_usd=0.5, post=post)
                run_live(sample, out, transport="direct", max_requests=1, hourly_rate_usd=0.5, post=post)
            self.assertEqual(len(calls), 2)
            payload = json.loads((out / "responses.json").read_text(encoding="utf-8"))
            self.assertEqual(len(payload["responses"]), 2)

    def test_max_requests_rejects_zero(self) -> None:
        with self.assertRaisesRegex(Exception, "max_requests"):
            filter_requests(self.requests, max_requests=0)

    def test_resume_skips_completed_and_appends(self) -> None:
        sample = [row for row in self.requests if row["condition"] == "S0"][:2]
        calls: List[Mapping[str, Any]] = []

        def post(url, body, headers, timeout_s=70, max_response_bytes=65536, secrets=None):
            calls.append({"url": url, "body": body, "headers": headers})
            return (
                200,
                {
                    "choices": [{"message": {"content": "answer-%s" % len(calls)}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                },
                12.5,
                b"{}",
            )

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            env = {
                MODEL_BASE_URL_ENV: "https://model.example.invalid",
                MODEL_BEARER_ENV: "secret-bearer-token",
                SMALL_MODEL_ID_ENV: "small-model",
                LARGE_MODEL_ID_ENV: "large-model",
            }
            with mock.patch.dict("os.environ", env, clear=False):
                first = run_live(
                    sample[:1],
                    out,
                    transport="direct",
                    hourly_rate_usd=0.5,
                    post=post,
                )
                self.assertEqual(len(first["responses"]), 1)
                second = run_live(
                    sample,
                    out,
                    transport="direct",
                    hourly_rate_usd=0.5,
                    post=post,
                    resume=True,
                )
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(second["responses"]), 2)
            digests = [row["request_sha256"] for row in second["responses"]]
            self.assertEqual(len(set(digests)), 2)
            self.assertTrue((out / "responses.json").exists())

    def test_no_resume_refuses_existing_checkpoint(self) -> None:
        sample = [row for row in self.requests if row["condition"] == "S0"][:1]

        def post(*_args, **_kwargs):
            return (
                200,
                {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
                5.0,
                b"{}",
            )

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "protected"
            env = {
                MODEL_BASE_URL_ENV: "https://model.example.invalid",
                MODEL_BEARER_ENV: "secret-bearer-token",
                SMALL_MODEL_ID_ENV: "small-model",
                LARGE_MODEL_ID_ENV: "large-model",
            }
            with mock.patch.dict("os.environ", env, clear=False):
                run_live(sample, out, transport="direct", hourly_rate_usd=0.5, post=post)
                with self.assertRaises(LiveRunnerError):
                    run_live(sample, out, transport="direct", hourly_rate_usd=0.5, post=post, resume=False)

    def test_timeout_and_failure_capture(self) -> None:
        sample = self.requests[0]

        def post(*_args, **_kwargs):
            raise HttpTransportError("timeout", "request timed out")

        row = call_direct_model(
            sample,
            base_url="https://model.example.invalid",
            bearer="token",
            model_id="small",
            timeout_s=1,
            max_response_bytes=100,
            hourly_rate_usd=0.5,
            post=post,
        )
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["failure_code"], "timeout")
        self.assertIsNone(row["answer_text"])
        self.assertIsNone(row["latency_ms"]["first_token"])
        self.assertIsNone(row["costs"]["actual_rental_and_service_spend"])

    def test_redirect_rejection(self) -> None:
        sample = self.requests[0]

        def post(*_args, **_kwargs):
            raise HttpTransportError("redirect_rejected", "HTTP redirect rejected")

        row = call_direct_model(
            sample,
            base_url="https://model.example.invalid",
            bearer="token",
            model_id="small",
            timeout_s=1,
            max_response_bytes=100,
            hourly_rate_usd=None,
            post=post,
        )
        self.assertEqual(row["failure_code"], "redirect_rejected")

    def test_response_size_limit(self) -> None:
        sample = self.requests[0]

        def post(*_args, **_kwargs):
            raise HttpTransportError("response_too_large", "response exceeds size limit")

        row = call_direct_model(
            sample,
            base_url="https://model.example.invalid",
            bearer="token",
            model_id="small",
            timeout_s=1,
            max_response_bytes=8,
            hourly_rate_usd=None,
            post=post,
        )
        self.assertEqual(row["failure_code"], "response_too_large")

    def test_http_util_rejects_negative_limits_and_bounds_reads(self) -> None:
        with self.assertRaises(HttpTransportError):
            post_json(
                "https://example.invalid/v1",
                {},
                {},
                timeout_s=1,
                max_response_bytes=0,
            )
        oversized = _FakeResponse(b"x" * 20)
        with self.assertRaises(HttpTransportError):
            _read_bounded(oversized, 8)
        ok = _FakeResponse(b'{"ok":true}')
        self.assertEqual(_read_bounded(ok, 64), b'{"ok":true}')

    def test_secret_redaction(self) -> None:
        text = "authorization Bearer super-secret-value and again super-secret-value"
        redacted = redact_secrets(text, {"TOKEN": "super-secret-value"})
        self.assertNotIn("super-secret-value", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_cost_separation_and_importer_compatibility(self) -> None:
        sample = [row for row in self.requests if row["condition"] == "S0" and row["question_id"] == "Q10"][0]

        def post(*_args, **_kwargs):
            return (
                200,
                {
                    "choices": [{"message": {"content": "measured answer"}}],
                    "usage": {"prompt_tokens": 84, "completion_tokens": 82},
                },
                1733.479,
                b"{}",
            )

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "run"
            env = {
                MODEL_BASE_URL_ENV: "https://model.example.invalid",
                MODEL_BEARER_ENV: "secret-bearer-token",
                SMALL_MODEL_ID_ENV: "small-model",
                LARGE_MODEL_ID_ENV: "large-model",
            }
            with mock.patch.dict("os.environ", env, clear=False):
                result = run_live(
                    [sample],
                    out,
                    transport="direct",
                    hourly_rate_usd=0.5,
                    gpu_type="RTX 3090",
                    session_id="sess-1",
                    pod_id="pod-1",
                    small_model_revision="74d4bd2bd4bff9cafc9345221320bffb08b406a3",
                    quantization="awq",
                    server_version="vllm-0.29.0",
                    post=post,
                )
            response = result["responses"][0]
            self.assertEqual(response["status"], "success")
            self.assertIsNone(response["latency_ms"]["first_token"])
            self.assertAlmostEqual(response["costs"]["allocated_processing_cost"], 0.00024076097222222225)
            self.assertIsNone(response["costs"]["actual_rental_and_service_spend"])
            self.assertIsNone(response["costs"]["market_generation_estimate"])
            session = result["session"]
            self.assertEqual(session["gpu_type"], "RTX 3090")
            self.assertEqual(session["hourly_rate_usd"], 0.5)
            self.assertEqual(
                session["small_model_revision"],
                "74d4bd2bd4bff9cafc9345221320bffb08b406a3",
            )
            self.assertIsNone(session["session_actuals"]["rental_and_service_spend"])
            # Session total spend stays in session metadata only.
            session["session_actuals"]["rental_and_service_spend"] = 0.1292403981
            (out / "session.json").write_text(json.dumps(session), encoding="utf-8")
            with mock.patch.dict("os.environ", env, clear=False):
                resumed = run_live(
                    [sample],
                    out,
                    transport="direct",
                    hourly_rate_usd=0.5,
                    post=post,
                    resume=True,
                )
            self.assertEqual(
                resumed["session"]["session_actuals"]["rental_and_service_spend"],
                0.1292403981,
            )
            imported = import_responses(
                self.bundle,
                {"responses": result["responses"]},
            )
            matched = [row for row in imported["records"] if row["request_sha256"] == sample["request_sha256"]][0]
            self.assertEqual(matched["status"], "success")
            self.assertAlmostEqual(matched["costs"]["allocated_processing_cost"], 0.00024076097222222225)
            self.assertIsNone(matched["costs"]["actual_rental_and_service_spend"])
            checkpoint_text = (out / "responses.json").read_text(encoding="utf-8")
            self.assertNotIn("secret-bearer-token", checkpoint_text)

    def test_fixed_generation_is_sent(self) -> None:
        sample = self.requests[0]
        captured = {}

        def post(url, body, headers, **_kwargs):
            captured["body"] = body
            return (
                200,
                {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
                5.0,
                b"{}",
            )

        call_direct_model(
            sample,
            base_url="https://model.example.invalid",
            bearer="token",
            model_id="small",
            timeout_s=1,
            max_response_bytes=1000,
            hourly_rate_usd=None,
            post=post,
        )
        body = captured["body"]
        self.assertFalse(body["stream"])
        self.assertEqual(body["max_tokens"], 256)
        self.assertEqual(body["temperature"], 0.7)
        self.assertEqual(body["top_p"], 0.8)
        self.assertEqual(body["top_k"], 20)
        self.assertEqual(body["min_p"], 0)
        self.assertEqual(body["seed"], 42)
        self.assertEqual(body["chat_template_kwargs"]["enable_thinking"], False)

    def test_edge_transport_parses_flat_handler_contract(self) -> None:
        sample = [row for row in self.requests if row["condition"] == "S0"][0]
        captured = {}
        server_evidence = "a" * 64

        def post(url, body, headers, **_kwargs):
            captured["url"] = url
            captured["body"] = body
            captured["headers"] = headers
            return (
                200,
                {
                    "request_id": body["request_id"],
                    "status": "success",
                    "condition": "S0",
                    "answer_text": "edge-answer",
                    "retrieval_ms": 0.0,
                    "model_http_ms": 11.0,
                    "gateway_ms": 1.0,
                    "first_token_ms": None,
                    "input_tokens": 2,
                    "output_tokens": 3,
                    "evidence_sha256": server_evidence,
                },
                15.0,
                b"{}",
            )

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "edge"
            env = {
                EDGE_URL_ENV: "https://example.functions.supabase.co/text-baseline-pilot",
                USER_JWT_ENV: "user-jwt-secret",
            }
            with mock.patch.dict("os.environ", env, clear=False):
                result = run_live(
                    [sample],
                    out,
                    transport="edge",
                    snapshot_id="11111111-1111-1111-1111-111111111111",
                    hourly_rate_usd=0.5,
                    post=post,
                )
            self.assertEqual(set(captured["body"]), {"request_id", "snapshot_id", "question", "condition"})
            self.assertEqual(captured["body"]["request_id"], stable_edge_request_id(sample["request_sha256"]))
            self.assertNotIn("messages", captured["body"])
            self.assertNotIn("model", captured["body"])
            response = result["responses"][0]
            self.assertEqual(response["status"], "success")
            self.assertEqual(response["evidence_source"], "edge")
            self.assertEqual(response["evidence_sha256"], server_evidence)
            self.assertEqual(response["exported_evidence_sha256"], sample["evidence_sha256"])
            self.assertEqual(response["latency_ms"]["model_http"], 11.0)
            self.assertAlmostEqual(response["costs"]["allocated_processing_cost"], 11.0 / 3_600_000 * 0.5)
            self.assertNotIn("user-jwt-secret", (out / "responses.json").read_text(encoding="utf-8"))
            imported = import_responses(self.bundle, {"responses": result["responses"]})
            matched = [row for row in imported["records"] if row["request_sha256"] == sample["request_sha256"]][0]
            self.assertEqual(matched["evidence_sha256"], server_evidence)
            self.assertEqual(matched["evidence_source"], "edge")

    def test_embedding_bundle_offline(self) -> None:
        bundle = build_embedding_bundle(DATA_DIR, encode_fn=_fake_encoder)
        self.assertEqual(bundle["dims"], 384)
        self.assertEqual(bundle["model_revision"], DEFAULT_MODEL_REVISION)
        self.assertEqual(len(bundle["items"]), len(json.loads((DATA_DIR / "memory.json").read_text())["items"]))
        self.assertEqual(len(bundle["questions"]), 12)
        for row in bundle["items"] + bundle["questions"]:
            norm = math.sqrt(sum(value * value for value in row["embedding"]))
            self.assertAlmostEqual(norm, 1.0, places=6)

    def test_runpod_launch_pins_revisions_and_settings(self) -> None:
        small = launch_bundle("small")
        large = launch_bundle("large")
        self.assertEqual(small["image"], VLLM_IMAGE)
        self.assertTrue(small["image"].startswith("vllm/vllm-openai@sha256:"))
        self.assertIn("--generation-config", small["runpod_start_command"])
        self.assertIn("vllm", small["runpod_start_command"])
        self.assertIn(PINNED_MODELS["small"]["revision"], small["runpod_start_command"])
        self.assertIn(PINNED_MODELS["large"]["revision"], large["runpod_start_command"])
        hostile = launch_bundle("small", host="0.0.0.0;injected")
        self.assertIn("'0.0.0.0;injected'", hostile["docker_run_command"])
        self.assertEqual(small["fixed_generation"]["seed"], 42)
        self.assertTrue(small["not_executed"])


if __name__ == "__main__":
    unittest.main()
