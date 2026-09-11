from __future__ import annotations

import unittest
from pathlib import Path

from experiments.text_baseline.fixtures import DATA_DIR, load_questions, load_scoring_anchors
from experiments.text_baseline.prompts import SYSTEM_PROMPT, PromptError, build_messages, prompt_contains_scoring_text
from experiments.text_baseline.run_builder import build_requests


class LeakageTests(unittest.TestCase):
    def test_questions_file_has_no_scoring_fields(self) -> None:
        for question in load_questions(DATA_DIR):
            self.assertNotIn("expected_answer", question)
            self.assertNotIn("anchors", question)

    def test_prompts_exclude_scoring_probe_tokens(self) -> None:
        anchors = load_scoring_anchors(DATA_DIR)
        bundle = build_requests(DATA_DIR, repeats=1, seed=0)
        for row in bundle["requests"]:
            self.assertFalse(prompt_contains_scoring_text(row["messages"], anchors))
            blob = row["messages"][1]["content"]
            self.assertNotIn("SCORING-ANCHOR", blob)
            self.assertNotIn("expected_answer", blob)

    def test_live_prompt_text_matches_python(self) -> None:
        prompt_ts = Path(__file__).resolve().parents[3] / "supabase" / "functions" / "text-baseline-pilot" / "prompt.ts"
        self.assertIn(SYSTEM_PROMPT, prompt_ts.read_text(encoding="utf-8"))

    def test_prompt_builder_rejects_scoring_keys(self) -> None:
        with self.assertRaises(PromptError):
            build_messages(
                {"text": "hello", "expected_answer": "secret"},
                [],
            )


if __name__ == "__main__":
    unittest.main()
