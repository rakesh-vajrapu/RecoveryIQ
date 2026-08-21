from __future__ import annotations

from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.scenario import ScenarioGenerator, scenario_digest


def _small_config(seed: int) -> SimulatorConfig:
    return SimulatorConfig(
        seed=seed,
        num_payment_attempts=300,
        merchant_count=3,
        customer_count=80,
        subscription_count=120,
        horizon_days=90,
        incident_count=5,
    )


def test_same_seed_produces_identical_scenario() -> None:
    config = _small_config(12_345)
    first = ScenarioGenerator(config).generate()
    second = ScenarioGenerator(config).generate()

    assert scenario_digest(first) == scenario_digest(second)
    assert first.model_dump_json() == second.model_dump_json()


def test_different_seed_materially_changes_scenario() -> None:
    first = ScenarioGenerator(_small_config(12_345)).generate()
    second = ScenarioGenerator(_small_config(54_321)).generate()

    first_amounts = [payment.amount_minor for payment in first.public.payments]
    second_amounts = [payment.amount_minor for payment in second.public.payments]
    assert scenario_digest(first) != scenario_digest(second)
    assert first_amounts != second_amounts


def test_payment_values_and_identifiers_are_safe(shared_scenario) -> None:  # type: ignore[no-untyped-def]
    assert all(payment.amount_minor > 0 for payment in shared_scenario.public.payments)
    identifiers = [payment.payment_id for payment in shared_scenario.public.payments]
    assert all(identifier.startswith("SIM_PAYMENT_") for identifier in identifiers)
    assert all(identifier.replace("SIM_PAYMENT_", "").isdigit() for identifier in identifiers)
    serialized = shared_scenario.public.model_dump_json().lower()
    assert "card_pan" not in serialized
    assert "cvv" not in serialized
    assert "otp" not in serialized
