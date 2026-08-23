import type { RecoveryCaseSummary } from "@/lib/api";
import { formatMoney } from "@/lib/format";

function chartPoints(values: number[], width: number, height: number): string {
  const maximum = Math.max(...values, 1);
  return values.map((value, index) => {
    const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
    const y = height - (value / maximum) * (height - 18) - 9;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

export function RecoveryTrendChart({ cases }: { cases: RecoveryCaseSummary[] }) {
  const days = Array.from({ length: 7 }, (_, offset) => {
    const date = new Date();
    date.setHours(0, 0, 0, 0);
    date.setDate(date.getDate() - (6 - offset));
    return date;
  });
  const values = days.map((date) => cases.filter((item) => {
    const created = new Date(item.created_at);
    return item.status === "RECOVERED" && created.toDateString() === date.toDateString();
  }).reduce((sum, item) => sum + item.amount_minor, 0));
  const points = chartPoints(values, 620, 176);
  const total = values.reduce((sum, value) => sum + value, 0);

  return (
    <article className="surface-panel rounded-2xl p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><p className="eyebrow">Recovery trend</p><h2 className="mt-2 text-lg font-semibold">Recovered value by case date</h2></div>
        <div className="text-right"><p className="text-xs text-muted-foreground">7-day total</p><p className="mt-1 font-mono text-sm font-semibold text-primary">{formatMoney(total)}</p></div>
      </div>
      <div className="mt-6 overflow-hidden rounded-xl border bg-[var(--surface-soft)] p-3">
        <svg viewBox="0 0 620 210" role="img" aria-label="Seven day recovered value chart" className="h-48 w-full overflow-visible">
          <defs><linearGradient id="recovery-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--primary)" stopOpacity="0.28" /><stop offset="100%" stopColor="var(--primary)" stopOpacity="0" /></linearGradient></defs>
          {[35, 78, 121, 164].map((y) => <line key={y} x1="0" y1={y} x2="620" y2={y} stroke="var(--chart-grid)" strokeWidth="1" />)}
          <polygon points={`0,190 ${points} 620,190`} fill="url(#recovery-area)" />
          <polyline points={points} fill="none" stroke="var(--primary)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" className="chart-line" />
          {values.map((value, index) => {
            const [x, y] = chartPoints(values, 620, 176).split(" ")[index].split(",");
            return <circle key={`${index}-${value}`} cx={x} cy={y} r="4" fill="var(--card)" stroke="var(--primary)" strokeWidth="2.5" />;
          })}
          {days.map((day, index) => <text key={day.toISOString()} x={(index / 6) * 620} y="207" textAnchor={index === 0 ? "start" : index === 6 ? "end" : "middle"} fill="var(--muted-foreground)" fontSize="10">{day.toLocaleDateString("en-IN", { weekday: "short" })}</text>)}
        </svg>
      </div>
      <p className="mt-3 text-[11px] leading-5 text-muted-foreground">Uses persisted recovered cases grouped by their creation date; it is not a forecast.</p>
    </article>
  );
}

export function RecoveryDonut({ recovered, active, terminal }: { recovered: number; active: number; terminal: number }) {
  const total = Math.max(recovered + active + terminal, 1);
  const recoveredPart = (recovered / total) * 100;
  const activePart = (active / total) * 100;
  return (
    <article className="surface-panel rounded-2xl p-5 sm:p-6">
      <p className="eyebrow">Case distribution</p><h2 className="mt-2 text-lg font-semibold">Current recovery states</h2>
      <div className="mt-5 flex flex-col items-center gap-6 sm:flex-row">
        <div className="relative size-40 shrink-0">
          <svg viewBox="0 0 42 42" className="size-full -rotate-90" role="img" aria-label={`${recovered} recovered, ${active} active, ${terminal} terminal cases`}>
            <circle cx="21" cy="21" r="15.915" fill="none" stroke="var(--muted)" strokeWidth="5" />
            <circle cx="21" cy="21" r="15.915" fill="none" stroke="var(--primary)" strokeWidth="5" strokeDasharray={`${recoveredPart} ${100 - recoveredPart}`} strokeDashoffset="0" />
            <circle cx="21" cy="21" r="15.915" fill="none" stroke="#38bdf8" strokeWidth="5" strokeDasharray={`${activePart} ${100 - activePart}`} strokeDashoffset={-recoveredPart} />
          </svg>
          <div className="absolute inset-0 grid place-items-center text-center"><div><p className="text-2xl font-bold">{recovered + active + terminal}</p><p className="text-[10px] text-muted-foreground uppercase">cases</p></div></div>
        </div>
        <dl className="w-full space-y-3">
          <Legend color="bg-primary" label="Recovered" value={recovered} />
          <Legend color="bg-sky-400" label="Active" value={active} />
          <Legend color="bg-muted-foreground/45" label="Stopped / failed" value={terminal} />
        </dl>
      </div>
    </article>
  );
}

function Legend({ color, label, value }: { color: string; label: string; value: number }) {
  return <div className="flex items-center rounded-xl border bg-card/50 px-3 py-2.5"><span className={`mr-2.5 size-2 rounded-full ${color}`} /><dt className="text-xs text-muted-foreground">{label}</dt><dd className="ml-auto font-mono text-xs font-semibold">{value}</dd></div>;
}

