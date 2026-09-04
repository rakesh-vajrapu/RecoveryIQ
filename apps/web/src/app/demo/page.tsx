"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/page-header";
import { getReplayPresets, getReplayTrace } from "@/lib/api";
import { formatMoney } from "@/lib/format";

// Inline UI wrappers
const Card = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`rounded-xl border border-zinc-800 bg-zinc-950/50 shadow-sm ${className}`}>
    {children}
  </div>
);
const CardHeader = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`flex flex-col space-y-1.5 p-6 ${className}`}>{children}</div>
);
const CardTitle = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <h3 className={`font-semibold leading-none tracking-tight ${className}`}>{children}</h3>
);
const CardContent = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
  <div className={`p-6 pt-0 ${className}`}>{children}</div>
);
const Badge = ({ children, variant = "default", className = "" }: { children: React.ReactNode; variant?: "default" | "destructive" | "outline"; className?: string }) => {
  const vclass = variant === "destructive" ? "bg-red-500/10 text-red-500 border-red-500/20" 
               : variant === "outline" ? "border border-zinc-700 text-zinc-300"
               : "bg-emerald-500/10 text-emerald-500 border-emerald-500/20";
  return <div className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors ${vclass} ${className}`}>{children}</div>;
};

export default function ReplayLabPage() {
  const [presets, setPresets] = useState<{ id: string; name: string }[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<string>("");
  const [trace, setTrace] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getReplayPresets()
      .then((data) => {
        setPresets(data);
        if (data.length > 0) {
          setSelectedPreset(data[0].id);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedPreset) return;
    setLoading(true);
    getReplayTrace(selectedPreset)
      .then(setTrace)
      .finally(() => setLoading(false));
  }, [selectedPreset]);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Interactive Demo"
        title="RecoveryIQ Replay Lab"
        description="Interactive replay of frozen Model V2 decisions from evaluation artifacts. The AI remains read-only here."
        actions={
          <select 
            className="border border-zinc-800 bg-zinc-900 rounded p-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-emerald-500"
            value={selectedPreset}
            onChange={(e) => setSelectedPreset(e.target.value)}
          >
            {presets.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        }
      />

      {loading && <div className="text-zinc-400 p-8 text-center animate-pulse">Loading trace...</div>}

      {!loading && trace && (
        <div className="space-y-8 animate-in fade-in duration-500">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Initial Failure Context</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-zinc-300">
                <div className="flex justify-between items-center pb-2 border-b border-zinc-800/50">
                  <span>Amount:</span>
                  <span className="font-mono text-zinc-100">{formatMoney(trace.initial_failure.amount_minor, "INR")}</span>
                </div>
                <div className="flex justify-between items-center pb-2 border-b border-zinc-800/50">
                  <span>Failure Reason:</span>
                  <Badge variant="outline" className="font-mono text-amber-400">{trace.initial_failure.failure_reason}</Badge>
                </div>
                <div className="flex justify-between items-center">
                  <span>Payment Method:</span>
                  <span className="font-mono">{trace.initial_failure.payment_method}</span>
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>Final Outcome</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-zinc-300">
                <div className="flex justify-between items-center pb-2 border-b border-zinc-800/50">
                  <span>Status:</span>
                  <Badge variant={trace.final.recovered ? "default" : "destructive"}>
                    {trace.final.recovered ? "RECOVERED" : "FAILED"}
                  </Badge>
                </div>
                <div className="flex justify-between items-center pb-2 border-b border-zinc-800/50">
                  <span>Recovered Amount:</span>
                  <span className="font-mono text-zinc-100">{formatMoney(trace.final.recovered_amount_minor, "INR")}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span>Action Count:</span>
                  <span className="font-mono text-zinc-100">{trace.final.action_count}</span>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <h2 className="text-xl font-bold tracking-tight text-zinc-100 flex items-center gap-2">
              <span className="w-2 h-6 bg-emerald-500 rounded-sm"></span>
              Decision Trace
            </h2>
            
            {trace.decisions.map((decision: any, index: number) => (
              <Card key={index} className="overflow-hidden border-zinc-800/50 bg-zinc-900/20 transition-all hover:border-zinc-700/50">
                <CardHeader className="bg-zinc-900/40 border-b border-zinc-800/50 flex flex-row items-center justify-between pb-4">
                  <div>
                    <CardTitle className="text-lg text-emerald-500">Decision Step {decision.decision_index}</CardTitle>
                    <div className="text-sm text-zinc-500 font-mono mt-1 flex gap-4">
                      <span>Elapsed: {decision.observable_context.elapsed_hours}h</span>
                      <span>Contacts: {decision.observable_context.contacts}</span>
                    </div>
                  </div>
                  <Badge variant="default" className="font-mono text-sm px-3 py-1 shadow-lg bg-emerald-900/30 text-emerald-400 border border-emerald-500/30">
                    {decision.action_selected || "STOP"}
                  </Badge>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="w-full overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-zinc-900/60 text-zinc-400 text-xs uppercase tracking-wider">
                        <tr>
                          <th className="px-6 py-3 text-left font-medium">Candidate Action</th>
                          <th className="px-6 py-3 text-right font-medium">Policy Score</th>
                          <th className="px-6 py-3 text-right font-medium">Incremental ERV</th>
                          <th className="px-6 py-3 text-right font-medium">Model Bin</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-zinc-800/50">
                        {decision.candidates.map((cand: any, i: number) => {
                          const isSelected = cand.action === decision.action_selected;
                          return (
                            <tr key={i} className={`group transition-colors ${isSelected ? "bg-emerald-900/10" : "hover:bg-zinc-800/30"}`}>
                              <td className="px-6 py-4 whitespace-nowrap">
                                <div className="flex items-center">
                                  <span className={`font-mono text-xs ${isSelected ? "text-emerald-400 font-bold" : "text-zinc-300"}`}>
                                    {cand.action}
                                  </span>
                                  {isSelected && (
                                    <span className="ml-3 inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500 text-zinc-950 uppercase tracking-widest shadow-sm">
                                      Selected
                                    </span>
                                  )}
                                </div>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right font-mono text-zinc-400 group-hover:text-zinc-300 transition-colors">
                                {cand.policy_score?.toFixed(4) || "N/A"}
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right font-mono">
                                <span className={cand.incremental_erv_minor > 0 ? "text-emerald-400" : "text-zinc-500"}>
                                  {cand.incremental_erv_minor > 0 ? "+" : ""}{formatMoney(cand.incremental_erv_minor, "INR")}
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-right">
                                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-zinc-800 text-xs font-mono text-zinc-300 border border-zinc-700">
                                  {cand.calibration_bin}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
