"use client";

import type { Jurisdiction, DDStatus } from "@/lib/types";
import StepProgress from "./StepProgress";

const JURISDICTIONS: { key: string; label: string }[] = [
  { key: "JP", label: "JP" },
  { key: "US", label: "US" },
  { key: "JP+US", label: "JP+US" },
];

interface Props {
  prompt: string;
  jurisdiction: string;
  status: DDStatus;
  currentStep: number;
  onPromptChange: (v: string) => void;
  onJurisdictionChange: (v: string) => void;
  onRun: () => void;
}

export default function DDPromptPanel({
  prompt,
  jurisdiction,
  status,
  currentStep,
  onPromptChange,
  onJurisdictionChange,
  onRun,
}: Props) {
  const isRunning = status === "running";

  return (
    <div className="w-[296px] flex-shrink-0 border-r border-[#E5E7EB] bg-white flex flex-col h-full overflow-y-auto">
      <div className="p-5">
        {/* Prompt textarea */}
        <div className="mb-3">
          <label className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wide mb-1.5 block">
            DD Instruction
          </label>
          <textarea
            value={prompt}
            onChange={(e) => onPromptChange(e.target.value)}
            disabled={isRunning}
            rows={4}
            placeholder='e.g. "Our company wants to invest ¥2B in TechCorp KK. Please conduct full legal DD as our lawyer."'
            className="w-full text-[12px] text-[#374151] placeholder-[#9CA3AF] p-3 rounded-lg resize-y outline-none leading-[1.55]"
            style={{
              minHeight: "84px",
              background: "#F9FAFB",
              border: "1px solid #E5E7EB",
              fontFamily: "var(--font-ibm-plex-sans)",
            }}
          />
        </div>

        {/* Jurisdiction toggle */}
        <div className="mb-4">
          <label className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wide mb-1.5 block">
            Jurisdiction
          </label>
          <div className="flex gap-1">
            {JURISDICTIONS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => onJurisdictionChange(key)}
                className="flex-1 py-1.5 text-[12px] font-medium rounded-lg transition-colors"
                style={{
                  background: jurisdiction === key ? "#EEF2FF" : "#F9FAFB",
                  border: `1px solid ${jurisdiction === key ? "#C7D2FA" : "#E5E7EB"}`,
                  color: jurisdiction === key ? "#4F46E5" : "#6B7280",
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Run button */}
        <button
          onClick={onRun}
          disabled={isRunning || !prompt.trim()}
          className="w-full py-2.5 text-[13px] font-semibold rounded-lg transition-colors"
          style={{
            background: isRunning || !prompt.trim() ? "#E5E7EB" : "#2D4FD6",
            color: isRunning || !prompt.trim() ? "#9CA3AF" : "#FFFFFF",
          }}
        >
          {isRunning ? "⟳ Running DD Agent..." : "▶ Run DD Agent"}
        </button>

        {/* Step progress */}
        {status !== "idle" && <StepProgress currentStep={currentStep} />}
      </div>
    </div>
  );
}
