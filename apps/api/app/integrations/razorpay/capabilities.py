from app.models import ExecutionCapability

ACTION_CAPABILITIES: dict[str, ExecutionCapability] = {
    "WAIT": ExecutionCapability.INTERNAL_SCHEDULE_ONLY,
    "RETRY_NOW": ExecutionCapability.INTERNAL_SCHEDULE_ONLY,
    "RETRY_LATER": ExecutionCapability.INTERNAL_SCHEDULE_ONLY,
    "RETRY_LATER_2H": ExecutionCapability.INTERNAL_SCHEDULE_ONLY,
    "RETRY_LATER_6H": ExecutionCapability.INTERNAL_SCHEDULE_ONLY,
    "RETRY_LATER_12H": ExecutionCapability.INTERNAL_SCHEDULE_ONLY,
    "RETRY_LATER_24H": ExecutionCapability.INTERNAL_SCHEDULE_ONLY,
    "SEND_NUDGE": ExecutionCapability.RECOMMENDATION_ONLY,
    "CREATE_PAYMENT_LINK": ExecutionCapability.REAL_TEST_EXECUTION,
    "REQUEST_PAYMENT_METHOD_UPDATE": ExecutionCapability.RECOMMENDATION_ONLY,
    "OFFER_ALTERNATE_METHOD": ExecutionCapability.RECOMMENDATION_ONLY,
    "ESCALATE_TO_HUMAN": ExecutionCapability.RECOMMENDATION_ONLY,
    "STOP": ExecutionCapability.RECOMMENDATION_ONLY,
    "HIDDEN_ORACLE_ACTION": ExecutionCapability.SIMULATION_ONLY,
}


def resolve_capability(action: str) -> ExecutionCapability:
    """Resolve an action without inventing an external provider operation."""

    return ACTION_CAPABILITIES.get(action, ExecutionCapability.RECOMMENDATION_ONLY)
