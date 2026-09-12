"""Execute exported text-baseline requests against a model or Edge Function."""

from __future__ import annotations

import json
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set

from experiments.text_baseline.constants import CONDITIONS, FIXED_GENERATION, MEMORY_CONDITIONS
from experiments.text_baseline.costs import active_inference_processing_cost, session_actuals_template
from experiments.text_baseline.hashing import canonical_json
from experiments.text_baseline.http_util import HttpTransportError, post_json, redact_secrets
from experiments.text_baseline.live_client import LiveClientError, build_live_request

DEFAULT_TIMEOUT_S = 70.0
DEFAULT_MAX_RESPONSE_BYTES = 64 * 1024
MODEL_BASE_URL_ENV = "TEXT_BASELINE_MODEL_BASE_URL"
MODEL_BEARER_ENV = "TEXT_BASELINE_MODEL_BEARER"
SMALL_MODEL_ID_ENV = "TEXT_BASELINE_SMALL_MODEL_ID"
LARGE_MODEL_ID_ENV = "TEXT_BASELINE_LARGE_MODEL_ID"
EDGE_URL_ENV = "TEXT_BASELINE_EDGE_FUNCTION_URL"
USER_JWT_ENV = "TEXT_BASELINE_USER_JWT"
PUBLISHABLE_KEY_ENV = "TEXT_BASELINE_SUPABASE_PUBLISHABLE_KEY"


class LiveRunnerError(ValueError):
    """Invalid live-runner configuration or inputs."""


def model_alias(condition: str) -> str:
    if condition not in CONDITIONS:
        raise LiveRunnerError("unknown condition %s" % condition)
    return "large" if condition.startswith("L") else "small"


def filter_requests(
    requests: Sequence[Mapping[str, Any]],
    *,
    conditions: Optional[Sequence[str]] = None,
    question_ids: Optional[Sequence[str]] = None,
    repeats: Optional[Sequence[int]] = None,
    max_requests: Optional[int] = None,
) -> List[Mapping[str, Any]]:
    condition_set = set(conditions) if conditions else None
    question_set = set(question_ids) if question_ids else None
    repeat_set = set(repeats) if repeats else None
    if condition_set is not None:
        unknown = condition_set - set(CONDITIONS)
        if unknown:
            raise LiveRunnerError("unknown conditions: %s" % sorted(unknown))
    if max_requests is not None and max_requests < 1:
        raise LiveRunnerError("max_requests must be >= 1 when provided")
    selected: List[Mapping[str, Any]] = []
    for request in requests:
        if condition_set is not None and request.get("condition") not in condition_set:
            continue
        if question_set is not None and request.get("question_id") not in question_set:
            continue
        if repeat_set is not None and request.get("repeat_index") not in repeat_set:
            continue
        selected.append(request)
    if max_requests is not None:
        return selected[:max_requests]
    return selected


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not str(value).strip():
        raise LiveRunnerError("missing required environment variable %s" % name)
    return str(value).strip()


def build_chat_payload(model_id: str, messages: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    return {
        "model": model_id,
        "messages": list(messages),
        **FIXED_GENERATION,
    }


def resolve_model_id(condition: str, small_model_id: str, large_model_id: str) -> str:
    return large_model_id if model_alias(condition) == "large" else small_model_id


def empty_latency() -> Dict[str, Optional[float]]:
    return {
        "retrieval": None,
        "model_http": None,
        "end_to_end": None,
        "first_token": None,
        "gateway": None,
        "client": None,
    }


def _token_pair(usage: Any) -> Dict[str, Any]:
    if not isinstance(usage, Mapping):
        return {"input": None, "output": None, "source": None}
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    input_tokens = prompt if isinstance(prompt, int) and not isinstance(prompt, bool) and prompt >= 0 else None
    output_tokens = (
        completion
        if isinstance(completion, int) and not isinstance(completion, bool) and completion >= 0
        else None
    )
    if input_tokens is None and output_tokens is None:
        return {"input": None, "output": None, "source": None}
    return {"input": input_tokens, "output": output_tokens, "source": "model_server"}


def _processing_cost(model_http_ms: Optional[float], hourly_rate_usd: Optional[float]) -> Optional[float]:
    computed = active_inference_processing_cost(model_http_ms, hourly_rate_usd)
    return float(computed) if computed is not None else None


def success_response(
    request: Mapping[str, Any],
    *,
    answer_text: str,
    model_http_ms: Optional[float],
    end_to_end_ms: float,
    tokens: Mapping[str, Any],
    hourly_rate_usd: Optional[float],
    retrieval_ms: Optional[float] = None,
    gateway_ms: Optional[float] = None,
    client_ms: Optional[float] = None,
    evidence_sha256: Optional[str] = None,
    evidence_source: str = "exported",
) -> Dict[str, Any]:
    latency = empty_latency()
    latency["retrieval"] = retrieval_ms
    latency["model_http"] = model_http_ms
    latency["end_to_end"] = end_to_end_ms
    latency["first_token"] = None
    latency["gateway"] = gateway_ms
    latency["client"] = client_ms
    row = {
        "request_sha256": request["request_sha256"],
        "question_id": request["question_id"],
        "condition": request["condition"],
        "repeat_index": request["repeat_index"],
        "status": "success",
        "answer_text": answer_text,
        "failure_code": None,
        "evidence_sha256": evidence_sha256 if evidence_sha256 is not None else request["evidence_sha256"],
        "evidence_source": evidence_source,
        "latency_ms": latency,
        "tokens": dict(tokens),
        "quality": None,
        "costs": {
            "market_generation_estimate": None,
            "allocated_processing_cost": _processing_cost(model_http_ms, hourly_rate_usd),
            "actual_rental_and_service_spend": None,
        },
    }
    if evidence_source == "edge":
        row["exported_evidence_sha256"] = request["evidence_sha256"]
    return row


def failed_response(
    request: Mapping[str, Any],
    *,
    failure_code: str,
    model_http_ms: Optional[float] = None,
    end_to_end_ms: Optional[float] = None,
    hourly_rate_usd: Optional[float] = None,
    evidence_sha256: Optional[str] = None,
    evidence_source: str = "exported",
) -> Dict[str, Any]:
    latency = empty_latency()
    latency["model_http"] = model_http_ms
    latency["end_to_end"] = end_to_end_ms
    latency["first_token"] = None
    row = {
        "request_sha256": request["request_sha256"],
        "question_id": request["question_id"],
        "condition": request["condition"],
        "repeat_index": request["repeat_index"],
        "status": "failed",
        "answer_text": None,
        "failure_code": failure_code,
        "evidence_sha256": evidence_sha256 if evidence_sha256 is not None else request["evidence_sha256"],
        "evidence_source": evidence_source,
        "latency_ms": latency,
        "tokens": {"input": None, "output": None, "source": None},
        "quality": None,
        "costs": {
            "market_generation_estimate": None,
            # Bill measured model HTTP time even when the answer parse fails.
            "allocated_processing_cost": _processing_cost(model_http_ms, hourly_rate_usd),
            "actual_rental_and_service_spend": None,
        },
    }
    if evidence_source == "edge":
        row["exported_evidence_sha256"] = request["evidence_sha256"]
    return row


def stable_edge_request_id(request_sha256: str) -> str:
    """Deterministic UUID so resume cannot double-bill the Edge Function."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "text-baseline-edge:%s" % request_sha256))


def _optional_ms(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)) or float(value) < 0:
        return None
    return float(value)


def _optional_token_count(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def parse_edge_success_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize the Edge Function success body (flat fields from handler.ts)."""
    answer = payload.get("answer_text")
    if not isinstance(answer, str) or not answer:
        raise LiveRunnerError("edge response missing answer_text")
    model_http = _optional_ms(payload.get("model_http_ms"))
    if model_http is None:
        # Accept nested shape only as a secondary compatibility path.
        latency = payload.get("latency_ms")
        if isinstance(latency, Mapping):
            model_http = _optional_ms(latency.get("model_http"))
    retrieval = _optional_ms(payload.get("retrieval_ms"))
    gateway = _optional_ms(payload.get("gateway_ms"))
    input_tokens = _optional_token_count(payload.get("input_tokens"))
    output_tokens = _optional_token_count(payload.get("output_tokens"))
    if input_tokens is None and output_tokens is None:
        nested_tokens = payload.get("tokens")
        if isinstance(nested_tokens, Mapping) and nested_tokens.get("source") == "model_server":
            input_tokens = _optional_token_count(nested_tokens.get("input"))
            output_tokens = _optional_token_count(nested_tokens.get("output"))
    evidence = payload.get("evidence_sha256")
    if not isinstance(evidence, str) or not evidence:
        raise LiveRunnerError("edge response missing evidence_sha256")
    tokens = {"input": input_tokens, "output": output_tokens, "source": None}
    if input_tokens is not None or output_tokens is not None:
        tokens["source"] = "model_server"
    return {
        "answer_text": answer,
        "model_http_ms": model_http,
        "retrieval_ms": retrieval,
        "gateway_ms": gateway,
        "tokens": tokens,
        "evidence_sha256": evidence,
    }


def build_session_metadata(
    *,
    transport: str,
    model_id: Optional[str],
    model_revision: Optional[str],
    quantization: Optional[str],
    server_version: Optional[str],
    gpu_type: Optional[str],
    hourly_rate_usd: Optional[float],
    session_id: Optional[str],
    pod_id: Optional[str],
    small_model_id: Optional[str] = None,
    large_model_id: Optional[str] = None,
    small_model_revision: Optional[str] = None,
    large_model_revision: Optional[str] = None,
) -> Dict[str, Any]:
    actuals = dict(session_actuals_template())
    return {
        "transport": transport,
        "session_id": session_id,
        "pod_id": pod_id,
        "gpu_type": gpu_type,
        "hourly_rate_usd": hourly_rate_usd,
        "model_id": model_id,
        "small_model_id": small_model_id,
        "large_model_id": large_model_id,
        "model_revision": model_revision,
        "small_model_revision": small_model_revision,
        "large_model_revision": large_model_revision,
        "quantization": quantization,
        "server_version": server_version,
        "fixed_generation": dict(FIXED_GENERATION),
        "session_actuals": actuals,
        "note": (
            "allocated_processing_cost uses measured model HTTP duration and hourly_rate_usd. "
            "session_actuals.rental_and_service_spend is operator-recorded total spend and is never "
            "copied into per-answer cost fields."
        ),
    }


def load_checkpoint(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"session": {}, "responses": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LiveRunnerError("checkpoint root must be an object")
    responses = payload.get("responses")
    if responses is None:
        responses = []
    if not isinstance(responses, list):
        raise LiveRunnerError("checkpoint responses must be a list")
    session = payload.get("session") or {}
    if not isinstance(session, dict):
        raise LiveRunnerError("checkpoint session must be an object")
    return {"session": session, "responses": responses}


def write_checkpoint(path: Path, session: Mapping[str, Any], responses: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = {"session": dict(session), "responses": list(responses)}
    tmp.write_text(canonical_json(payload) + "\n", encoding="utf-8")
    tmp.replace(path)


def completed_digests(responses: Sequence[Mapping[str, Any]]) -> Set[str]:
    done: Set[str] = set()
    for row in responses:
        digest = row.get("request_sha256")
        status = row.get("status")
        if isinstance(digest, str) and status in {"success", "failed"}:
            done.add(digest)
    return done


PostFn = Callable[..., Any]


def call_direct_model(
    request: Mapping[str, Any],
    *,
    base_url: str,
    bearer: str,
    model_id: str,
    timeout_s: float,
    max_response_bytes: int,
    hourly_rate_usd: Optional[float],
    post: PostFn = post_json,
) -> Dict[str, Any]:
    url = base_url.rstrip("/") + "/v1/chat/completions"
    payload = build_chat_payload(model_id, request["messages"])
    secrets = {MODEL_BEARER_ENV: bearer}
    headers = {"authorization": "Bearer %s" % bearer}
    wall_started = time.perf_counter()
    try:
        status, body, http_ms, _raw = post(
            url,
            payload,
            headers,
            timeout_s=timeout_s,
            max_response_bytes=max_response_bytes,
            secrets=secrets,
        )
    except HttpTransportError as exc:
        end_ms = (time.perf_counter() - wall_started) * 1000.0
        return failed_response(
            request,
            failure_code=exc.failure_code,
            end_to_end_ms=end_ms,
            hourly_rate_usd=hourly_rate_usd,
        )
    end_ms = (time.perf_counter() - wall_started) * 1000.0
    if status >= 300 and status < 400:
        return failed_response(
            request,
            failure_code="redirect_rejected",
            model_http_ms=http_ms,
            end_to_end_ms=end_ms,
            hourly_rate_usd=hourly_rate_usd,
        )
    if status < 200 or status >= 300:
        return failed_response(
            request,
            failure_code="model_http_error",
            model_http_ms=http_ms,
            end_to_end_ms=end_ms,
            hourly_rate_usd=hourly_rate_usd,
        )
    choices = body.get("choices")
    text = None
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], Mapping) else None
        if isinstance(message, Mapping):
            text = message.get("content")
    if not isinstance(text, str) or not text:
        return failed_response(
            request,
            failure_code="missing_answer_text",
            model_http_ms=http_ms,
            end_to_end_ms=end_ms,
            hourly_rate_usd=hourly_rate_usd,
        )
    return success_response(
        request,
        answer_text=text,
        model_http_ms=http_ms,
        end_to_end_ms=end_ms,
        tokens=_token_pair(body.get("usage")),
        hourly_rate_usd=hourly_rate_usd,
        client_ms=end_ms,
    )


def call_edge_function(
    request: Mapping[str, Any],
    *,
    edge_url: str,
    user_jwt: str,
    publishable_key: str,
    snapshot_id: str,
    embedding: Optional[Sequence[float]],
    timeout_s: float,
    max_response_bytes: int,
    hourly_rate_usd: Optional[float],
    post: PostFn = post_json,
) -> Dict[str, Any]:
    request_id = stable_edge_request_id(str(request["request_sha256"]))
    try:
        body = build_live_request(
            request_id,
            snapshot_id,
            request["question_text"],
            request["condition"],
            embedding=embedding,
        )
    except LiveClientError:
        return failed_response(request, failure_code="invalid_edge_payload", evidence_source="edge")
    secrets = {USER_JWT_ENV: user_jwt, PUBLISHABLE_KEY_ENV: publishable_key}
    headers = {
        "Authorization": "Bearer %s" % user_jwt,
        "apikey": publishable_key,
    }
    wall_started = time.perf_counter()
    try:
        status, payload, _http_ms, _raw = post(
            edge_url,
            body,
            headers,
            timeout_s=timeout_s,
            max_response_bytes=max_response_bytes,
            secrets=secrets,
        )
    except HttpTransportError as exc:
        end_ms = (time.perf_counter() - wall_started) * 1000.0
        return failed_response(
            request,
            failure_code=exc.failure_code,
            end_to_end_ms=end_ms,
            evidence_source="edge",
        )
    end_ms = (time.perf_counter() - wall_started) * 1000.0
    if status >= 300 and status < 400:
        return failed_response(
            request,
            failure_code="redirect_rejected",
            end_to_end_ms=end_ms,
            evidence_source="edge",
        )
    if status < 200 or status >= 300:
        return failed_response(
            request,
            failure_code="edge_http_error",
            end_to_end_ms=end_ms,
            evidence_source="edge",
        )
    try:
        parsed = parse_edge_success_payload(payload)
    except LiveRunnerError:
        return failed_response(
            request,
            failure_code="missing_answer_text",
            end_to_end_ms=end_ms,
            evidence_source="edge",
        )
    return success_response(
        request,
        answer_text=parsed["answer_text"],
        model_http_ms=parsed["model_http_ms"],
        end_to_end_ms=end_ms,
        tokens=parsed["tokens"],
        hourly_rate_usd=hourly_rate_usd,
        retrieval_ms=parsed["retrieval_ms"],
        gateway_ms=parsed["gateway_ms"],
        client_ms=end_ms,
        evidence_sha256=parsed["evidence_sha256"],
        evidence_source="edge",
    )


def load_embedding_lookup(path: Optional[Path]) -> Dict[str, List[float]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise LiveRunnerError("embedding bundle root must be an object")
    lookup: Dict[str, List[float]] = {}
    for group_key in ("questions", "items", "embeddings"):
        rows = payload.get(group_key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            key = row.get("id") or row.get("question_id")
            embedding = row.get("embedding")
            if not isinstance(key, str) or not isinstance(embedding, list):
                continue
            try:
                lookup[key] = [float(value) for value in embedding]
            except (TypeError, ValueError) as exc:
                raise LiveRunnerError("embedding for %s contains non-numeric values" % key) from exc
    return lookup


def _merge_session_actuals(
    base: Mapping[str, Any],
    checkpoint_actuals: Any,
    session_path: Path,
    *,
    resume: bool,
) -> Dict[str, Any]:
    merged = dict(base)
    if isinstance(checkpoint_actuals, dict):
        merged.update(checkpoint_actuals)
    if resume and session_path.exists():
        try:
            prior_session = json.loads(session_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prior_session = {}
        prior_actuals = prior_session.get("session_actuals") if isinstance(prior_session, dict) else None
        if isinstance(prior_actuals, dict):
            for key, value in prior_actuals.items():
                if value is not None:
                    merged[key] = value
    return merged


def validate_request_rows(requests: Sequence[Any]) -> None:
    required = {
        "request_sha256",
        "question_id",
        "condition",
        "repeat_index",
        "evidence_sha256",
        "messages",
        "question_text",
    }
    for index, row in enumerate(requests):
        if not isinstance(row, dict):
            raise LiveRunnerError("requests[%d] must be an object" % index)
        missing = sorted(required - set(row))
        if missing:
            raise LiveRunnerError("requests[%d] is missing required fields: %s" % (index, missing))
        messages = row.get("messages")
        if not isinstance(messages, list) or not messages:
            raise LiveRunnerError("requests[%d].messages must be a non-empty list" % index)
        for message_index, message in enumerate(messages):
            if not isinstance(message, dict) or "role" not in message or "content" not in message:
                raise LiveRunnerError(
                    "requests[%d].messages[%d] must include role and content" % (index, message_index)
                )


def run_live(
    requests: Sequence[Mapping[str, Any]],
    output_dir: Path,
    *,
    transport: str = "direct",
    conditions: Optional[Sequence[str]] = None,
    question_ids: Optional[Sequence[str]] = None,
    repeats: Optional[Sequence[int]] = None,
    max_requests: Optional[int] = None,
    hourly_rate_usd: Optional[float] = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    session_id: Optional[str] = None,
    pod_id: Optional[str] = None,
    gpu_type: Optional[str] = None,
    model_revision: Optional[str] = None,
    small_model_revision: Optional[str] = None,
    large_model_revision: Optional[str] = None,
    quantization: Optional[str] = None,
    server_version: Optional[str] = None,
    snapshot_id: Optional[str] = None,
    embeddings_path: Optional[Path] = None,
    post: PostFn = post_json,
    resume: bool = True,
) -> Dict[str, Any]:
    validate_request_rows(requests)
    if max_response_bytes < 1:
        raise LiveRunnerError("max_response_bytes must be >= 1")
    matched = filter_requests(
        requests,
        conditions=conditions,
        question_ids=question_ids,
        repeats=repeats,
        max_requests=None,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "responses.json"
    session_path = output_dir / "session.json"
    if not resume and checkpoint_path.exists():
        raise LiveRunnerError(
            "refusing to overwrite existing checkpoint without resume: %s" % checkpoint_path
        )
    checkpoint = load_checkpoint(checkpoint_path) if resume and checkpoint_path.exists() else {
        "session": {},
        "responses": [],
    }
    responses: List[Dict[str, Any]] = [dict(row) for row in checkpoint["responses"] if isinstance(row, dict)]
    done = completed_digests(responses) if resume else set()
    pending = [row for row in matched if row["request_sha256"] not in done]
    if max_requests is not None:
        if max_requests < 1:
            raise LiveRunnerError("max_requests must be >= 1 when provided")
        pending = pending[:max_requests]

    secrets: Dict[str, str] = {}
    small_model_id = None
    large_model_id = None
    base_url = None
    bearer = None
    edge_url = None
    user_jwt = None
    publishable_key = None
    if transport == "direct":
        base_url = require_env(MODEL_BASE_URL_ENV)
        bearer = require_env(MODEL_BEARER_ENV)
        secrets[MODEL_BEARER_ENV] = bearer
        small_model_id = require_env(SMALL_MODEL_ID_ENV)
        large_model_id = require_env(LARGE_MODEL_ID_ENV)
    elif transport == "edge":
        edge_url = require_env(EDGE_URL_ENV)
        user_jwt = require_env(USER_JWT_ENV)
        publishable_key = require_env(PUBLISHABLE_KEY_ENV)
        secrets[USER_JWT_ENV] = user_jwt
        secrets[PUBLISHABLE_KEY_ENV] = publishable_key
        if not snapshot_id:
            raise LiveRunnerError("edge transport requires --snapshot-id")
        if any(row.get("condition") in MEMORY_CONDITIONS for row in pending) and embeddings_path is None:
            raise LiveRunnerError("edge transport for S1/L1 requires --embeddings")
    else:
        raise LiveRunnerError("transport must be direct or edge")

    embeddings = load_embedding_lookup(embeddings_path)
    aliases = {model_alias(row["condition"]) for row in pending} | {
        model_alias(row["condition"])
        for row in matched
        if row["request_sha256"] in done
    }
    single_model_id = None
    if transport == "direct" and small_model_id and large_model_id and len(aliases) == 1:
        single_model_id = large_model_id if next(iter(aliases)) == "large" else small_model_id
    resolved_small_revision = small_model_revision or model_revision
    resolved_large_revision = large_model_revision or model_revision
    session = build_session_metadata(
        transport=transport,
        model_id=single_model_id,
        model_revision=model_revision,
        quantization=quantization,
        server_version=server_version,
        gpu_type=gpu_type,
        hourly_rate_usd=hourly_rate_usd,
        session_id=session_id,
        pod_id=pod_id,
        small_model_id=small_model_id,
        large_model_id=large_model_id,
        small_model_revision=resolved_small_revision,
        large_model_revision=resolved_large_revision,
    )
    session["session_actuals"] = _merge_session_actuals(
        session["session_actuals"],
        checkpoint.get("session", {}).get("session_actuals"),
        session_path,
        resume=resume,
    )

    for request in pending:
        digest = request["request_sha256"]
        if transport == "direct":
            assert base_url is not None and bearer is not None
            assert small_model_id is not None and large_model_id is not None
            model_id = resolve_model_id(request["condition"], small_model_id, large_model_id)
            row = call_direct_model(
                request,
                base_url=base_url,
                bearer=bearer,
                model_id=model_id,
                timeout_s=timeout_s,
                max_response_bytes=max_response_bytes,
                hourly_rate_usd=hourly_rate_usd,
                post=post,
            )
        else:
            assert (
                edge_url is not None
                and user_jwt is not None
                and publishable_key is not None
                and snapshot_id is not None
            )
            embedding = None
            if request["condition"] in MEMORY_CONDITIONS:
                embedding = embeddings.get(request["question_id"])
                if embedding is None:
                    row = failed_response(request, failure_code="missing_embedding", evidence_source="edge")
                    responses.append(row)
                    done.add(digest)
                    write_checkpoint(checkpoint_path, session, responses)
                    continue
            row = call_edge_function(
                request,
                edge_url=edge_url,
                user_jwt=user_jwt,
                publishable_key=publishable_key,
                snapshot_id=snapshot_id,
                embedding=embedding,
                timeout_s=timeout_s,
                max_response_bytes=max_response_bytes,
                hourly_rate_usd=hourly_rate_usd,
                post=post,
            )
        # Never persist secrets into checkpoint files.
        safe_row = json.loads(redact_secrets(canonical_json(row), secrets))
        responses.append(safe_row)
        done.add(digest)
        write_checkpoint(checkpoint_path, session, responses)

    write_checkpoint(checkpoint_path, session, responses)
    session_path.write_text(canonical_json(session) + "\n", encoding="utf-8")
    return {"session": session, "responses": responses, "checkpoint": str(checkpoint_path)}
