import { BatchExplorerContent } from "@/components/batch-explorer/batch-explorer-content";

export const metadata = {
  title: "Batch Explorer | RecoveryIQ",
};

export default function BatchExplorerPage() {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-7xl px-4 py-8 md:px-8">
            <BatchExplorerContent />
          </div>
        </div>
      </main>
    </div>
  );
}
