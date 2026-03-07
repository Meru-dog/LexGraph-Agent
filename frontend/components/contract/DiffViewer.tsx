"use client";

import { useState } from "react";
import type { DiffLine as DiffLineType } from "@/lib/types";
import DiffLine from "./DiffLine";

interface Props {
  diff: DiffLineType[];
  filename: string;
}

export default function DiffViewer({ diff, filename }: Props) {
  const [mode, setMode] = useState<"split" | "unified">("split");

  const removedLines = diff.filter((l) => l.type !== "added");
  const addedLines = diff.filter((l) => l.type !== "removed");

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div
        className="flex items-center justify-between px-4 py-2.5 border-b border-[#E5E7EB] bg-white flex-shrink-0"
      >
        <span
          className="text-[12px] text-[#4F46E5] font-medium"
          style={{ fontFamily: "var(--font-ibm-plex-mono)" }}
        >
          {filename}
        </span>
        <div className="flex gap-1">
          {(["split", "unified"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className="px-3 py-1 text-[11px] font-medium rounded"
              style={{
                background: mode === m ? "#EEF2FF" : "#F9FAFB",
                border: `1px solid ${mode === m ? "#C7D2FA" : "#E5E7EB"}`,
                color: mode === m ? "#4F46E5" : "#6B7280",
              }}
            >
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Diff content */}
      <div className="flex-1 overflow-hidden">
        {mode === "split" ? (
          <div className="flex h-full">
            {/* Left: Original (removed + same) */}
            <div className="flex-1 overflow-auto border-r border-[#E5E7EB]">
              <div
                className="sticky top-0 px-3 py-1.5 text-[12px] font-semibold z-10"
                style={{ background: "#FEF2F2", color: "#DC2626", fontFamily: "var(--font-ibm-plex-mono)" }}
              >
                − Original
              </div>
              <div className="text-[12px]">
                {removedLines.map((line, i) => <DiffLine key={i} line={line} />)}
              </div>
            </div>

            {/* Right: Reviewed (added + same) */}
            <div className="flex-1 overflow-auto">
              <div
                className="sticky top-0 px-3 py-1.5 text-[12px] font-semibold z-10"
                style={{ background: "#F0FDF4", color: "#15803D", fontFamily: "var(--font-ibm-plex-mono)" }}
              >
                + AI Redline
              </div>
              <div className="text-[12px]">
                {addedLines.map((line, i) => <DiffLine key={i} line={line} />)}
              </div>
            </div>
          </div>
        ) : (
          <div className="h-full overflow-auto">
            {diff.map((line, i) => <DiffLine key={i} line={line} />)}
          </div>
        )}
      </div>
    </div>
  );
}
