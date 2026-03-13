// ─── LLM Model ────────────────────────────────────────────────────────────────

export type LLMModel = "gemini" | "llama" | "fine_tuned";

// ─── Chat ─────────────────────────────────────────────────────────────────────

export type Role = "user" | "assistant";

export interface Citation {
  node_id: string;
  type: "Statute" | "Case" | "Provision";
  title: string;
  article: string;
  url: string | null;
}

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  citations?: Citation[];
  timestamp: Date;
}

export type Jurisdiction = "JP" | "US" | "JP+US" | "auto";

// ─── DD Agent ─────────────────────────────────────────────────────────────────

export type RiskLevel = "critical" | "high" | "medium" | "low" | "ok" | "warn";

export interface DDFinding {
  status: RiskLevel;
  text: string;
}

export interface DDSection {
  num: string;
  title: string;
  items: DDFinding[];
}

export interface DDSummary {
  critical: number;
  high: number;
  medium: number;
  low: number;
  recommendation: string;
}

export interface DDReport {
  target: string;
  transaction: string;
  date: string;
  jurisdiction: string;
  summary: DDSummary;
  sections: DDSection[];
}

export type DDStatus = "idle" | "running" | "awaiting_review" | "complete" | "error";

export interface DDAgentState {
  status: DDStatus;
  currentStep: number;
  report: DDReport | null;
}

// ─── Contract Review ──────────────────────────────────────────────────────────

export type DiffType = "same" | "added" | "removed";

export interface DiffLine {
  type: DiffType;
  text: string;
}

export interface ClauseAnnotation {
  clauseRef: string;
  title: string;
  risk: RiskLevel;
  notes: string;       // semicolon-separated issues
  reason?: string;     // one-sentence reason for the redline change
  textSnippet?: string; // first ~120 chars of original clause text (for diff matching)
}

export interface ContractReviewResult {
  filename: string;
  addedCount: number;
  deletedCount: number;
  diff: DiffLine[];
  clauses: ClauseAnnotation[];
}

// ─── Graph ────────────────────────────────────────────────────────────────────

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  jurisdiction: string;
}

export interface GraphEdge {
  from: string;
  to: string;
  type: string;
}
