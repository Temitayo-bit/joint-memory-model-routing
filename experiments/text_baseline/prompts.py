"""Prompt assembly. Scoring anchors must never be passed into this module."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

FORBIDDEN_PROMPT_KEYS = frozenset(
    {
        "expected_answer",
        "anchors",
        "scoring",
        "reference_answer",
        "gold",
        "keywords",
    }
)

SYSTEM_PROMPT = (
    "Answer the question. If memory evidence is listed, you may use those "
    "facts and source passages. If no memory evidence is listed, answer from "
    "general knowledge and do not invent private lab facts."
)


class PromptError(ValueError):
    """Prompt inputs included scoring data or invalid fields."""


def _reject_scoring(payload: Mapping[str, Any]) -> None:
    banned = FORBIDDEN_PROMPT_KEYS.intersection(payload.keys())
    if banned:
        raise PromptError("scoring fields are not allowed in prompts: %s" % sorted(banned))


def render_user_message(question_text: str, evidence: Sequence[Mapping[str, Any]]) -> str:
    lines = []
    if evidence:
        lines.append("Memory evidence:")
        for item in evidence:
            lines.append("- [%s] %s" % (item["kind"], item["content"]))
        lines.append("")
    else:
        lines.append("Memory evidence: none")
        lines.append("")
    lines.append("Question:")
    lines.append(question_text)
    return "\n".join(lines)


def build_messages(
    question: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
) -> List[Dict[str, str]]:
    _reject_scoring(question)
    for item in evidence:
        if isinstance(item, Mapping):
            _reject_scoring(item)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": render_user_message(str(question["text"]), evidence)},
    ]


def prompt_contains_scoring_text(messages: Sequence[Mapping[str, str]], anchors: Mapping[str, Any]) -> bool:
    blob = "\n".join(message.get("content", "") for message in messages).lower()
    for spec in anchors.get("anchors", {}).values():
        for marker in spec.get("must_not_appear_in_prompts", []):
            if str(marker).lower() in blob:
                return True
    return False
