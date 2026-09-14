"""Shared request construction for mock, export, and import."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from experiments.text_baseline.constants import (
    FIXED_GENERATION,
    MEMORY_CONDITIONS,
    NO_MEMORY_CONDITIONS,
    RETRIEVAL_CONFIG,
)
from experiments.text_baseline.costs import empty_cost_fields, session_actuals_template
from experiments.text_baseline.fixtures import (
    dataset_identity,
    fixture_hashes,
    load_dataset_manifest,
    load_memory,
    load_questions,
)
from experiments.text_baseline.hashing import sha256_json
from experiments.text_baseline.prompts import build_messages
from experiments.text_baseline.retrieval import evidence_hash, retrieve_for_condition
from experiments.text_baseline.schedule import build_cells, expected_cell_count, schedule_hash


def empty_measurements() -> Dict[str, Any]:
    return {
        "latency_ms": {
            "retrieval": None,
            "model_http": None,
            "end_to_end": None,
            "first_token": None,
            "gateway": None,
            "client": None,
        },
        "tokens": {"input": None, "output": None, "source": None},
        "quality": None,
        "costs": dict(empty_cost_fields()),
    }


def request_digest(request: Mapping[str, Any]) -> str:
    """Hash the canonical request fields. Stored digests are never trusted alone."""
    payload: Dict[str, Any] = {
        "repeat_index": request["repeat_index"],
        "question_id": request["question_id"],
        "condition": request["condition"],
        "messages": request["messages"],
        "evidence_sha256": request["evidence_sha256"],
    }
    # Legacy pilot digests omit generation_seed so recorded artifacts stay reproducible.
    if "generation_seed" in request:
        payload["generation_seed"] = request["generation_seed"]
    return sha256_json(payload)


def build_requests(
    data_dir,
    repeats: int = 1,
    seed: int = 0,
) -> Dict[str, Any]:
    questions = load_questions(data_dir)
    memory = load_memory(data_dir)
    hashes = dict(fixture_hashes(data_dir))
    identity = dataset_identity(data_dir)
    manifest_meta = load_dataset_manifest(data_dir)
    generation_seeds: Optional[Sequence[int]]
    if manifest_meta is None:
        generation_seeds = None
        generation_seed_count = 1
    else:
        generation_seeds = list(manifest_meta["allowed_generation_seeds"])
        generation_seed_count = len(generation_seeds)
    cells = build_cells(
        questions,
        repeats=repeats,
        seed=seed,
        generation_seeds=generation_seeds,
    )
    evidence_by_question = {}
    requests: List[Dict[str, Any]] = []
    for cell in cells:
        condition = cell["condition"]
        question_id = cell["question_id"]
        if condition in MEMORY_CONDITIONS:
            if question_id not in evidence_by_question:
                evidence_by_question[question_id] = retrieve_for_condition(
                    condition,
                    cell["question_text"],
                    memory,
                )
            evidence = evidence_by_question[question_id]
        elif condition in NO_MEMORY_CONDITIONS:
            # S0/L0 never invoke retrieval plumbing.
            evidence = []
        else:
            raise ValueError("unknown condition %s" % condition)
        question_payload = {
            "id": question_id,
            "text": cell["question_text"],
            "category": cell.get("question_category"),
        }
        if "question_stratum" in cell:
            question_payload["stratum"] = cell["question_stratum"]
        messages = build_messages(question_payload, evidence)
        request: Dict[str, Any] = {
            "repeat_index": cell["repeat_index"],
            "question_id": question_id,
            "question_category": cell.get("question_category"),
            "question_text": cell["question_text"],
            "condition": condition,
            "messages": messages,
            "evidence": evidence,
            "evidence_sha256": evidence_hash(evidence),
            "retrieval_invoked": condition in MEMORY_CONDITIONS,
            "dataset_id": identity["dataset_id"],
            "dataset_version": identity["dataset_version"],
            "dataset_split": identity["dataset_split"],
            "schedule_seed": seed,
        }
        if "question_stratum" in cell:
            request["question_stratum"] = cell["question_stratum"]
        if "generation_seed" in cell:
            request["generation_seed"] = cell["generation_seed"]
        request["request_sha256"] = request_digest(request)
        requests.append(request)
    expected = expected_cell_count(
        repeats,
        question_count=len(questions),
        generation_seed_count=generation_seed_count,
    )
    manifest = {
        "experiment": "text_baseline_fixed_conditions",
        "not_a_research_result": True,
        "repeats": repeats,
        "seed": seed,
        "schedule_seed": seed,
        "cell_count": len(requests),
        "expected_cell_count": expected,
        "schedule_sha256": schedule_hash(cells),
        "fixture_hashes": hashes,
        "fixed_generation": dict(FIXED_GENERATION),
        "retrieval": dict(RETRIEVAL_CONFIG),
        "session_actuals": dict(session_actuals_template()),
        "requests_sha256": sha256_json([row["request_sha256"] for row in requests]),
        "dataset_id": identity["dataset_id"],
        "dataset_version": identity["dataset_version"],
        "dataset_split": identity["dataset_split"],
    }
    if generation_seeds is not None:
        manifest["allowed_generation_seeds"] = list(generation_seeds)
        manifest["generation_seed_count"] = generation_seed_count
    return {"manifest": manifest, "requests": requests}


def mock_record(request: Mapping[str, Any]) -> Dict[str, Any]:
    record = {
        "request_sha256": request["request_sha256"],
        "question_id": request["question_id"],
        "condition": request["condition"],
        "repeat_index": request["repeat_index"],
        "status": "mock",
        "answer_text": "MOCK_ANSWER not a research result for %s/%s"
        % (request["question_id"], request["condition"]),
        "failure_code": None,
        "evidence_sha256": request["evidence_sha256"],
        "dataset_id": request.get("dataset_id"),
        "dataset_version": request.get("dataset_version"),
        "dataset_split": request.get("dataset_split"),
    }
    if "generation_seed" in request:
        record["generation_seed"] = request["generation_seed"]
    record.update(empty_measurements())
    return record
