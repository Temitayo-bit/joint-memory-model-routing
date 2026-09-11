"""Canonical JSON hashing for manifests, requests, fixtures, and evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from experiments.text_baseline.constants import CANONICAL_JSON_SEPARATORS


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=CANONICAL_JSON_SEPARATORS,
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))
