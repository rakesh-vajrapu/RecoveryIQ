from __future__ import annotations

from dataclasses import dataclass

from recoveriq_simulator.enums import ActionType, CostRegime

POLICY_DEVELOPMENT_SEEDS = tuple(range(20_270_501, 20_270_511))
POLICY_VALIDATION_SEEDS = tuple(range(20_270_601, 20_270_611))
POLICY_STRESS_SEEDS = tuple(range(20_270_701, 20_270_706))
PHASE4_HELDOUT_SEEDS = tuple(range(20_270_401, 20_270_411))
OVERALL_FINAL_SEEDS = tuple(range(20_261_101, 20_261_121))

TARGET_HORIZON_HOURS = 48.0
PRIMARY_COST_REGIME = CostRegime.BALANCED
MIN_ACTION_TRAINING_SUPPORT = 1_000
MIN_CALIBRATION_BIN_SUPPORT = 100
REASON_BASELINE_MIN_SUPPORT = 200
REASON_METHOD_BASELINE_MIN_SUPPORT = 500
HETEROGENEITY_MIN_SUPPORT = 200
MAX_RETRY_COUNT = 2
MAX_CONTACT_COUNT = 2
MIN_RETRY_INTERVAL_HOURS = 0.0
QUIET_HOURS_START_UTC = 22
QUIET_HOURS_END_UTC = 7
MIN_AUTONOMOUS_COVERAGE = 0.70
MARGIN_THRESHOLD_CANDIDATES = (0.0, 0.001, 0.0025, 0.005, 0.01)
CONTACT_ALLOWED_RATE = 0.95
EXISTING_PAYMENT_LINK_RATE = 0.03
ALTERNATE_METHOD_AVAILABLE_RATE = 0.90


@dataclass(frozen=True, slots=True)
class CandidateSpec:
    label: str
    action_type: ActionType
    delay_hours: float


CANDIDATE_SPECS = (
    CandidateSpec("RETRY_NOW", ActionType.RETRY_NOW, 0.0),
    CandidateSpec("RETRY_LATER_2H", ActionType.RETRY_LATER, 2.0),
    CandidateSpec("RETRY_LATER_6H", ActionType.RETRY_LATER, 6.0),
    CandidateSpec("RETRY_LATER_12H", ActionType.RETRY_LATER, 12.0),
    CandidateSpec("RETRY_LATER_24H", ActionType.RETRY_LATER, 24.0),
    CandidateSpec("SEND_NUDGE", ActionType.SEND_NUDGE, 0.0),
    CandidateSpec("CREATE_PAYMENT_LINK", ActionType.CREATE_PAYMENT_LINK, 0.0),
    CandidateSpec(
        "REQUEST_PAYMENT_METHOD_UPDATE",
        ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
        0.0,
    ),
    CandidateSpec(
        "OFFER_ALTERNATE_METHOD",
        ActionType.OFFER_ALTERNATE_METHOD,
        0.0,
    ),
)
CANDIDATE_LABELS = tuple(spec.label for spec in CANDIDATE_SPECS)
CANDIDATE_INDEX = {label: index for index, label in enumerate(CANDIDATE_LABELS)}
