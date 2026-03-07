"use client";

import { useState } from "react";
import type { DiffLine as DiffLineType, ClauseAnnotation } from "@/lib/types";

const CONTEXT_LINES = 3;
const COLLAPSE_THRESHOLD = 8;

interface Props {
  diff: DiffLineType[];
  filename: string;
  clauses?: ClauseAnnotation[];
}

interface NumberedLine {
  line: DiffLineType;
  lineNo?: number; // original line number (undefined for pure additions)
}

interface Block {
  type: "same" | "changed";
  numbered: NumberedLine[];
  blockIndex: number;
}

// Assign original-file line numbers to each diff line.
function numberLines(diff: DiffLineType[]): NumberedLine[] {
  let n = 0;
  return diff.map((line) => {
    if (line.type !== "added") n++;
    return { line, lineNo: line.type !== "added" ? n : undefined };
  });
}

function buildBlocks(numbered: NumberedLine[]): Block[] {
  const blocks: Block[] = [];
  for (const item of numbered) {
    const gType = item.line.type === "same" ? "same" : "changed";
    const last = blocks[blocks.length - 1];
    if (last && last.type === gType) {
      last.numbered.push(item);
    } else {
      blocks.push({ type: gType, numbered: [item], blockIndex: blocks.length });
    }
  }
  return blocks;
}

const RISK_COLOR: Record<string, string> = {
  critical: "#DC2626", high: "#EA580C", medium: "#D97706", low: "#6B7280", ok: "#16A34A",
};

function matchClause(block: Block, clauses: ClauseAnnotation[]): ClauseAnnotation | null {
  if (!clauses.length) return null;
  const text = block.numbered.map((n) => n.line.text).join(" ").toLowerCase();
  for (const c of clauses) {
    if (text.includes(c.clauseRef.toLowerCase()) || text.includes(c.title.toLowerCase())) return c;
  }
  const order: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1, ok: 0 };
  return [...clauses].sort((a, b) => (order[b.risk] ?? 0) - (order[a.risk] ?? 0))[0] ?? null;
}

function DiffRow({ item }: { item: NumberedLine }) {
  const { line, lineNo } = item;
  const isAdded = line.type === "added";
  const isRemoved = line.type === "removed";
  return (
    <div
      className="flex text-[12px] leading-[1.75] select-text"
      style={{
        background: isAdded ? "#1a4731" : isRemoved ? "#4b1113" : "transparent",
        fontFamily: "var(--font-ibm-plex-mono)",
      }}
    >
      <span
        className="select-none flex-shrink-0 w-10 text-right pr-3 border-r text-[11px]"
        style={{
          color: isAdded ? "#4ae168" : isRemoved ? "#ff7b72" : "#484f58",
          borderColor: "#30363d",
          background: isAdded ? "#1b4332" : isRemoved ? "#67060c" : "#161b22",
        }}
      >
        {lineNo ?? ""}
      </span>
      <span
        className="flex-shrink-0 w-5 text-center select-none font-bold"
        style={{ color: isAdded ? "#3fb950" : isRemoved ? "#f85149" : "transparent" }}
      >
        {isAdded ? "+" : isRemoved ? "−" : " "}
      </span>
      <span
        className="flex-1 px-2 whitespace-pre-wrap break-all"
        style={{ color: isAdded ? "#aff5b4" : isRemoved ? "#ffdcd7" : "#8b949e" }}
      >
        {line.text || "\u00A0"}
      </span>
    </div>
  );
}

function TooltipCard({ clause, x, y }: { clause: ClauseAnnotation; x: number; y: number }) {
  const color = RISK_COLOR[clause.risk] ?? "#6B7280";
  const safeX = typeof window !== "undefined" ? Math.min(x + 14, window.innerWidth - 320) : x + 14;
  return (
    <div
      className="fixed z-50 rounded-lg shadow-2xl p-3 max-w-[300px] pointer-events-none"
      style={{ left: safeX, top: y - 8, background: "#1c2128", border: `1px solid ${color}55` }}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <span
          className="text-[9px] px-1.5 py-0.5 rounded font-bold uppercase"
          style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}
        >
          {clause.risk}
        </span>
        <span className="text-[11px] font-semibold" style={{ color: "#e6edf3" }}>
          {clause.clauseRef}
        </span>
      </div>
      {clause.notes && (
        <div className="text-[10px] leading-relaxed" style={{ color: "#8b949e" }}>
          {clause.notes.split(";").map((n, i) => (
            <div key={i}>· {n.trim()}</div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function DiffViewer({ diff, filename, clauses = [] }: Props) {
  const [tooltip, setTooltip] = useState<{ clause: ClauseAnnotation; x: number; y: number } | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const added = diff.filter((l) => l.type === "added").length;
  const removed = diff.filter((l) => l.type === "removed").length;

  const numbered = numberLines(diff);
  const blocks = buildBlocks(numbered);

  return (
    <div className="flex flex-col h-full" style={{ background: "#0d1117" }}>
      {/* Toolbar */}
      <div
        className="flex items-center gap-3 px-4 py-2 border-b flex-shrink-0"
        style={{ background: "#161b22", borderColor: "#30363d" }}
      >
        <span className="text-[12px] font-medium" style={{ color: "#58a6ff", fontFamily: "var(--font-ibm-plex-mono)" }}>
          {filename}
        </span>
        <span
          className="text-[11px] px-2 py-0.5 rounded-full font-semibold"
          style={{ background: "#1b433222", color: "#3fb950", border: "1px solid #3fb95044" }}
        >
          +{added}
        </span>
        <span
          className="text-[11px] px-2 py-0.5 rounded-full font-semibold"
          style={{ background: "#67060c22", color: "#f85149", border: "1px solid #f8514944" }}
        >
          −{removed}
        </span>
        {added === 0 && removed === 0 && (
          <span className="text-[11px]" style={{ color: "#484f58" }}>No changes detected</span>
        )}
      </div>

      {/* Diff content */}
      <div className="flex-1 overflow-auto">
        {blocks.map((block) => {
          if (block.type === "changed") {
            const matched = matchClause(block, clauses);
            const color = matched ? (RISK_COLOR[matched.risk] ?? "#6B7280") : "#484f58";
            return (
              <div
                key={block.blockIndex}
                className="relative group"
                onMouseMove={(e) => matched && setTooltip({ clause: matched, x: e.clientX, y: e.clientY })}
                onMouseLeave={() => setTooltip(null)}
              >
                {block.numbered.map((item, li) => <DiffRow key={li} item={item} />)}
                {matched && (
                  <div
                    className="absolute right-2 top-1 opacity-0 group-hover:opacity-100 transition-opacity text-[9px] px-1.5 py-0.5 rounded pointer-events-none"
                    style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}
                  >
                    {matched.risk.toUpperCase()} · {matched.clauseRef}
                  </div>
                )}
              </div>
            );
          }

          // same block
          const items = block.numbered;
          const isExpanded = expanded.has(block.blockIndex);

          if (items.length <= COLLAPSE_THRESHOLD || isExpanded) {
            return (
              <div key={block.blockIndex}>
                {items.map((item, li) => <DiffRow key={li} item={item} />)}
              </div>
            );
          }

          // Collapsed
          const top = items.slice(0, CONTEXT_LINES);
          const bottom = items.slice(-CONTEXT_LINES);
          const hidden = items.length - CONTEXT_LINES * 2;

          return (
            <div key={block.blockIndex}>
              {top.map((item, li) => <DiffRow key={`t${li}`} item={item} />)}
              <div
                className="flex items-center gap-3 px-4 py-1.5 cursor-pointer hover:bg-[#1c2128] transition-colors"
                style={{ borderTop: "1px solid #30363d", borderBottom: "1px solid #30363d" }}
                onClick={() => setExpanded((s) => { const n = new Set(s); n.add(block.blockIndex); return n; })}
              >
                <span style={{ color: "#58a6ff", fontSize: 11 }}>▸ {hidden} unchanged lines</span>
                <span style={{ color: "#484f58", fontSize: 10 }}>click to expand</span>
              </div>
              {bottom.map((item, li) => <DiffRow key={`b${li}`} item={item} />)}
            </div>
          );
        })}
      </div>

      {tooltip && <TooltipCard clause={tooltip.clause} x={tooltip.x} y={tooltip.y} />}
    </div>
  );
}
