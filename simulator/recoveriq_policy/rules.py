from __future__ import annotations

from recoveriq_policy.candidates import RETRY_ACTIONS
from recoveriq_policy.config import (
    MAX_CONTACT_COUNT,
    MAX_RETRY_COUNT,
    MIN_RETRY_INTERVAL_HOURS,
    TARGET_HORIZON_HOURS,
)
from recoveriq_policy.models import (
    CandidatePrediction,
    DecisionPolicyFacts,
    EconomicScore,
    PolicyDecisionContext,
    PolicyRuleEvidence,
    RuleResult,
)
from recoveriq_simulator.enums import ActionType


def facts_from_context(context: PolicyDecisionContext) -> DecisionPolicyFacts:
    return DecisionPolicyFacts(
        decision_key=context.decision_key,
        decision_at=context.decision_at,
        payment_amount_minor=context.base_features.amount_minor,
        failure_to_decision_hours=context.base_features.failure_to_decision_hours,
        current_retry_count=context.base_features.current_retry_count,
        current_contact_count=context.base_features.current_contact_count,
        operational=context.operational,
    )


def hard_feasibility_checks(
    prediction: CandidatePrediction,
    facts: DecisionPolicyFacts,
) -> tuple[PolicyRuleEvidence, ...]:
    candidate = prediction.candidate
    action = candidate.recovery_action
    checks = [
        _check(
            "RECOVERY_HORIZON_EXCEEDED",
            action.scheduled_delay_hours <= TARGET_HORIZON_HOURS,
            action.scheduled_delay_hours,
            TARGET_HORIZON_HOURS,
            "candidate execution must remain inside the 48-hour horizon",
        )
    ]
    if action.action_type in RETRY_ACTIONS:
        checks.extend(
            (
                _check(
                    "MAX_RETRY_COUNT",
                    facts.current_retry_count < MAX_RETRY_COUNT,
                    facts.current_retry_count,
                    MAX_RETRY_COUNT,
                    "retry count must remain below the autonomous cap",
                ),
                _check(
                    "MIN_RETRY_INTERVAL",
                    action.action_type is not ActionType.RETRY_NOW
                    or facts.failure_to_decision_hours >= MIN_RETRY_INTERVAL_HOURS,
                    facts.failure_to_decision_hours,
                    MIN_RETRY_INTERVAL_HOURS,
                    "retry-now must satisfy the configured interval",
                ),
            )
        )
    if candidate.is_customer_contact:
        checks.extend(
            (
                _check(
                    "MAX_CONTACT_COUNT",
                    facts.current_contact_count < MAX_CONTACT_COUNT,
                    facts.current_contact_count,
                    MAX_CONTACT_COUNT,
                    "contact count must remain below the autonomous cap",
                ),
                _check(
                    "CUSTOMER_OPT_OUT",
                    facts.operational.customer_contact_allowed,
                    facts.operational.customer_contact_allowed,
                    True,
                    "customer contact must be permitted",
                ),
                _check(
                    "QUIET_HOURS",
                    not facts.operational.quiet_hours,
                    facts.operational.quiet_hours,
                    False,
                    "immediate customer contact is blocked during quiet hours",
                ),
            )
        )
    if action.action_type is ActionType.CREATE_PAYMENT_LINK:
        checks.append(
            _check(
                "DUPLICATE_PAYMENT_LINK",
                not facts.operational.existing_active_payment_link,
                facts.operational.existing_active_payment_link,
                False,
                "a second active payment link is not allowed",
            )
        )
    if action.action_type is ActionType.OFFER_ALTERNATE_METHOD:
        checks.append(
            _check(
                "ALTERNATE_METHOD_UNAVAILABLE",
                facts.operational.alternate_method_available,
                facts.operational.alternate_method_available,
                True,
                "alternate-method workflow must be available",
            )
        )
    return tuple(checks)


def candidate_policy_checks(
    prediction: CandidatePrediction,
    economic: EconomicScore,
    facts: DecisionPolicyFacts,
) -> tuple[PolicyRuleEvidence, ...]:
    checks = list(hard_feasibility_checks(prediction, facts))
    checks.append(
        PolicyRuleEvidence(
            policy_id="LOW_SUPPORT",
            result=RuleResult.REVIEW if prediction.support.low_support else RuleResult.PASS,
            observed_value=(
                ",".join(prediction.support.reasons) if prediction.support.reasons else "SUPPORTED"
            ),
            threshold=("action>=1000; calibration_bin>=100; no unknown categorical values"),
            reason="poorly supported candidates require human review",
        )
    )
    checks.append(
        PolicyRuleEvidence(
            policy_id="NON_POSITIVE_ERV",
            result=RuleResult.PASS if economic.erv_minor > 0 else RuleResult.BLOCK,
            observed_value=str(economic.erv_minor),
            threshold=">0 minor INR",
            reason="autonomous candidates must have positive expected recovery value",
        )
    )
    return tuple(checks)


def combined_result(checks: tuple[PolicyRuleEvidence, ...]) -> RuleResult:
    if any(check.result is RuleResult.BLOCK for check in checks):
        return RuleResult.BLOCK
    if any(check.result is RuleResult.REVIEW for check in checks):
        return RuleResult.REVIEW
    return RuleResult.PASS


def _check(
    policy_id: str,
    passed: bool,
    observed: object,
    threshold: object,
    reason: str,
) -> PolicyRuleEvidence:
    return PolicyRuleEvidence(
        policy_id=policy_id,
        result=RuleResult.PASS if passed else RuleResult.BLOCK,
        observed_value=str(observed),
        threshold=str(threshold),
        reason=reason,
    )
