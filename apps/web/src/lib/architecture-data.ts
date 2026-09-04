import { LucideIcon, BrainCircuit, Activity, Database, Scale, ShieldCheck, Clock, CreditCard, UserCircle, StopCircle, CheckCircle2, MessageSquare, AlertCircle, RefreshCw, Zap } from "lucide-react";

export type NodeShape = 'rounded' | 'diamond' | 'hexagon' | 'cloud' | 'cylinder' | 'octagon' | 'circle' | 'human';
export type EvidenceLane = 'decision' | 'provider';
export type NodeColor = 'cyan' | 'electric' | 'violet' | 'magenta' | 'amber' | 'teal' | 'emerald' | 'gold' | 'red' | 'aqua' | 'slate' | 'blue';

export interface ArchitectureStage {
  id: string;
  lane: EvidenceLane;
  label: string;
  sublabel?: string;
  icon: LucideIcon;
  color: NodeColor;
  shape: NodeShape;
  
  whatIsThis: string;
  whatGoesIn: string;
  whatHappens: string;
  whatComesOut: string;
  whyDoesItMatter: string;
  evidenceType?: string;
  whereToSeeIt?: string;
}

export interface ArchitectureEdge {
  id: string;
  sourceId: string;
  targetId: string;
  label?: string;
}

export interface ArchitectureScenario {
  id: string;
  label: string;
  description: string;
  activeStageIds: string[];
  activeEdgeIds: string[];
  finalOutcome: string;
  colorTheme: NodeColor;
}

export const ARCHITECTURE_STAGES: ArchitectureStage[] = [
  // ==========================================
  // LANE 1: DECISION ENGINE
  // ==========================================
  {
    id: "dec-failed", lane: "decision", label: "FAILED PAYMENT", icon: AlertCircle, color: "red", shape: "rounded",
    whatIsThis: "Initial trigger.", whatGoesIn: "Payment failed webhook.", whatHappens: "Registers failure.", whatComesOut: "Failed state.", whyDoesItMatter: "Starts process."
  },
  {
    id: "dec-context", lane: "decision", label: "OBSERVABLE CONTEXT", icon: Database, color: "cyan", shape: "rounded",
    whatIsThis: "Current state.", whatGoesIn: "User history.", whatHappens: "Aggregates features.", whatComesOut: "Context vector.", whyDoesItMatter: "Feeds ML."
  },
  {
    id: "dec-feasible", lane: "decision", label: "FEASIBLE ACTIONS", icon: Zap, color: "electric", shape: "rounded",
    whatIsThis: "Available actions.", whatGoesIn: "Context.", whatHappens: "Filters allowed actions.", whatComesOut: "List of candidates.", whyDoesItMatter: "Narrows search."
  },
  // Feasible Left
  {
    id: "dec-f-now", lane: "decision", label: "RETRY NOW", icon: RefreshCw, color: "blue", shape: "rounded",
    whatIsThis: "Retry.", whatGoesIn: "-", whatHappens: "-", whatComesOut: "-", whyDoesItMatter: "-"
  },
  {
    id: "dec-f-2h", lane: "decision", label: "RETRY LATER - 2H", icon: Clock, color: "blue", shape: "rounded",
    whatIsThis: "Retry.", whatGoesIn: "-", whatHappens: "-", whatComesOut: "-", whyDoesItMatter: "-"
  },
  {
    id: "dec-f-24h", lane: "decision", label: "RETRY LATER - 24H", icon: Clock, color: "blue", shape: "rounded",
    whatIsThis: "Retry.", whatGoesIn: "-", whatHappens: "-", whatComesOut: "-", whyDoesItMatter: "-"
  },
  // Feasible Right
  {
    id: "dec-f-nudge", lane: "decision", label: "SEND NUDGE", icon: MessageSquare, color: "electric", shape: "rounded",
    whatIsThis: "Nudge.", whatGoesIn: "-", whatHappens: "-", whatComesOut: "-", whyDoesItMatter: "-"
  },
  {
    id: "dec-f-plink", lane: "decision", label: "CREATE PAYMENT LINK", icon: CreditCard, color: "emerald", shape: "rounded",
    whatIsThis: "Link.", whatGoesIn: "-", whatHappens: "-", whatComesOut: "-", whyDoesItMatter: "-"
  },
  {
    id: "dec-f-alt", lane: "decision", label: "ALTERNATE METHOD", icon: Database, color: "blue", shape: "rounded",
    whatIsThis: "Alt.", whatGoesIn: "-", whatHappens: "-", whatComesOut: "-", whyDoesItMatter: "-"
  },
  {
    id: "dec-model", lane: "decision", label: "MODEL V2", sublabel: "scores every feasible action", icon: BrainCircuit, color: "electric", shape: "rounded",
    whatIsThis: "Probability Engine.", whatGoesIn: "Features.", whatHappens: "Predicts recovery.", whatComesOut: "Probabilities.", whyDoesItMatter: "Action-conditioned ML."
  },
  // Probs Left
  {
    id: "dec-p-now", lane: "decision", label: "RETRY NOW", sublabel: "P(recovery | customer, Retry Now)", icon: Activity, color: "blue", shape: "rounded",
    whatIsThis: "Score.", whatGoesIn: "-", whatHappens: "-", whatComesOut: "-", whyDoesItMatter: "-"
  },
  {
    id: "dec-p-2h", lane: "decision", label: "RETRY LATER - 2H", sublabel: "P(recovery | customer, Retry 2H)", icon: Activity, color: "blue", shape: "rounded",
    whatIsThis: "Score.", whatGoesIn: "-", whatHappens: "-", whatComesOut: "-", whyDoesItMatter: "-"
  },
  {
    id: "dec-p-24h", lane: "decision", label: "RETRY LATER - 24H", sublabel: "P(recovery | customer, Retry 24H)", icon: Activity, color: "blue", shape: "rounded",
    whatIsThis: "Score.", whatGoesIn: "-", whatHappens: "-", whatComesOut: "-", whyDoesItMatter: "-"
  },
  // Probs Right
  {
    id: "dec-p-nudge", lane: "decision", label: "SEND NUDGE", sublabel: "P(recovery | customer, Nudge)", icon: Activity, color: "electric", shape: "rounded",
    whatIsThis: "Score.", whatGoesIn: "-", whatHappens: "-", whatComesOut: "-", whyDoesItMatter: "-"
  },
  {
    id: "dec-p-plink", lane: "decision", label: "PAYMENT LINK", sublabel: "P(recovery | customer, P.Link)", icon: Activity, color: "emerald", shape: "rounded",
    whatIsThis: "Score.", whatGoesIn: "-", whatHappens: "-", whatComesOut: "-", whyDoesItMatter: "-"
  },
  {
    id: "dec-p-alt", lane: "decision", label: "ALTERNATE METHOD", sublabel: "P(recovery | customer, Alt)", icon: Activity, color: "blue", shape: "rounded",
    whatIsThis: "Score.", whatGoesIn: "-", whatHappens: "-", whatComesOut: "-", whyDoesItMatter: "-"
  },
  {
    id: "dec-erv", lane: "decision", label: "ERV", sublabel: "P(recovery) × payment value − intervention / friction", icon: Activity, color: "violet", shape: "rounded",
    whatIsThis: "Expected Value.", whatGoesIn: "Probs + cost.", whatHappens: "Calculates net value.", whatComesOut: "ERV.", whyDoesItMatter: "Optimizes economics."
  },
  {
    id: "dec-rank", lane: "decision", label: "ECONOMIC RANKING", icon: Scale, color: "gold", shape: "rounded",
    whatIsThis: "Sorting.", whatGoesIn: "ERV list.", whatHappens: "Sorts.", whatComesOut: "Top action.", whyDoesItMatter: "Finds best."
  },
  {
    id: "dec-policy", lane: "decision", label: "SEQUENTIAL POLICY V2", sublabel: "safety + limits + support", icon: ShieldCheck, color: "magenta", shape: "rounded",
    whatIsThis: "Guardrails.", whatGoesIn: "Top action.", whatHappens: "Checks budgets.", whatComesOut: "Authorized intent.", whyDoesItMatter: "Financial safety."
  },
  {
    id: "dec-stop", lane: "decision", label: "STOP", icon: StopCircle, color: "red", shape: "rounded",
    whatIsThis: "Halt.", whatGoesIn: "Exhausted budget.", whatHappens: "Ends.", whatComesOut: "Terminal.", whyDoesItMatter: "No spam."
  },
  {
    id: "dec-human", lane: "decision", label: "HUMAN REVIEW", icon: UserCircle, color: "gold", shape: "rounded",
    whatIsThis: "Escalation.", whatGoesIn: "Low confidence.", whatHappens: "Escalates.", whatComesOut: "Queue.", whyDoesItMatter: "Safe fallback."
  },
  {
    id: "dec-action", lane: "decision", label: "ACTION", icon: Zap, color: "emerald", shape: "rounded",
    whatIsThis: "Intent to execute.", whatGoesIn: "Approved intent.", whatHappens: "Passes to executor.", whatComesOut: "Dispatch.", whyDoesItMatter: "Ends decision phase."
  },

  // ==========================================
  // LANE 2: PROVIDER EXECUTION
  // ==========================================
  {
    id: "prov-auth", lane: "provider", label: "AUTHORIZED ACTION", icon: ShieldCheck, color: "emerald", shape: "rounded",
    whatIsThis: "Validated action.", whatGoesIn: "Intent.", whatHappens: "Reserves.", whatComesOut: "Reservation.", whyDoesItMatter: "Idempotency."
  },
  {
    id: "prov-req", lane: "provider", label: "EXECUTION REQUEST", icon: Database, color: "gold", shape: "rounded",
    whatIsThis: "API Payload.", whatGoesIn: "Data.", whatHappens: "Formats.", whatComesOut: "JSON.", whyDoesItMatter: "Network dispatch."
  },
  {
    id: "prov-test", lane: "provider", label: "RAZORPAY TEST MODE", sublabel: "No real money", icon: CreditCard, color: "teal", shape: "rounded",
    whatIsThis: "Provider sandbox.", whatGoesIn: "Request.", whatHappens: "Creates link.", whatComesOut: "plink_id.", whyDoesItMatter: "External state."
  },
  {
    id: "prov-webhook", lane: "provider", label: "PROVIDER EVENT / WEBHOOK", icon: Zap, color: "cyan", shape: "rounded",
    whatIsThis: "Callback.", whatGoesIn: "Payment.", whatHappens: "Notifies.", whatComesOut: "Raw bytes.", whyDoesItMatter: "Asynchronous truth."
  },
  {
    id: "prov-sig", lane: "provider", label: "SIGNATURE VERIFICATION", icon: ShieldCheck, color: "emerald", shape: "rounded",
    whatIsThis: "Security.", whatGoesIn: "Webhook.", whatHappens: "Validates HMAC.", whatComesOut: "Trusted payload.", whyDoesItMatter: "Authenticity."
  },
  {
    id: "prov-fetch", lane: "provider", label: "INDEPENDENT PROVIDER FETCH", icon: Database, color: "cyan", shape: "rounded",
    whatIsThis: "REST Fetch.", whatGoesIn: "ID.", whatHappens: "Gets state.", whatComesOut: "State.", whyDoesItMatter: "Double check."
  },
  {
    id: "prov-truth", lane: "provider", label: "PROVIDER TRUTH", sublabel: "webhook + provider fetch agree", icon: CheckCircle2, color: "emerald", shape: "rounded",
    whatIsThis: "Triangulation.", whatGoesIn: "Both inputs.", whatHappens: "Compares.", whatComesOut: "Truth.", whyDoesItMatter: "Certainty."
  },
  {
    id: "prov-outcome", lane: "provider", label: "EXTERNAL OUTCOME", icon: Database, color: "cyan", shape: "rounded",
    whatIsThis: "Local state.", whatGoesIn: "Truth.", whatHappens: "Saves.", whatComesOut: "Outcome ID.", whyDoesItMatter: "Persistence."
  },
  {
    id: "prov-attr", lane: "provider", label: "RECOVERY ATTRIBUTION", sublabel: "exactly-once local semantics", icon: Scale, color: "emerald", shape: "rounded",
    whatIsThis: "Accounting.", whatGoesIn: "Outcome.", whatHappens: "Links to case.", whatComesOut: "Attribution.", whyDoesItMatter: "No double counting."
  },
  {
    id: "prov-recovered", lane: "provider", label: "RECOVERED", icon: CheckCircle2, color: "emerald", shape: "circle",
    whatIsThis: "Success.", whatGoesIn: "Attribution.", whatHappens: "Ends.", whatComesOut: "Success.", whyDoesItMatter: "Goal achieved."
  }
];

export const ARCHITECTURE_EDGES: ArchitectureEdge[] = [
  // Decision Flow
  { id: "d1", sourceId: "dec-failed", targetId: "dec-context" },
  { id: "d2", sourceId: "dec-context", targetId: "dec-feasible" },
  { id: "d3", sourceId: "dec-feasible", targetId: "dec-f-now" },
  { id: "d4", sourceId: "dec-feasible", targetId: "dec-f-nudge" },
  { id: "d5", sourceId: "dec-f-now", targetId: "dec-model" },
  { id: "d6", sourceId: "dec-f-nudge", targetId: "dec-model" },
  
  { id: "d7", sourceId: "dec-model", targetId: "dec-p-now" },
  { id: "d8", sourceId: "dec-model", targetId: "dec-p-nudge" },
  { id: "d9", sourceId: "dec-p-now", targetId: "dec-erv" },
  { id: "d10", sourceId: "dec-p-nudge", targetId: "dec-erv" },

  { id: "d11", sourceId: "dec-erv", targetId: "dec-rank" },
  { id: "d12", sourceId: "dec-rank", targetId: "dec-policy" },

  { id: "d13", sourceId: "dec-policy", targetId: "dec-stop" },
  { id: "d14", sourceId: "dec-policy", targetId: "dec-human" },
  { id: "d15", sourceId: "dec-policy", targetId: "dec-action" },

  // Cross-lane
  { id: "cross", sourceId: "dec-action", targetId: "prov-auth" },

  // Provider Flow
  { id: "p1", sourceId: "prov-auth", targetId: "prov-req" },
  { id: "p2", sourceId: "prov-req", targetId: "prov-test" },
  { id: "p3", sourceId: "prov-test", targetId: "prov-webhook" },
  { id: "p4", sourceId: "prov-webhook", targetId: "prov-sig" },
  { id: "p5", sourceId: "prov-sig", targetId: "prov-fetch" },
  { id: "p6", sourceId: "prov-fetch", targetId: "prov-truth" },
  { id: "p7", sourceId: "prov-truth", targetId: "prov-outcome" },
  { id: "p8", sourceId: "prov-outcome", targetId: "prov-attr" },
  { id: "p9", sourceId: "prov-attr", targetId: "prov-recovered" }
];

export const SCENARIOS: ArchitectureScenario[] = [
  {
    id: "full",
    label: "Full System Architecture",
    description: "The complete macroscopic view from Failed Payment to Recovered.",
    colorTheme: "slate",
    activeStageIds: ARCHITECTURE_STAGES.map(s => s.id),
    activeEdgeIds: ARCHITECTURE_EDGES.map(e => e.id),
    finalOutcome: "ARCHITECTURE LOADED"
  },
  {
    id: "decision-success",
    label: "Decision Engine → Execution",
    description: "The happy path where the decision engine authorizes an action and provider successfully recovers it.",
    colorTheme: "emerald",
    activeStageIds: [
      "dec-failed", "dec-context", "dec-feasible", "dec-f-now", "dec-f-2h", "dec-f-24h", "dec-f-nudge", "dec-f-plink", "dec-f-alt", "dec-model", 
      "dec-p-now", "dec-p-2h", "dec-p-24h", "dec-p-nudge", "dec-p-plink", "dec-p-alt", "dec-erv", "dec-rank", "dec-policy", "dec-action",
      "prov-auth", "prov-req", "prov-test", "prov-webhook", "prov-sig", "prov-fetch", 
      "prov-truth", "prov-outcome", "prov-attr", "prov-recovered"
    ],
    activeEdgeIds: [
      "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "d9", "d10", "d11", "d12", "d15",
      "cross", "p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9"
    ],
    finalOutcome: "RECOVERED"
  },
  {
    id: "bounded-stop",
    label: "Bounded Stop (Negative ERV)",
    description: "The decision engine evaluates feasible actions but ERV shows negative expected value, so it stops safely.",
    colorTheme: "red",
    activeStageIds: [
      "dec-failed", "dec-context", "dec-feasible", "dec-f-now", "dec-f-2h", "dec-f-24h", "dec-f-nudge", "dec-f-plink", "dec-f-alt", "dec-model", 
      "dec-p-now", "dec-p-2h", "dec-p-24h", "dec-p-nudge", "dec-p-plink", "dec-p-alt", "dec-erv", "dec-rank", "dec-policy", "dec-stop"
    ],
    activeEdgeIds: [
      "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "d9", "d10", "d11", "d12", "d13"
    ],
    finalOutcome: "STOP"
  },
  {
    id: "human-escalation",
    label: "Human Review Escalation",
    description: "Policy detects anomaly or insufficient support and escalates before execution.",
    colorTheme: "gold",
    activeStageIds: [
      "dec-failed", "dec-context", "dec-feasible", "dec-f-now", "dec-f-2h", "dec-f-24h", "dec-f-nudge", "dec-f-plink", "dec-f-alt", "dec-model", 
      "dec-p-now", "dec-p-2h", "dec-p-24h", "dec-p-nudge", "dec-p-plink", "dec-p-alt", "dec-erv", "dec-rank", "dec-policy", "dec-human"
    ],
    activeEdgeIds: [
      "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "d9", "d10", "d11", "d12", "d14"
    ],
    finalOutcome: "HUMAN REVIEW"
  }
];
