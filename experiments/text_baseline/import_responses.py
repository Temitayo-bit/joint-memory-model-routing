"""Validate imported measured responses. Do not invent measurements."""

from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from experiments.text_baseline.costs import allocated_processing_cost, market_generation_estimate
from experiments.text_baseline.hashing import sha256_json
from experiments.text_baseline.run_builder import empty_measurements, request_digest


class ImportError_(ValueError):
    """Malformed, duplicate, missing, failed, or tampered response import."""


_ALLOWED_STATUS = {"success", "failed", "missing"}
_LATENCY_KEYS = ("retrieval", "model_http", "end_to_end", "first_token", "gateway", "client")
_CONDITIONS = ("S0", "S1", "L0", "L1")
_RATE_META_KEYS = ("currency", "source_url", "checked_on", "priced_model_or_service", "basis")


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ImportError_("%s must be an object" % label)
    return value


def _optional_non_negative(value: Any, label: str) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ImportError_("%s must be a number" % label)
    if not isinstance(value, (int, float)):
        raise ImportError_("%s must be a number" % label)
    if not math.isfinite(value):
        raise ImportError_("%s must be finite" % label)
    if value < 0:
        raise ImportError_("%s must be >= 0" % label)
    return float(value)


def _optional_token(value: Any, label: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ImportError_("%s must be a non-negative integer" % label)
    return value


def validate_measurement_block(payload: Mapping[str, Any]) -> Dict[str, Any]:
    latency = _require_mapping(payload.get("latency_ms"), "latency_ms")
    if set(latency.keys()) != set(_LATENCY_KEYS):
        raise ImportError_("latency_ms has unknown or missing keys")
    checked_latency = {key: _optional_non_negative(latency[key], "latency_ms.%s" % key) for key in _LATENCY_KEYS}
    if checked_latency["first_token"] is not None:
        raise ImportError_("first_token latency must be null for non-streaming requests")
    tokens = _require_mapping(payload.get("tokens"), "tokens")
    token_in = _optional_token(tokens.get("input"), "tokens.input")
    token_out = _optional_token(tokens.get("output"), "tokens.output")
    source = tokens.get("source")
    if (token_in is not None or token_out is not None) and source != "model_server":
        raise ImportError_("measured tokens require source=model_server")
    if source not in (None, "model_server"):
        raise ImportError_("unknown token source")
    costs = _require_mapping(payload.get("costs") or empty_measurements()["costs"], "costs")
    for key in ("market_generation_estimate", "allocated_processing_cost", "actual_rental_and_service_spend"):
        _optional_non_negative(costs.get(key), "costs.%s" % key)
    if payload.get("quality") is not None and not isinstance(payload.get("quality"), dict):
        raise ImportError_("quality must be null or an object")
    return {
        "latency_ms": checked_latency,
        "tokens": {"input": token_in, "output": token_out, "source": source},
        "quality": payload.get("quality"),
        "costs": {
            "market_generation_estimate": costs.get("market_generation_estimate"),
            "allocated_processing_cost": costs.get("allocated_processing_cost"),
            "actual_rental_and_service_spend": costs.get("actual_rental_and_service_spend"),
        },
    }


def _index_responses(responses: Sequence[Mapping[str, Any]]) -> Dict[str, Mapping[str, Any]]:
    indexed: Dict[str, Mapping[str, Any]] = {}
    for row in responses:
        if not isinstance(row, Mapping):
            raise ImportError_("each response must be an object")
        digest = row.get("request_sha256")
        if not digest or not isinstance(digest, str):
            raise ImportError_("each response needs request_sha256")
        if digest in indexed:
            raise ImportError_("duplicate response for %s" % digest)
        indexed[digest] = row
    return indexed


def _validate_market_rates(market_rates: Mapping[str, Any]) -> None:
    for key in _RATE_META_KEYS:
        value = market_rates.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ImportError_("market rates require %s" % key)
    if not market_rates["source_url"].startswith("https://"):
        raise ImportError_("market rate source_url must be https")
    try:
        date.fromisoformat(market_rates["checked_on"])
    except ValueError as exc:
        raise ImportError_("market rate checked_on must be YYYY-MM-DD") from exc
    if market_rates["basis"] not in {"exact_model", "model_class_proxy"}:
        raise ImportError_("market rate basis must be exact_model or model_class_proxy")
    if market_rates.get("currency") != "USD":
        raise ImportError_("market rate currency must be USD for this harness")
    for condition in _CONDITIONS:
        entry = market_rates.get(condition)
        if not isinstance(entry, Mapping):
            raise ImportError_("market rates require an entry for %s" % condition)
        for field in ("input_per_million", "output_per_million"):
            value = entry.get(field)
            if value is None:
                continue
            _optional_non_negative(value, "%s.%s" % (condition, field))


def import_responses(
    requests_bundle: Mapping[str, Any],
    responses_payload: Mapping[str, Any],
    market_rates: Optional[Mapping[str, Any]] = None,
    session_processing_total: Any = None,
) -> Dict[str, Any]:
    requests = requests_bundle["requests"]
    if not isinstance(requests, list):
        raise ImportError_("requests bundle is missing the requests list")
    manifest = _require_mapping(requests_bundle.get("manifest"), "manifest")
    expected_count = manifest.get("expected_cell_count")
    if not isinstance(expected_count, int) or isinstance(expected_count, bool):
        raise ImportError_("manifest.expected_cell_count is required")
    if len(requests) != expected_count:
        raise ImportError_("incomplete or extra schedule cells")
    schedule = manifest.get("schedule_sha256")
    if not isinstance(schedule, str) or not re.fullmatch(r"[0-9a-f]{64}", schedule):
        raise ImportError_("manifest.schedule_sha256 is required")
    expected_requests_hash = manifest.get("requests_sha256")
    if not isinstance(expected_requests_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_requests_hash):
        raise ImportError_("manifest.requests_sha256 is required")
    recomputed_digests = []
    for row in requests:
        if not isinstance(row, Mapping):
            raise ImportError_("each request must be an object")
        digest = request_digest(row)
        if row.get("request_sha256") != digest:
            raise ImportError_("request digest does not match canonical request fields")
        recomputed_digests.append(digest)
    if expected_requests_hash != sha256_json(recomputed_digests):
        raise ImportError_("tampered requests list")
    if market_rates is not None:
        _validate_market_rates(_require_mapping(market_rates, "market_rates"))
    raw_responses = responses_payload.get("responses")
    if not isinstance(raw_responses, list):
        raise ImportError_("responses must be a list")
    indexed = _index_responses(raw_responses)
    expected = set(recomputed_digests)
    extra = set(indexed) - expected
    if extra:
        raise ImportError_("tampered or unknown request hashes in responses")
    completed = 0
    records = []
    for request in requests:
        digest = request["request_sha256"]
        if digest not in indexed:
            record = {
                "request_sha256": digest,
                "question_id": request["question_id"],
                "condition": request["condition"],
                "repeat_index": request["repeat_index"],
                "status": "missing",
                "answer_text": None,
                "failure_code": "missing_response",
                "evidence_sha256": request["evidence_sha256"],
            }
            record.update(empty_measurements())
            records.append(record)
            continue
        raw = indexed[digest]
        if raw.get("evidence_sha256") != request["evidence_sha256"]:
            raise ImportError_("tampered evidence hash for %s" % digest)
        if raw.get("condition") != request["condition"] or raw.get("question_id") != request["question_id"]:
            raise ImportError_("tampered identity for %s" % digest)
        status = raw.get("status")
        if status not in _ALLOWED_STATUS:
            raise ImportError_("invalid status")
        measurements = empty_measurements()
        if status == "success":
            measurements = validate_measurement_block(raw)
            completed += 1
            rates = (market_rates or {}).get(request["condition"], {})
            computed = market_generation_estimate(
                measurements["tokens"]["input"],
                measurements["tokens"]["output"],
                rates.get("input_per_million") if isinstance(rates, Mapping) else None,
                rates.get("output_per_million") if isinstance(rates, Mapping) else None,
            )
            provided = measurements["costs"]["market_generation_estimate"]
            if provided is not None and computed is None:
                raise ImportError_("market estimate requires measured tokens and documented rates")
            if provided is not None and computed is not None and str(provided) != computed:
                raise ImportError_("market estimate does not match tokens and documented rates")
            measurements["costs"]["market_generation_estimate"] = (
                float(computed) if computed is not None else None
            )
        if status == "failed":
            measurements = validate_measurement_block(raw) if raw.get("latency_ms") else empty_measurements()
            if raw.get("answer_text"):
                raise ImportError_("failed responses must not include answer_text")
        record = {
            "request_sha256": digest,
            "question_id": request["question_id"],
            "condition": request["condition"],
            "repeat_index": request["repeat_index"],
            "status": status,
            "answer_text": raw.get("answer_text") if status == "success" else None,
            "failure_code": raw.get("failure_code") if status != "success" else None,
            "evidence_sha256": request["evidence_sha256"],
        }
        if status == "success" and not record["answer_text"]:
            raise ImportError_("successful responses need answer_text")
        if status == "failed" and not record["failure_code"]:
            raise ImportError_("failed responses need failure_code")
        record.update(measurements)
        records.append(record)
    if session_processing_total is not None:
        share = allocated_processing_cost(session_processing_total, completed if completed else None)
        for record in records:
            if record["status"] == "success":
                if record["costs"]["allocated_processing_cost"] is None:
                    record["costs"]["allocated_processing_cost"] = float(share) if share is not None else None
    return {
        "manifest": {
            **manifest,
            "market_rates_sha256": sha256_json(market_rates) if market_rates is not None else None,
            "import_sha256": sha256_json(records),
            "not_a_research_result": True,
        },
        "records": records,
    }


def load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ImportError_("JSON root must be an object")
    return payload
