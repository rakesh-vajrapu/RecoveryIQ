from __future__ import annotations

from decimal import Decimal

from recoveriq_policy import POLICY_VERSION
from recoveriq_policy.config import CANDIDATE_INDEX
from recoveriq_policy.economics import economic_score
from recoveriq_policy.models import (
    CandidatePrediction,
    DecisionCandidate,
    DecisionKind,
    DecisionPolicyFacts,
    PolicyRuleEvidence,
    RecoveryDecision,
    RuleResult,
)
from recoveriq_policy.rules import candidate_policy_checks, combined_result


class RecoverIQPolicyEngine:
    def __init__(
        self,
        *,
        policy_config_hash: str,
        normalized_margin_threshold: Decimal,
    ) -> None:
        if normalized_margin_threshold < 0:
            raise ValueError("decision-margin threshold cannot be negative")
        self.policy_config_hash = policy_config_hash
        self.normalized_margin_threshold = normalized_margin_threshold

    def decide(
        self,
        facts: DecisionPolicyFacts,
        predictions: tuple[CandidatePrediction, ...],
    ) -> RecoveryDecision:
        if not predictions:
            return self._schema_review(facts, "no scored candidates")
        candidates = tuple(
            self._evaluate_candidate(facts, prediction) for prediction in predictions
        )
        eligible = [
            candidate
            for candidate in candidates
            if candidate.final_policy_result is not RuleResult.BLOCK
        ]
        eligible.sort(
            key=lambda item: (
                -item.economic.erv_minor,
                CANDIDATE_INDEX[item.prediction.candidate.label],
            )
        )
        if not eligible:
            return RecoveryDecision(
                policy_version=POLICY_VERSION,
                policy_config_hash=self.policy_config_hash,
                decision_key=facts.decision_key,
                decision_kind=DecisionKind.STOP,
                selected_candidate=None,
                candidates=candidates,
                absolute_erv_margin_minor=None,
                normalized_erv_margin=None,
                decision_rules=(),
                reason="all candidates are blocked or non-positive ERV",
            )
        top = eligible[0]
        second_erv = eligible[1].economic.erv_minor if len(eligible) > 1 else 0
        absolute_margin = top.economic.erv_minor - second_erv
        normalized_margin = Decimal(absolute_margin) / Decimal(facts.payment_amount_minor)
        margin_evidence = PolicyRuleEvidence(
            policy_id="LOW_DECISION_MARGIN",
            result=(
                RuleResult.PASS
                if normalized_margin >= self.normalized_margin_threshold
                else RuleResult.REVIEW
            ),
            observed_value=str(normalized_margin),
            threshold=str(self.normalized_margin_threshold),
            reason="small normalized ERV separation requires human review",
        )
        if top.final_policy_result is RuleResult.REVIEW:
            return RecoveryDecision(
                policy_version=POLICY_VERSION,
                policy_config_hash=self.policy_config_hash,
                decision_key=facts.decision_key,
                decision_kind=DecisionKind.HUMAN_REVIEW,
                selected_candidate=None,
                candidates=candidates,
                absolute_erv_margin_minor=absolute_margin,
                normalized_erv_margin=normalized_margin,
                decision_rules=(margin_evidence,),
                reason="highest-ERV candidate requires support review",
            )
        if margin_evidence.result is RuleResult.REVIEW:
            return RecoveryDecision(
                policy_version=POLICY_VERSION,
                policy_config_hash=self.policy_config_hash,
                decision_key=facts.decision_key,
                decision_kind=DecisionKind.HUMAN_REVIEW,
                selected_candidate=None,
                candidates=candidates,
                absolute_erv_margin_minor=absolute_margin,
                normalized_erv_margin=normalized_margin,
                decision_rules=(margin_evidence,),
                reason="normalized ERV decision margin is below the frozen threshold",
            )
        return RecoveryDecision(
            policy_version=POLICY_VERSION,
            policy_config_hash=self.policy_config_hash,
            decision_key=facts.decision_key,
            decision_kind=DecisionKind.ACTION,
            selected_candidate=top,
            candidates=candidates,
            absolute_erv_margin_minor=absolute_margin,
            normalized_erv_margin=normalized_margin,
            decision_rules=(margin_evidence,),
            reason="selected maximum positive ERV among policy-allowed candidates",
        )

    def _evaluate_candidate(
        self,
        facts: DecisionPolicyFacts,
        prediction: CandidatePrediction,
    ) -> DecisionCandidate:
        economic = economic_score(prediction, facts.payment_amount_minor)
        checks = candidate_policy_checks(prediction, economic, facts)
        return DecisionCandidate(
            prediction=prediction,
            economic=economic,
            policy_checks=checks,
            final_policy_result=combined_result(checks),
        )

    def _schema_review(
        self,
        facts: DecisionPolicyFacts,
        reason: str,
    ) -> RecoveryDecision:
        evidence = PolicyRuleEvidence(
            policy_id="MODEL_SCHEMA_INVALID",
            result=RuleResult.REVIEW,
            observed_value=reason,
            threshold="exact frozen model feature schema",
            reason="invalid model input cannot produce an autonomous decision",
        )
        return RecoveryDecision(
            policy_version=POLICY_VERSION,
            policy_config_hash=self.policy_config_hash,
            decision_key=facts.decision_key,
            decision_kind=DecisionKind.HUMAN_REVIEW,
            selected_candidate=None,
            candidates=(),
            absolute_erv_margin_minor=None,
            normalized_erv_margin=None,
            decision_rules=(evidence,),
            reason=reason,
        )
