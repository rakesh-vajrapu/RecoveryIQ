import { RecoveryCaseDetailView } from "@/components/recovery-case-detail";

export default async function RecoveryCasePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RecoveryCaseDetailView id={id} />;
}
