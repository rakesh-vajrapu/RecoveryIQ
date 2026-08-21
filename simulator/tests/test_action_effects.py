from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from recoveriq_simulator.enums import (
    ActionType,
    IncidentSeverity,
    InstrumentState,
    PaymentMethod,
    TrueFailureCause,
)
from recoveriq_simulator.environment import AttributionLedger, RecoveryProbabilityModel
from recoveriq_simulator.ground_truth import (
    CustomerGroundTruth,
    DegradationIncidentGroundTruth,
    PaymentGroundTruth,
)
from recoveriq_simulator.observation import RecoveryAction
from recoveriq_simulator.results import RecoveryAttribution

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _customer() -> CustomerGroundTruth:
    return CustomerGroundTruth(
        customer_id="SIM_CUSTOMER_TEST",
        liquidity_propensity=0.5,
        historical_reliability=0.7,
        nudge_responsiveness=0.6,
        payment_method_stability=0.8,
        instrument_update_propensity=0.7,
        retry_sensitivity=0.6,
    )


def _truth(cause: TrueFailureCause, state: InstrumentState) -> PaymentGroundTruth:
    return PaymentGroundTruth(
        payment_id="SIM_PAYMENT_TEST",
        initial_success=False,
        initial_success_probability=0.2,
        true_failure_cause=cause,
        instrument_state=state,
        incident_id=None,
    )


def _action(action_type: ActionType, hours: float) -> RecoveryAction:
    return RecoveryAction(
        action_id=f"SIM_ACTION_{action_type.value}",
        action_type=action_type,
        execute_at=NOW + timedelta(hours=hours),
        scheduled_delay_hours=hours,
        attempt_number=1,
        intervention_cost_minor=0,
        friction_cost_minor=0,
    )


def test_recovery_timing_changes_probability() -> None:
    model = RecoveryProbabilityModel()
    truth = _truth(TrueFailureCause.LIQUIDITY_SHORTFALL, InstrumentState.VALID)
    now = model.probability(
        truth=truth,
        customer=_customer(),
        action=_action(ActionType.RETRY_NOW, 0),
        incident=None,
        hours_since_failure=0,
        retry_number=1,
        prior_contacts=0,
    )
    later = model.probability(
        truth=truth,
        customer=_customer(),
        action=_action(ActionType.RETRY_LATER, 24),
        incident=None,
        hours_since_failure=24,
        retry_number=1,
        prior_contacts=0,
    )
    assert later > now


def test_incident_clearance_changes_retry_probability() -> None:
    model = RecoveryProbabilityModel()
    truth = _truth(TrueFailureCause.ISSUER_DEGRADATION, InstrumentState.VALID)
    incident = DegradationIncidentGroundTruth(
        incident_id="SIM_INCIDENT_TEST",
        start_at=NOW,
        end_at=NOW + timedelta(hours=8),
        payment_method=PaymentMethod.UPI,
        issuer="ISSUER_B",
        severity_class=IncidentSeverity.CRITICAL,
        severity=0.7,
        traffic_exposure_fraction=1.0,
        error_shift_strength=1.0,
        baseline_health=0.95,
        degraded_health=0.285,
        dominant_failure_cause=TrueFailureCause.ISSUER_DEGRADATION,
    )
    during = model.probability(
        truth=truth,
        customer=_customer(),
        action=_action(ActionType.RETRY_LATER, 2),
        incident=incident,
        hours_since_failure=2,
        retry_number=1,
        prior_contacts=0,
    )
    after = model.probability(
        truth=truth,
        customer=_customer(),
        action=_action(ActionType.RETRY_LATER, 12),
        incident=None,
        hours_since_failure=12,
        retry_number=1,
        prior_contacts=0,
    )
    assert after > during


def test_expired_instrument_differs_from_temporary_network_failure() -> None:
    model = RecoveryProbabilityModel()
    expired = model.probability(
        truth=_truth(TrueFailureCause.INVALID_INSTRUMENT, InstrumentState.EXPIRED),
        customer=_customer(),
        action=_action(ActionType.RETRY_LATER, 6),
        incident=None,
        hours_since_failure=6,
        retry_number=1,
        prior_contacts=0,
    )
    network = model.probability(
        truth=_truth(TrueFailureCause.NETWORK_INSTABILITY, InstrumentState.VALID),
        customer=_customer(),
        action=_action(ActionType.RETRY_LATER, 6),
        incident=None,
        hours_since_failure=6,
        retry_number=1,
        prior_contacts=0,
    )
    assert network > expired * 10


def test_method_update_is_more_useful_than_retry_for_expired_instrument() -> None:
    model = RecoveryProbabilityModel()
    truth = _truth(TrueFailureCause.INVALID_INSTRUMENT, InstrumentState.EXPIRED)
    retry = model.probability(
        truth=truth,
        customer=_customer(),
        action=_action(ActionType.RETRY_LATER, 6),
        incident=None,
        hours_since_failure=6,
        retry_number=1,
        prior_contacts=0,
    )
    update = model.probability(
        truth=truth,
        customer=_customer(),
        action=_action(ActionType.REQUEST_PAYMENT_METHOD_UPDATE, 1),
        incident=None,
        hours_since_failure=1,
        retry_number=0,
        prior_contacts=0,
    )
    assert update > retry * 20


def test_nudge_does_not_repair_infrastructure_failure() -> None:
    model = RecoveryProbabilityModel()
    for cause in (
        TrueFailureCause.ISSUER_DEGRADATION,
        TrueFailureCause.NETWORK_INSTABILITY,
    ):
        probability = model.probability(
            truth=_truth(cause, InstrumentState.VALID),
            customer=_customer(),
            action=_action(ActionType.SEND_NUDGE, 0.1),
            incident=None,
            hours_since_failure=0.1,
            retry_number=0,
            prior_contacts=0,
        )
        assert probability < 0.01


def test_responsive_customer_benefits_more_from_nudge() -> None:
    model = RecoveryProbabilityModel()
    truth = _truth(TrueFailureCause.CUSTOMER_CONFIRMATION, InstrumentState.VALID)
    low = _customer().model_copy(update={"nudge_responsiveness": 0.05})
    high = _customer().model_copy(update={"nudge_responsiveness": 0.95})
    high_probability = model.probability(
        truth=truth,
        customer=high,
        action=_action(ActionType.SEND_NUDGE, 0.1),
        incident=None,
        hours_since_failure=0.1,
        retry_number=0,
        prior_contacts=0,
    )
    low_probability = model.probability(
        truth=truth,
        customer=low,
        action=_action(ActionType.SEND_NUDGE, 0.1),
        incident=None,
        hours_since_failure=0.1,
        retry_number=0,
        prior_contacts=0,
    )
    assert high_probability > low_probability


def test_extremely_long_wait_is_not_always_optimal_for_network_failure() -> None:
    model = RecoveryProbabilityModel()
    truth = _truth(TrueFailureCause.NETWORK_INSTABILITY, InstrumentState.VALID)
    six_hours = model.probability(
        truth=truth,
        customer=_customer(),
        action=_action(ActionType.RETRY_LATER, 6),
        incident=None,
        hours_since_failure=6,
        retry_number=1,
        prior_contacts=0,
    )
    one_week = model.probability(
        truth=truth,
        customer=_customer(),
        action=_action(ActionType.RETRY_LATER, 168),
        incident=None,
        hours_since_failure=168,
        retry_number=1,
        prior_contacts=0,
    )
    assert six_hours > one_week


def test_revenue_attribution_occurs_once() -> None:
    ledger = AttributionLedger()
    attribution = RecoveryAttribution(
        payment_id="SIM_PAYMENT_TEST",
        action_id="SIM_ACTION_TEST",
        action_type=ActionType.RETRY_LATER,
        recovered_at=NOW,
        recovered_amount_minor=49_900,
    )
    ledger.attribute(attribution)
    with pytest.raises(ValueError, match="already attributed"):
        ledger.attribute(attribution)
