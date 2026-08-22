from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from recoveriq_policy.models import CandidatePrediction, EconomicScore


def expected_recovered_minor(probability: Decimal, payment_amount_minor: int) -> int:
    if payment_amount_minor <= 0:
        raise ValueError("payment amount must be positive")
    value = (probability * Decimal(payment_amount_minor)).quantize(
        Decimal("1"),
        rounding=ROUND_HALF_UP,
    )
    return int(value)


def economic_score(
    prediction: CandidatePrediction,
    payment_amount_minor: int,
) -> EconomicScore:
    action = prediction.candidate.recovery_action
    expected = expected_recovered_minor(
        prediction.calibrated_probability,
        payment_amount_minor,
    )
    return EconomicScore(
        expected_recovered_minor=expected,
        intervention_cost_minor=action.intervention_cost_minor,
        friction_cost_minor=action.friction_cost_minor,
        erv_minor=expected - action.intervention_cost_minor - action.friction_cost_minor,
    )
