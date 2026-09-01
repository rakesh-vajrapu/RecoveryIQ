import { Metadata } from "next";

import { PageHeader } from "@/components/page-header";
import { SafetyLabContent } from "@/components/safety-lab/safety-lab-content";

export const metadata: Metadata = {
  title: "Safety Lab | RecoverIQ",
  description: "Verified safety and idempotency evidence.",
};

export default function SafetyLabPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Verification Evidence"
        title="Safety Lab"
        description="Verifiable idempotency, concurrency, and reliability claims based on isolated local test evidence."
      />
      <SafetyLabContent />
    </div>
  );
}
