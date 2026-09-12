"""Three separate cost measures. Missing values stay null; nothing is invented."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional


class CostError(ValueError):
    """Malformed token counts or documented rates."""


def _as_non_negative_number(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise CostError("%s must be a number" % label)
    if isinstance(value, float) and value != value:  # NaN
        raise CostError("%s must be finite" % label)
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CostError("%s is not a number" % label) from exc
    if not parsed.is_finite():
        raise CostError("%s must be finite" % label)
    if parsed < 0:
        raise CostError("%s must be >= 0" % label)
    return parsed


def market_generation_estimate(
    input_tokens: Any,
    output_tokens: Any,
    input_rate_per_million: Any,
    output_rate_per_million: Any,
) -> Optional[str]:
    """Return a decimal string, or None when any input is missing.

    Never used as processing cost or as actual rental/service spending.
    """
    if any(
        value is None
        for value in (input_tokens, output_tokens, input_rate_per_million, output_rate_per_million)
    ):
        return None
    tokens_in = _as_non_negative_number(input_tokens, "input_tokens")
    tokens_out = _as_non_negative_number(output_tokens, "output_tokens")
    rate_in = _as_non_negative_number(input_rate_per_million, "input_rate_per_million")
    rate_out = _as_non_negative_number(output_rate_per_million, "output_rate_per_million")
    million = Decimal("1000000")
    estimate = (tokens_in / million) * rate_in + (tokens_out / million) * rate_out
    return format(estimate, "f")


def allocated_processing_cost(
    session_processing_total: Any,
    completed_answers: Any,
) -> Optional[str]:
    """Split an operator-supplied processing total equally. Does not invent the total."""
    if session_processing_total is None or completed_answers is None:
        return None
    total = _as_non_negative_number(session_processing_total, "session_processing_total")
    count = _as_non_negative_number(completed_answers, "completed_answers")
    if count == 0:
        raise CostError("cannot allocate processing cost over zero answers")
    if count != count.to_integral_value():
        raise CostError("completed_answers must be an integer")
    return format(total / count, "f")


def active_inference_processing_cost(
    model_http_ms: Any,
    hourly_rate_usd: Any,
) -> Optional[str]:
    """GPU processing cost for one answer from measured model HTTP duration.

    Equals (model_http_ms / 3_600_000) * hourly_rate_usd.
    Never copies session rental/service spending into this field.
    """
    if model_http_ms is None or hourly_rate_usd is None:
        return None
    duration_ms = _as_non_negative_number(model_http_ms, "model_http_ms")
    rate = _as_non_negative_number(hourly_rate_usd, "hourly_rate_usd")
    cost = (duration_ms / Decimal("3600000")) * rate
    return format(cost, "f")


def empty_cost_fields() -> Mapping[str, None]:
    return {
        "market_generation_estimate": None,
        "allocated_processing_cost": None,
        "actual_rental_and_service_spend": None,
    }


def session_actuals_template() -> Mapping[str, None]:
    return {
        "rental_and_service_spend": None,
        "setup": None,
        "idle": None,
        "memory_preparation": None,
        "storage": None,
        "later_speech_processing": None,
        "note": "Actuals are operator-recorded. They are not derived from token estimates.",
    }
