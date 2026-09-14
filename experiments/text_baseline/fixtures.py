"""Load synthetic fixtures. Scoring anchors are never imported by prompt code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from experiments.text_baseline.constants import (
    BENCHMARK_V2_DIAGNOSTIC_TAGS,
    BENCHMARK_V2_GENERATION_SEEDS,
    BENCHMARK_V2_STRATA,
    LEGACY_DATASET_ID,
    LEGACY_PER_CATEGORY,
    LEGACY_QUESTION_COUNT,
    MAX_REQUIRED_EVIDENCE_IDS,
    QUESTION_CATEGORIES,
)
from experiments.text_baseline.hashing import sha256_json

DATA_DIR = Path(__file__).resolve().parent / "data"
DATASETS_DIR = Path(__file__).resolve().parent / "datasets"
SCORING_ONLY_QUESTION_KEYS = frozenset(
    {
        "expected_answer",
        "expected_conclusion",
        "anchors",
        "scoring",
        "required_evidence_ids",
        "diagnostic_tags",
        "rubric",
        "reference_answer",
        "gold",
        "keywords",
    }
)


class FixtureError(ValueError):
    """Invalid or incomplete fixture files."""


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def resolve_data_dir(data_dir: Optional[Path] = None, dataset: Optional[str] = None) -> Path:
    if data_dir is not None and dataset is not None:
        raise FixtureError("pass only one of data_dir or dataset")
    if dataset:
        path = DATASETS_DIR / dataset
        if not path.is_dir():
            raise FixtureError("unknown dataset %s" % dataset)
        return path
    if data_dir is None:
        return DATA_DIR
    return Path(data_dir)


def load_dataset_manifest(data_dir: Path = DATA_DIR) -> Optional[Dict[str, Any]]:
    path = Path(data_dir) / "manifest.json"
    if not path.exists():
        return None
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise FixtureError("manifest.json must be an object")
    required = (
        "dataset_id",
        "version",
        "split",
        "question_count",
        "stratum_counts",
        "allowed_generation_seeds",
    )
    for key in required:
        if key not in payload:
            raise FixtureError("manifest.json missing %s" % key)
    if not isinstance(payload["dataset_id"], str) or not payload["dataset_id"].strip():
        raise FixtureError("manifest.dataset_id must be a non-empty string")
    if not isinstance(payload["version"], str) or not payload["version"].strip():
        raise FixtureError("manifest.version must be a non-empty string")
    if payload["split"] not in {"dev", "eval"}:
        raise FixtureError("manifest.split must be dev or eval")
    if not isinstance(payload["question_count"], int) or isinstance(payload["question_count"], bool):
        raise FixtureError("manifest.question_count must be an integer")
    stratum_counts = payload["stratum_counts"]
    if not isinstance(stratum_counts, dict):
        raise FixtureError("manifest.stratum_counts must be an object")
    if set(stratum_counts) != set(BENCHMARK_V2_STRATA):
        raise FixtureError("manifest.stratum_counts must include strata A–D only")
    total = 0
    for stratum in BENCHMARK_V2_STRATA:
        count = stratum_counts[stratum]
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise FixtureError("manifest stratum counts must be positive integers")
        total += count
    if total != payload["question_count"]:
        raise FixtureError("manifest stratum counts must sum to question_count")
    seeds = payload["allowed_generation_seeds"]
    if not isinstance(seeds, list) or not seeds:
        raise FixtureError("manifest.allowed_generation_seeds must be a non-empty list")
    if any(not isinstance(seed, int) or isinstance(seed, bool) for seed in seeds):
        raise FixtureError("manifest.allowed_generation_seeds must be integers")
    if tuple(seeds) != BENCHMARK_V2_GENERATION_SEEDS:
        raise FixtureError(
            "benchmark-v2 allowed_generation_seeds must be exactly %s"
            % list(BENCHMARK_V2_GENERATION_SEEDS)
        )
    if len(set(seeds)) != len(seeds):
        raise FixtureError("manifest.allowed_generation_seeds must be unique")
    return payload


def load_memory(data_dir: Path = DATA_DIR) -> Dict[str, Any]:
    payload = _read_json(Path(data_dir) / "memory.json")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise FixtureError("memory.json must contain a non-empty items list")
    kinds = {item.get("kind") for item in items}
    if kinds != {"fact", "source_passage"}:
        raise FixtureError("memory items must include facts and source passages only")
    seen: Set[str] = set()
    for item in items:
        item_id = item.get("id")
        if not item_id or not item.get("content"):
            raise FixtureError("each memory item needs id and content")
        if item_id in seen:
            raise FixtureError("duplicate memory item id %s" % item_id)
        seen.add(str(item_id))
    return payload


def _validate_legacy_questions(questions: Sequence[Mapping[str, Any]]) -> None:
    if len(questions) != LEGACY_QUESTION_COUNT:
        raise FixtureError("questions.json must contain exactly 12 questions")
    counts = {category: 0 for category in QUESTION_CATEGORIES}
    seen: Set[str] = set()
    for question in questions:
        qid = question.get("id")
        category = question.get("category")
        text = question.get("text")
        if qid in seen or not text or category not in counts:
            raise FixtureError("questions must have unique ids, text, and a known category")
        if SCORING_ONLY_QUESTION_KEYS.intersection(question.keys()):
            raise FixtureError("questions.json must not contain scoring fields")
        seen.add(str(qid))
        counts[category] += 1
    if any(count != LEGACY_PER_CATEGORY for count in counts.values()):
        raise FixtureError("need four questions in each category")


def _validate_benchmark_questions(
    questions: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
) -> None:
    if len(questions) != manifest["question_count"]:
        raise FixtureError(
            "questions.json must contain exactly %s questions" % manifest["question_count"]
        )
    counts = {stratum: 0 for stratum in BENCHMARK_V2_STRATA}
    seen: Set[str] = set()
    for question in questions:
        qid = question.get("id")
        stratum = question.get("stratum")
        text = question.get("text")
        if not qid or qid in seen or not text:
            raise FixtureError("questions must have unique ids and non-empty text")
        if stratum not in counts:
            raise FixtureError("unknown stratum %s" % stratum)
        if SCORING_ONLY_QUESTION_KEYS.intersection(question.keys()):
            raise FixtureError("questions.json must not contain scoring fields")
        if "category" in question and question["category"] not in QUESTION_CATEGORIES:
            # Benchmark questions may omit legacy categories; if present, keep them valid.
            if question["category"] != stratum:
                raise FixtureError("optional category must match stratum for benchmark-v2")
        seen.add(str(qid))
        counts[stratum] += 1
    expected = manifest["stratum_counts"]
    for stratum in BENCHMARK_V2_STRATA:
        if counts[stratum] != expected[stratum]:
            raise FixtureError(
                "stratum %s requires %s questions, found %s"
                % (stratum, expected[stratum], counts[stratum])
            )


def load_questions(data_dir: Path = DATA_DIR) -> List[Dict[str, Any]]:
    payload = _read_json(Path(data_dir) / "questions.json")
    questions = payload.get("questions")
    if not isinstance(questions, list):
        raise FixtureError("questions.json must contain a questions list")
    manifest = load_dataset_manifest(data_dir)
    if manifest is None:
        _validate_legacy_questions(questions)
    else:
        _validate_benchmark_questions(questions, manifest)
    return list(questions)


def _validate_legacy_anchors(anchors: Mapping[str, Any], question_ids: Set[str]) -> None:
    if set(anchors) != question_ids or len(anchors) != LEGACY_QUESTION_COUNT:
        raise FixtureError("scoring_anchors.json must map all 12 question ids")


def _validate_benchmark_anchors(
    anchors: Mapping[str, Any],
    questions: Sequence[Mapping[str, Any]],
    memory_ids: Set[str],
) -> None:
    question_ids = {str(question["id"]) for question in questions}
    if set(anchors) != question_ids:
        raise FixtureError("scoring_anchors.json must map every question id exactly once")
    by_id = {str(question["id"]): question for question in questions}
    for qid, spec in anchors.items():
        if not isinstance(spec, Mapping):
            raise FixtureError("each scoring anchor must be an object")
        if SCORING_ONLY_QUESTION_KEYS.isdisjoint(spec.keys()) and "expected_answer" not in spec:
            raise FixtureError("anchor for %s is missing scoring fields" % qid)
        markers = spec.get("must_not_appear_in_prompts")
        if not isinstance(markers, list) or not markers:
            raise FixtureError("anchor %s needs must_not_appear_in_prompts markers" % qid)
        required = spec.get("required_evidence_ids", [])
        if required is None:
            required = []
        if not isinstance(required, list):
            raise FixtureError("required_evidence_ids must be a list for %s" % qid)
        if len(required) > MAX_REQUIRED_EVIDENCE_IDS:
            raise FixtureError(
                "anchor %s may require at most %s evidence ids" % (qid, MAX_REQUIRED_EVIDENCE_IDS)
            )
        if any(not isinstance(item_id, str) or not item_id for item_id in required):
            raise FixtureError("required_evidence_ids must be non-empty strings")
        unknown = set(required) - memory_ids
        if unknown:
            raise FixtureError("anchor %s references unknown evidence ids %s" % (qid, sorted(unknown)))
        stratum = by_id[qid]["stratum"]
        if stratum in {"A", "B"} and required:
            raise FixtureError("no-memory strata must not require evidence ids (%s)" % qid)
        if stratum in {"C", "D"} and not required and not spec.get("allows_empty_evidence"):
            # Memory strata normally require evidence; abstention items may set allows_empty_evidence.
            if "unsupported-information abstention" not in set(spec.get("diagnostic_tags") or []):
                raise FixtureError("memory strata anchors need required_evidence_ids (%s)" % qid)
        tags = spec.get("diagnostic_tags") or []
        if not isinstance(tags, list) or not tags:
            raise FixtureError("anchor %s needs diagnostic_tags" % qid)
        unknown_tags = set(tags) - BENCHMARK_V2_DIAGNOSTIC_TAGS
        if unknown_tags:
            raise FixtureError("anchor %s has unknown diagnostic tags %s" % (qid, sorted(unknown_tags)))


def load_scoring_anchors(data_dir: Path = DATA_DIR) -> Dict[str, Any]:
    payload = _read_json(Path(data_dir) / "scoring_anchors.json")
    anchors = payload.get("anchors")
    if not isinstance(anchors, dict):
        raise FixtureError("scoring_anchors.json must contain an anchors object")
    if payload.get("not_for_prompts") is not True:
        raise FixtureError("scoring_anchors.json must declare not_for_prompts=true")
    questions = load_questions(data_dir)
    question_ids = {str(question["id"]) for question in questions}
    manifest = load_dataset_manifest(data_dir)
    if manifest is None:
        _validate_legacy_anchors(anchors, question_ids)
    else:
        memory = load_memory(data_dir)
        memory_ids = {str(item["id"]) for item in memory["items"]}
        _validate_benchmark_anchors(anchors, questions, memory_ids)
    return payload


def load_market_rates_example(data_dir: Path = DATA_DIR) -> Dict[str, Any]:
    return _read_json(Path(data_dir) / "market_rates.example.json")


def fixture_hashes(data_dir: Path = DATA_DIR) -> Mapping[str, str]:
    memory = load_memory(data_dir)
    questions = load_questions(data_dir)
    hashes = {
        "memory_sha256": sha256_json(memory),
        "questions_sha256": sha256_json({"questions": questions}),
        "scoring_anchors_sha256": sha256_json(load_scoring_anchors(data_dir)),
    }
    manifest = load_dataset_manifest(data_dir)
    if manifest is not None:
        hashes["manifest_sha256"] = sha256_json(manifest)
    return hashes


def dataset_identity(data_dir: Path = DATA_DIR) -> Dict[str, Any]:
    manifest = load_dataset_manifest(data_dir)
    if manifest is None:
        memory = load_memory(data_dir)
        return {
            "dataset_id": memory.get("snapshot_label", LEGACY_DATASET_ID),
            "dataset_version": "1",
            "dataset_split": "legacy",
            "allowed_generation_seeds": None,
            "question_count": LEGACY_QUESTION_COUNT,
        }
    return {
        "dataset_id": manifest["dataset_id"],
        "dataset_version": manifest["version"],
        "dataset_split": manifest["split"],
        "allowed_generation_seeds": list(manifest["allowed_generation_seeds"]),
        "question_count": manifest["question_count"],
    }


def assert_split_disjointness(
    left_dir: Path,
    right_dir: Path,
) -> Tuple[Set[str], Set[str]]:
    left_questions = {str(row["id"]) for row in load_questions(left_dir)}
    right_questions = {str(row["id"]) for row in load_questions(right_dir)}
    left_evidence = {str(item["id"]) for item in load_memory(left_dir)["items"]}
    right_evidence = {str(item["id"]) for item in load_memory(right_dir)["items"]}
    question_overlap = left_questions & right_questions
    evidence_overlap = left_evidence & right_evidence
    if question_overlap:
        raise FixtureError("question id overlap across splits: %s" % sorted(question_overlap))
    if evidence_overlap:
        raise FixtureError("evidence id overlap across splits: %s" % sorted(evidence_overlap))
    return left_questions | right_questions, left_evidence | right_evidence
