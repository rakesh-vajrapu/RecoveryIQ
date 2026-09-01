export const dynamic = 'force-dynamic';
import { RecoveryCaseDetailView } from "@/components/recovery-case-detail";
import { getSimulatedDecisionExample } from "@/lib/api";

export default async function SimulatedExamplePage() {
  const simulatedCase = await getSimulatedDecisionExample();
  return <RecoveryCaseDetailView simulatedCase={simulatedCase} />;
}
