import { AuditTimelineView } from "@/components/audit-timeline";

export default async function AuditPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AuditTimelineView id={id} />;
}
