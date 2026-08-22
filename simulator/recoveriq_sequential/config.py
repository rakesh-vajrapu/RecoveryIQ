from __future__ import annotations

from dataclasses import dataclass

from recoveriq_simulator.enums import ActionType, CostRegime

SEQUENTIAL_TRAINING_SEEDS = tuple(range(20_270_801, 20_270_821))
MODEL_V2_DEVELOPMENT_SEEDS = tuple(range(20_270_901, 20_270_911))
MODEL_V2_CALIBRATION_SEEDS = tuple(range(20_271_001, 20_271_011))
MODEL_V2_HELDOUT_SEEDS = tuple(range(20_271_101, 20_271_111))
SEQUENTIAL_POLICY_DEVELOPMENT_SEEDS = tuple(range(20_271_201, 20_271_211))
SEQUENTIAL_POLICY_VALIDATION_SEEDS = tuple(range(20_280_101, 20_280_111))
SEQUENTIAL_STRESS_SEEDS = tuple(range(20_280_201, 20_280_206))
OVERALL_FINAL_SEEDS = tuple(range(20_261_101, 20_261_121))

EPISODE_HORIZON_HOURS = 48.0
MAX_AUTONOMOUS_INTERVENTIONS = 3
MAX_RETRIES = 2
MAX_CONTACTS = 2
MIN_RETRY_INTERVAL_HOURS = 2.0
RETRY_OBSERVATION_WINDOW_HOURS = 2.0
CONTACT_OBSERVATION_WINDOW_HOURS = 6.0
QUIET_HOURS_START_UTC = 22
QUIET_HOURS_END_UTC = 7
PRIMARY_COST_REGIME = CostRegime.BALANCED

CONTACT_ALLOWED_RATE = 0.95
INITIAL_ACTIVE_LINK_RATE = 0.03
ALTERNATE_METHOD_AVAILABLE_RATE = 0.90


@dataclass(frozen=True, slots=True)
class SequentialCandidateSpec:
    label: str
    action_type: ActionType
    delay_hours: float


SEQUENTIAL_CANDIDATE_SPECS = (
    SequentialCandidateSpec("RETRY_NOW", ActionType.RETRY_NOW, 0.0),
    SequentialCandidateSpec("RETRY_LATER_2H", ActionType.RETRY_LATER, 2.0),
    SequentialCandidateSpec("RETRY_LATER_6H", ActionType.RETRY_LATER, 6.0),
    SequentialCandidateSpec("RETRY_LATER_12H", ActionType.RETRY_LATER, 12.0),
    SequentialCandidateSpec("RETRY_LATER_24H", ActionType.RETRY_LATER, 24.0),
    SequentialCandidateSpec("SEND_NUDGE", ActionType.SEND_NUDGE, 0.0),
    SequentialCandidateSpec("CREATE_PAYMENT_LINK", ActionType.CREATE_PAYMENT_LINK, 0.0),
    SequentialCandidateSpec(
        "REQUEST_PAYMENT_METHOD_UPDATE",
        ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
        0.0,
    ),
    SequentialCandidateSpec(
        "OFFER_ALTERNATE_METHOD",
        ActionType.OFFER_ALTERNATE_METHOD,
        0.0,
    ),
)
SEQUENTIAL_CANDIDATE_LABELS = tuple(spec.label for spec in SEQUENTIAL_CANDIDATE_SPECS)
SEQUENTIAL_CANDIDATE_INDEX = {
    label: index for index, label in enumerate(SEQUENTIAL_CANDIDATE_LABELS)
}

CONTACT_ACTIONS = frozenset(
    {
        ActionType.SEND_NUDGE,
        ActionType.CREATE_PAYMENT_LINK,
        ActionType.REQUEST_PAYMENT_METHOD_UPDATE,
        ActionType.OFFER_ALTERNATE_METHOD,
    }
)
RETRY_ACTIONS = frozenset({ActionType.RETRY_NOW, ActionType.RETRY_LATER})
METHOD_CHANGE_ACTIONS = frozenset(
    {ActionType.REQUEST_PAYMENT_METHOD_UPDATE, ActionType.OFFER_ALTERNATE_METHOD}
)
