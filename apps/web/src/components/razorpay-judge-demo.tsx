"use client";

import { useEffect, useState, useCallback } from "react";
import { Link2, ShieldCheck, CreditCard, RefreshCw, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { prepareRazorpayJudgeDemo, createTestPaymentLink, getRecoveryCase, type RecoveryCaseDetail } from "@/lib/api";
import { formatMoney } from "@/lib/format";

export function RazorpayJudgeDemo() {
  const [caseDetail, setCaseDetail] = useState<RecoveryCaseDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollCase = useCallback(async (id: string) => {
    try {
      const data = await getRecoveryCase(id);
      setCaseDetail(data);
      if (data.status === "recovered") {
        return true; // Stop polling
      }
    } catch (e) {
      console.error(e);
    }
    return false;
  }, []);

  useEffect(() => {
    if (!caseDetail || caseDetail.status === "recovered") return;
    const interval = setInterval(async () => {
      const done = await pollCase(caseDetail.id);
      if (done) clearInterval(interval);
    }, 2500);
    return () => clearInterval(interval);
  }, [caseDetail, pollCase]);

  const handlePrepare = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await prepareRazorpayJudgeDemo();
      setCaseDetail(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to prepare test case");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateLink = async () => {
    if (!caseDetail) return;
    if (!window.confirm("Create a ₹1,000.00 Razorpay Test Mode Payment Link?\nNo real money will move.")) return;
    setLoading(true);
    setError(null);
    try {
      await createTestPaymentLink(caseDetail.id);
      await pollCase(caseDetail.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create payment link");
    } finally {
      setLoading(false);
    }
  };

  if (!caseDetail) {
    return (
      <section className="surface-panel rounded-2xl p-6 border-amber-500/30 bg-amber-500/5">
        <div className="flex justify-between items-start">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="bg-amber-500/20 text-amber-500 font-bold px-2 py-0.5 rounded text-[10px] tracking-wider uppercase">Razorpay &middot; Test Mode</span>
              <h2 className="text-xl font-bold">LIVE RAZORPAY TEST DEMO</h2>
            </div>
            <p className="mt-2 text-sm text-muted-foreground max-w-xl">
              Execute a controlled ₹1,000 Test Mode recovery and watch real Razorpay provider evidence flow back into RecoveryIQ.
            </p>
            <p className="mt-2 text-xs text-amber-500 font-medium">Razorpay Test Mode only. No real money moves.</p>
          </div>
          <Button onClick={handlePrepare} disabled={loading}>
            {loading ? <RefreshCw className="size-4 mr-2 animate-spin" /> : <ShieldCheck className="size-4 mr-2" />}
            PREPARE ₹1,000 TEST CASE
          </Button>
        </div>
        {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
      </section>
    );
  }

  const execution = caseDetail.executions[0];
  const linkCreated = !!execution;
  const outcome = caseDetail.outcomes[0];
  const isRecovered = caseDetail.status === "recovered";

  return (
    <section className="surface-panel rounded-2xl p-6 border-amber-500/30 bg-amber-500/5 mt-8">
      <div className="flex justify-between items-start border-b border-border/50 pb-5 mb-5">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="bg-amber-500/20 text-amber-500 font-bold px-2 py-0.5 rounded text-[10px] tracking-wider uppercase">Razorpay &middot; Test Mode</span>
            <h2 className="text-xl font-bold">{isRecovered ? "RAZORPAY TEST RECOVERY VERIFIED" : "LIVE RAZORPAY TEST DEMO"}</h2>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {isRecovered ? "Test flow complete. Provider evidence recorded and recovery attributed." : "Watch real Razorpay provider evidence flow back into RecoveryIQ."}
          </p>
          <p className="mt-2 text-xs text-amber-500 font-medium">Razorpay Test Mode only. No real money moves.</p>
        </div>
        {isRecovered && (
          <Button onClick={handlePrepare} disabled={loading} variant="outline">
            {loading ? <RefreshCw className="size-4 mr-2 animate-spin" /> : <RefreshCw className="size-4 mr-2" />}
            PREPARE ANOTHER ₹1,000 TEST CASE
          </Button>
        )}
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h3 className="text-sm font-semibold mb-4 uppercase text-muted-foreground tracking-wider">Test Mode Timeline</h3>
          <div className="space-y-4">
            <TimelineStep label="1. PREPARE ₹1,000 TEST CASE" done={true} />
            <TimelineStep label="2. CREATE ₹1,000 RAZORPAY TEST PAYMENT LINK" done={linkCreated} />
            <TimelineStep label="3. OPEN RAZORPAY TEST PAYMENT LINK" done={linkCreated} />
            <TimelineStep label="4. WAITING FOR RAZORPAY WEBHOOK" done={!!outcome} active={linkCreated && !outcome} />
            <TimelineStep label="5. WEBHOOK RECEIVED" done={!!outcome} />
            <TimelineStep label="6. SIGNATURE VERIFIED" done={!!outcome} />
            <TimelineStep label="7. PROVIDER STATE CONFIRMED" done={outcome?.verified === true} />
            <TimelineStep label="8. EXTERNAL OUTCOME RECORDED" done={!!outcome} />
            <TimelineStep label="9. LOCAL ATTRIBUTION CREATED" done={!!caseDetail.attribution} />
            <TimelineStep label="10. RECOVERED" done={isRecovered} />
          </div>
          {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
        </div>

        <div className="space-y-4">
          {!linkCreated ? (
            <div className="bg-card/50 border rounded-xl p-5 text-center">
              <p className="text-sm font-medium mb-1">LOCAL TEST SETUP</p>
              <p className="text-xs text-muted-foreground mb-4">
                This case was prepared locally for a controlled Razorpay Test Mode provider demonstration. Provider evidence begins when the Test Mode Payment Link is created and Razorpay events are received.
              </p>
              <Button onClick={handleCreateLink} disabled={loading} className="w-full">
                {loading ? <RefreshCw className="size-4 mr-2 animate-spin" /> : <Link2 className="size-4 mr-2" />}
                CREATE ₹1,000 RAZORPAY TEST PAYMENT LINK
              </Button>
            </div>
          ) : (
            <div className="bg-card/50 border rounded-xl p-5">
              <h3 className="text-sm font-semibold mb-3 flex items-center gap-2"><CreditCard className="size-4" /> Provider Execution Evidence</h3>
              <div className="space-y-2 text-xs mb-4">
                <div className="flex justify-between"><span className="text-muted-foreground">Execution ID</span><span className="font-mono">{execution.id}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Amount</span><span>{formatMoney(execution.amount_minor)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Currency</span><span>{execution.currency}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">State</span><span>{execution.state}</span></div>
              </div>
              {execution.provider_url && !isRecovered && (
                <Button onClick={() => window.open(execution.provider_url!, "_blank")} className="w-full">
                  OPEN RAZORPAY TEST PAYMENT LINK
                </Button>
              )}
            </div>
          )}

          {isRecovered && outcome && (
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-xl p-5 mt-4">
              <h3 className="text-sm font-semibold mb-3 text-emerald-600 dark:text-emerald-400 flex items-center gap-2"><CheckCircle2 className="size-4" /> Provider Truth & Attribution</h3>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between"><span className="text-muted-foreground">Signed webhook</span><span className="font-medium text-emerald-500">VERIFIED</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Provider state</span><span className="font-medium text-emerald-500">CONFIRMED</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Amount</span><span className="font-medium text-emerald-500">{formatMoney(outcome.amount_minor)} VERIFIED</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Currency</span><span className="font-medium text-emerald-500">{outcome.currency} VERIFIED</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">ExternalOutcome</span><span className="font-medium text-emerald-500">RECORDED</span></div>
                <div className="mt-3 pt-3 border-t border-emerald-500/20">
                  <span className="block text-muted-foreground mb-1">Local attribution</span>
                  <span className="font-medium text-emerald-500 block">EXACTLY ONCE</span>
                  <span className="text-[10px] text-emerald-600/70 block mt-1">Exactly-once local outcome and recovery attribution semantics.</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function TimelineStep({ label, done, active }: { label: string; done: boolean; active?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`size-4 rounded-full flex items-center justify-center text-[10px] ${done ? 'bg-emerald-500 text-white' : active ? 'bg-amber-500 text-white animate-pulse' : 'bg-muted text-transparent'}`}>
        {done && '✓'}
      </div>
      <span className={`text-xs font-medium ${done ? 'text-foreground' : active ? 'text-amber-500' : 'text-muted-foreground'}`}>{label}</span>
      {!done && active && <span className="text-[10px] text-amber-500 ml-auto">WAITING</span>}
      {!done && !active && <span className="text-[10px] text-muted-foreground ml-auto">PENDING</span>}
    </div>
  );
}
