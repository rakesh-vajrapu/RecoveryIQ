from __future__ import annotations

import pytest

from recoveriq_simulator.benchmark import run_benchmark
from recoveriq_simulator.config import SimulatorConfig
from recoveriq_simulator.ground_truth import GeneratedScenario
from recoveriq_simulator.results import BenchmarkResult


@pytest.fixture(scope="session")
def shared_config() -> SimulatorConfig:
    return SimulatorConfig(
        seed=42_424,
        num_payment_attempts=1_200,
        merchant_count=4,
        customer_count=200,
        subscription_count=400,
        horizon_days=90,
        incident_count=12,
    )


@pytest.fixture(scope="session")
def shared_run(
    shared_config: SimulatorConfig,
) -> tuple[GeneratedScenario, BenchmarkResult]:
    return run_benchmark(shared_config)


@pytest.fixture(scope="session")
def shared_scenario(
    shared_run: tuple[GeneratedScenario, BenchmarkResult],
) -> GeneratedScenario:
    return shared_run[0]


@pytest.fixture(scope="session")
def shared_benchmark(
    shared_run: tuple[GeneratedScenario, BenchmarkResult],
) -> BenchmarkResult:
    return shared_run[1]
