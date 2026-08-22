from __future__ import annotations

from recoveriq_sequential.config import (
    MAX_AUTONOMOUS_INTERVENTIONS,
    MAX_CONTACTS,
    MAX_RETRIES,
    SEQUENTIAL_CANDIDATE_INDEX,
)
from recoveriq_sequential.models import SequentialEpisodeState
from recoveriq_sequential_policy.models import (
    SequentialCandidateScore,
    SequentialDecisionKind,
    SequentialPolicyDecision,
)


class RecoverIQSequentialPolicyEngine:
    def __init__(self, normalized_margin_threshold: float) -> None:
        if normalized_margin_threshold < 0:
            raise ValueError("normalized margin threshold cannot be negative")
        self.normalized_margin_threshold = normalized_margin_threshold

    def decide(
        self,
        state: SequentialEpisodeState,
        scores: tuple[SequentialCandidateScore, ...],
    ) -> SequentialPolicyDecision:
        if state.intervention_count >= MAX_AUTONOMOUS_INTERVENTIONS:
            return self._stop("MAX_INTERVENTIONS")
        if state.decision_at >= state.horizon_at:
            return self._stop("RECOVERY_HORIZON")
        if not scores:
            reason = (
                "BUDGETS_EXHAUSTED"
                if state.retry_count >= MAX_RETRIES and state.contact_count >= MAX_CONTACTS
                else "NO_FEASIBLE_ACTION"
            )
            return self._stop(reason)
        ordered = sorted(
            scores,
            key=lambda item: (
                -item.incremental_erv_minor,
                SEQUENTIAL_CANDIDATE_INDEX[item.candidate.label],
            ),
        )
        positive = [item for item in ordered if item.incremental_erv_minor > 0]
        if not positive:
            return self._stop("NON_POSITIVE_INCREMENTAL_ERV")
        best = positive[0]
        if not best.supported:
            return SequentialPolicyDecision(
                kind=SequentialDecisionKind.HUMAN_REVIEW,
                selected=None,
                reason=(
                    "MODEL_SUPPORT" if best.action_stage_support < 500 else "CALIBRATION_SUPPORT"
                ),
                normalized_margin=None,
            )
        margin = (
            1.0
            if len(positive) == 1
            else max(0.0, best.normalized_erv - positive[1].normalized_erv)
        )
        if margin < self.normalized_margin_threshold:
            return SequentialPolicyDecision(
                kind=SequentialDecisionKind.HUMAN_REVIEW,
                selected=None,
                reason="LOW_DECISION_MARGIN",
                normalized_margin=margin,
            )
        return SequentialPolicyDecision(
            kind=SequentialDecisionKind.ACTION,
            selected=best,
            reason="MAX_POSITIVE_SUPPORTED_INCREMENTAL_ERV",
            normalized_margin=margin,
        )

    @staticmethod
    def _stop(reason: str) -> SequentialPolicyDecision:
        return SequentialPolicyDecision(
            kind=SequentialDecisionKind.STOP,
            selected=None,
            reason=reason,
            normalized_margin=None,
        )
