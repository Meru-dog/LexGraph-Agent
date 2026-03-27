"use client";

import { useEffect, useState } from "react";
import type { DDStatus } from "@/lib/types";
import type { DDHistoryEntry } from "@/hooks/useDDAgent";
import StepProgress from "./StepProgress";
import type { DDReport } from "@/lib/types";
import { getAvailableModels } from "@/lib/api";

const JURISDICTIONS: { key: string; label: string }[] = [
  { key: "JP", label: "JP" },
  { key: "US", label: "US" },
  { key: "JP+US", label: "JP+US" },
];

interface ModelOption {
  id: string;
  name: string;
  type: string;
  available: boolean;
}

interface Props {
  prompt: string;
  jurisdiction: string;
  modelName: string;
  status: DDStatus;
  currentStep: number;
  history: DDHistoryEntry[];
  onPromptChange: (v: string) => void;
  onJurisdictionChange: (v: string) => void;
  onModelChange: (v: string) => void;
  onRun: () => void;
  onReset: () => void;
  onSelectHistory: (entry: DDHistoryEntry) => void;
}

function ModelIcon({ type, id }: { type: string; id: string }) {
  if (id === "fine_tuned") return <span className="text-[11px]">★</span>;
  if (type === "local") return <span className="text-[11px]">⬡</span>;
  return <span className="text-[11px]">☁</span>;
}

export default function DDPromptPanel({
  prompt,
  jurisdiction,
  modelName,
  status,
  currentStep,
  history,
  onPromptChange,
  onJurisdictionChange,
  onModelChange,
  onRun,
  onReset,
  onSelectHistory,
}: Props) {
  const isRunning = status === "running";
  const isComplete = status === "complete";
  const isError = status === "error";
  const isDone = isComplete || isError;

  const [models, setModels] = useState<ModelOption[]>([
    { id: "ollama", name: "Qwen3 Swallow 8B", type: "local", available: false },
  ]);
  const [modelsLoaded, setModelsLoaded] = useState(false);

  useEffect(() => {
    getAvailableModels()
      .then((data) => {
        if (data && data.length > 0) setModels(data);
        setModelsLoaded(true);
      })
      .catch(() => setModelsLoaded(true));
  }, []);

  return (
    <div className="w-[296px] flex-shrink-0 border-r border-[#E5E7EB] bg-white flex flex-col h-full overflow-y-auto">
      {/* Panel header */}
      <div className="px-5 pt-[18px] pb-[14px] border-b border-[#F3F4F6]">
        <div className="text-[15px] font-semibold text-[#111827]">DD Agent</div>
        <div className="text-[11px] text-[#9CA3AF] mt-0.5">Automated legal due diligence as counsel</div>
      </div>

      <div className="p-5 flex flex-col gap-3">
        {/* Prompt textarea */}
        <div>
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
        <div>
          <label className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wide mb-1.5 block">
            Jurisdiction
          </label>
          <div className="flex gap-1">
            {JURISDICTIONS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => onJurisdictionChange(key)}
                disabled={isRunning}
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

        {/* Model selector */}
        <div>
          <label className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wide mb-1.5 block">
            LLM Model
          </label>
          <div className="flex flex-col gap-1">
            {models.map((m) => {
              const isSelected = modelName === m.id;
              const isUnavailable = !m.available;
              return (
                <button
                  key={m.id}
                  onClick={() => !isUnavailable && !isRunning && onModelChange(m.id)}
                  disabled={isRunning || isUnavailable}
                  title={isUnavailable ? "Install via Ollama to enable this model" : undefined}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-lg transition-colors text-left"
                  style={{
                    background: isSelected ? "#EEF2FF" : "#F9FAFB",
                    border: `1px solid ${isSelected ? "#C7D2FA" : "#E5E7EB"}`,
                    opacity: isUnavailable ? 0.45 : 1,
                    cursor: isUnavailable || isRunning ? "not-allowed" : "pointer",
                  }}
                >
                  {/* Status dot */}
                  <span
                    className="flex-shrink-0 w-2 h-2 rounded-full"
                    style={{ background: m.available ? "#22C55E" : "#D1D5DB" }}
                  />
                  {/* Model icon */}
                  <span style={{ color: isSelected ? "#4F46E5" : "#9CA3AF" }}>
                    <ModelIcon type={m.type} id={m.id} />
                  </span>
                  {/* Model name */}
                  <span
                    className="flex-1 text-[11px] font-medium truncate"
                    style={{ color: isSelected ? "#4F46E5" : isUnavailable ? "#9CA3AF" : "#374151" }}
                  >
                    {m.name}
                  </span>
                  {/* Type badge */}
                  <span
                    className="text-[9px] px-1.5 py-0.5 rounded"
                    style={{
                      background: m.type === "cloud" ? "#EFF6FF" : "#F0FDF4",
                      color: m.type === "cloud" ? "#2563EB" : "#15803D",
                    }}
                  >
                    {m.type === "cloud" ? "cloud" : "local"}
                  </span>
                </button>
              );
            })}
          </div>
          {modelsLoaded && models.some((m) => !m.available) && (
            <div className="mt-1.5 text-[10px] text-[#9CA3AF] leading-tight">
              Local models require Ollama. Run: <code className="text-[#6B7280]">ollama pull llama3.1:8b</code>
            </div>
          )}
        </div>

        {/* Action buttons */}
        {isDone ? (
          <button
            onClick={onReset}
            className="w-full py-2.5 text-[13px] font-semibold rounded-lg transition-colors"
            style={{ background: "#F0FDF4", border: "1px solid #BBF7D0", color: "#15803D" }}
          >
            + New DD Analysis
          </button>
        ) : (
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
        )}

        {/* While running, also allow cancelling to start over */}
        {isRunning && (
          <button
            onClick={onReset}
            className="w-full py-1.5 text-[11px] rounded-lg transition-colors"
            style={{ background: "#FEF2F2", border: "1px solid #FECACA", color: "#DC2626" }}
          >
            Cancel
          </button>
        )}

        {/* Step progress */}
        {status !== "idle" && <StepProgress currentStep={currentStep} />}

        {/* History */}
        {history.length > 0 && (
          <div className="mt-1 border-t border-[#F3F4F6] pt-3">
            <div className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wide mb-2">
              Recent Runs
            </div>
            <div className="flex flex-col gap-1.5">
              {history.map((entry) => (
                <button
                  key={entry.taskId}
                  onClick={() => onSelectHistory(entry)}
                  className="w-full text-left px-3 py-2 rounded-lg transition-colors hover:bg-[#F9FAFB]"
                  style={{ border: "1px solid #F3F4F6" }}
                >
                  <div className="text-[11px] text-[#374151] line-clamp-1 font-medium">
                    {entry.prompt.slice(0, 55)}{entry.prompt.length > 55 ? "…" : ""}
                  </div>
                  <div className="text-[9px] text-[#9CA3AF] mt-0.5">
                    {entry.jurisdiction} · {new Date(entry.completedAt).toLocaleString()}
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
