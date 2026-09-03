"use client";

import { useEffect, useState } from "react";
import { getRecoveryProof, RecoveryProofRecord } from "@/lib/api";

export function RecoveryProof({ caseId }: { caseId: string }) {
  const [proof, setProof] = useState<RecoveryProofRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const result = await getRecoveryProof(caseId);
        if (active) {
          setProof(result);
          setError(null);
        }
      } catch (err: unknown) {
        if (active) setError(err instanceof Error ? err.message : "Failed to load proof");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => { active = false; };
  }, [caseId]);

  if (loading) return <div className="text-gray-400 text-sm py-4">Loading Recovery Proof...</div>;
  if (error || !proof) return <div className="text-red-400 text-sm py-4">Recovery Proof unavailable</div>;

  const isDemo = proof.evidence_lane === "DEMO_SYNTHETIC";
  const badgeClass = isDemo ? "bg-purple-900 text-purple-200" : "bg-blue-900 text-blue-200";

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-5 font-mono text-xs text-gray-300 mt-6 shadow-lg">
      <div className="flex justify-between items-center mb-4 pb-2 border-b border-gray-800">
        <h3 className="font-bold text-gray-100 uppercase tracking-wider">Recovery Proof</h3>
        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${badgeClass}`}>
          {isDemo ? "DEMO \u00B7 SYNTHETIC" : "RAZORPAY \u00B7 TEST MODE"}
        </span>
      </div>

      <div className="space-y-4">
        {/* Case */}
        <div>
          <div className="text-gray-500 uppercase font-semibold mb-1">Case</div>
          <div className="flex justify-between">
            <span>Status</span>
            <span className="text-gray-100">{proof.case.status}</span>
          </div>
        </div>

        {/* Decision */}
        {proof.decision && (
          <div>
            <div className="text-gray-500 uppercase font-semibold mb-1">Decision</div>
            <div className="flex justify-between">
              <span>{proof.decision.selected_action || proof.decision.decision_kind}</span>
              <span className="text-gray-100">
                {proof.authorization?.initiator.replace("_", " ")}
              </span>
            </div>
          </div>
        )}

        {/* Execution */}
        {proof.execution && (
          <div>
            <div className="text-gray-500 uppercase font-semibold mb-1">Execution</div>
            <div className="flex justify-between">
              <span>{proof.execution.provider_entity_type.replace("_", " ")}</span>
              <span className="text-gray-100 font-mono">{proof.execution.provider_entity_reference || "plink_..."}</span>
            </div>
          </div>
        )}

        {/* Provider Evidence */}
        <div>
          <div className="text-gray-500 uppercase font-semibold mb-1">Provider Evidence</div>
          <div className="flex justify-between">
            <span>Signed Webhook</span>
            <span className="text-gray-100">
              {proof.provider_evidence?.webhook_signature_verified ? "VERIFIED" : "NOT CAPTURED"}
            </span>
          </div>
          <div className="flex justify-between mt-1">
            <span>Independent Provider Fetch</span>
            <span className="text-gray-100">
              {proof.provider_evidence?.provider_confirmation_status ? proof.provider_evidence.provider_confirmation_status.replace("_", " ") : "NOT CAPTURED"}
            </span>
          </div>
        </div>

        {/* Outcome */}
        {proof.outcome && (
          <div>
            <div className="text-gray-500 uppercase font-semibold mb-1">Outcome</div>
            <div className="flex justify-between">
              <span>Provider Payment</span>
              <span className="text-gray-100">
                {proof.outcome.outcome === "PAID" ? "VERIFIED" : proof.outcome.outcome}
              </span>
            </div>
          </div>
        )}

        {/* Attribution */}
        {proof.attribution && (
          <div>
            <div className="text-gray-500 uppercase font-semibold mb-1">Attribution</div>
            <div className="flex justify-between">
              <span>Local Recovery</span>
              <span className="text-gray-100">ATTRIBUTED ONCE</span>
            </div>
          </div>
        )}

        {/* Integrity */}
        <div className="pt-4 border-t border-gray-800 mt-2">
          <div className="text-gray-500 uppercase font-semibold mb-1">Proof Fingerprint</div>
          <div className="text-green-400 break-all text-[11px] mb-1">
            {proof.integrity.fingerprint}
          </div>
          <div className="text-gray-500 text-[10px]">
            SHA-256 &middot; canonical non-secret evidence
          </div>
        </div>
      </div>
    </div>
  );
}
