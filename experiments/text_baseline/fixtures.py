"""Load synthetic fixtures. Scoring anchors are never imported by prompt code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping

from experiments.text_baseline.constants import QUESTION_CATEGORIES
from experiments.text_baseline.hashing import sha256_json

DATA_DIR = Path(__file__).resolve().parent / "data"


class FixtureError(ValueError):
    """Invalid or incomplete fixture files."""


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_memory(data_dir: Path = DATA_DIR) -> Dict[str, Any]:
    payload = _read_json(data_dir / "memory.json")
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise FixtureError("memory.json must contain a non-empty items list")
    kinds = {item.get("kind") for item in items}
    if kinds != {"fact", "source_passage"}:
        raise FixtureError("memory items must include facts and source passages only")
    for item in items:
        if not item.get("id") or not item.get("content"):
            raise FixtureError("each memory item needs id and content")
    return payload


def load_questions(data_dir: Path = DATA_DIR) -> List[Dict[str, Any]]:
    payload = _read_json(data_dir / "questions.json")
    questions = payload.get("questions")
    if not isinstance(questions, list) or len(questions) != 12:
        raise FixtureError("questions.json must contain exactly 12 questions")
    counts = {category: 0 for category in QUESTION_CATEGORIES}
    seen = set()
    for question in questions:
        qid = question.get("id")
        category = question.get("category")
        text = question.get("text")
        if qid in seen or not text or category not in counts:
            raise FixtureError("questions must have unique ids, text, and a known category")
        if any(key in question for key in ("expected_answer", "anchors", "scoring")):
            raise FixtureError("questions.json must not contain scoring fields")
        seen.add(qid)
        counts[category] += 1
    if any(count != 4 for count in counts.values()):
        raise FixtureError("need four questions in each category")
    return questions


def load_scoring_anchors(data_dir: Path = DATA_DIR) -> Dict[str, Any]:
    payload = _read_json(data_dir / "scoring_anchors.json")
    anchors = payload.get("anchors")
    if not isinstance(anchors, dict) or len(anchors) != 12:
        raise FixtureError("scoring_anchors.json must map all 12 question ids")
    return payload


def load_market_rates_example(data_dir: Path = DATA_DIR) -> Dict[str, Any]:
    return _read_json(data_dir / "market_rates.example.json")


def fixture_hashes(data_dir: Path = DATA_DIR) -> Mapping[str, str]:
    memory = load_memory(data_dir)
    questions = load_questions(data_dir)
    return {
        "memory_sha256": sha256_json(memory),
        "questions_sha256": sha256_json({"questions": questions}),
        "scoring_anchors_sha256": sha256_json(load_scoring_anchors(data_dir)),
    }
