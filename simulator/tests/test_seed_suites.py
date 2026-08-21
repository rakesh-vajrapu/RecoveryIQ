from __future__ import annotations

from recoveriq_simulator.cli import main
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.seeds import (
    DEVELOPMENT_SEEDS,
    FINAL_EVALUATION_SEEDS,
    VALIDATION_SEEDS,
    seeds_for_group,
)
from recoveriq_simulator.suite import run_seed_suite


def test_seed_groups_are_named_stable_and_non_overlapping() -> None:
    assert len(DEVELOPMENT_SEEDS) == 10
    assert len(VALIDATION_SEEDS) == 10
    assert len(FINAL_EVALUATION_SEEDS) == 20
    assert not set(DEVELOPMENT_SEEDS) & set(VALIDATION_SEEDS)
    assert not set(DEVELOPMENT_SEEDS) & set(FINAL_EVALUATION_SEEDS)
    assert not set(VALIDATION_SEEDS) & set(FINAL_EVALUATION_SEEDS)
    assert seeds_for_group("robustness") == DEVELOPMENT_SEEDS + VALIDATION_SEEDS


def test_multi_seed_execution_aggregates_required_metrics() -> None:
    config = SimulatorConfig(
        num_payment_attempts=200,
        merchant_count=3,
        customer_count=80,
        subscription_count=100,
        horizon_days=60,
        incident_count=6,
    )
    report = run_seed_suite(
        group="test",
        base_config=config,
        seeds=(101, 202, 303),
    )
    assert len(report.runs) == 3
    failure_rate = report.environment_metrics["failure_rate"]
    assert failure_rate is not None
    assert failure_rate.minimum >= 0
    for metrics in report.policy_metrics.values():
        assert "recovery_rate" in metrics
        assert "gross_recovered_amount_minor" in metrics
        assert "net_recovered_value_minor" in metrics
        assert "average_time_to_recovery_hours" in metrics


def test_final_seed_group_requires_explicit_acknowledgement(capsys) -> None:  # type: ignore[no-untyped-def]
    exit_code = main(["benchmark-suite", "--group", "final", "--attempts", "100"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "FINAL EVALUATION SEEDS ARE RESERVED" in captured.err
