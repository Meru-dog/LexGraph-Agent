"use client";

import { useState, useEffect } from "react";
import PageHeader from "@/components/layout/PageHeader";
import UploadZone from "@/components/contract/UploadZone";
import ClauseAnnotationCard from "@/components/contract/ClauseAnnotationCard";
import DiffViewer from "@/components/contract/DiffViewer";
import { useContractReviewContext } from "@/context/ContractReviewContext";
import { downloadRedlinedDocx, getAvailableModels } from "@/lib/api";
import { MOCK_DIFF, MOCK_CLAUSE_ANNOTATIONS } from "@/lib/mockData";
import { diffLines, countDiffStats } from "@/lib/diff";
import type { DiffLine, ClauseAnnotation } from "@/lib/types";

interface ModelOption {
  id: string;
  name: string;
  type: string;
  available: boolean;
}

export default function ContractReviewPage() {
  const { status, result, error, taskId, reviewFile, reset } = useContractReviewContext();
  const [modelName, setModelName] = useState("ollama");
  const [models, setModels] = useState<ModelOption[]>([
    { id: "ollama", name: "Qwen3 Swallow 8B", type: "local", available: false },
  ]);

  useEffect(() => {
    getAvailableModels()
      .then((data) => { if (data?.length > 0) setModels(data); })
      .catch(() => {});
  }, []);

  const handleFile = (file: File) => {
    reviewFile(file, {
      jurisdiction: "US",
      contractType: "MSA",
      clientPosition: "buyer",
      modelName,
    });
  };

  // Compute diff from backend original_text + reviewed_text when available
  const diff: DiffLine[] = (() => {
    const orig = result?.original_text as string | undefined;
    const rev = result?.reviewed_text as string | undefined;
    if (orig && rev) return diffLines(orig, rev);
    return MOCK_DIFF;
  })();

  // Map backend clause_reviews to ClauseAnnotation format
  const clauses: ClauseAnnotation[] = (() => {
    const reviews = result?.clause_reviews as
      | { clause_id: string; risk_level: string; issues: string[]; redline_reason?: string; text_snippet?: string }[]
      | undefined;
    if (reviews?.length) {
      return reviews.map((r) => ({
        clauseRef: r.clause_id,
        title: r.clause_id,
        risk: (r.risk_level as ClauseAnnotation["risk"]) ?? "ok",
        notes: r.issues?.join("; ") ?? "",
        reason: r.redline_reason ?? "",
        textSnippet: r.text_snippet ?? "",
      }));
    }
    return MOCK_CLAUSE_ANNOTATIONS;
  })();

  const stats = countDiffStats(diff);

  const isReviewed = status === "complete";
  const isProcessing = status === "uploading" || status === "running";
  const hasFile = status !== "idle";

  return (
    <div className="flex h-full">
      {/* Left panel */}
      <div className="w-[296px] flex-shrink-0 border-r border-[#E5E7EB] bg-white flex flex-col h-full overflow-y-auto">
        {/* Panel header */}
        <div className="px-5 pt-[18px] pb-[14px] border-b border-[#F3F4F6]">
          <div className="text-[15px] font-semibold text-[#111827]">Contract Review</div>
          <div className="text-[11px] text-[#9CA3AF] mt-0.5">AI redlining as legal counsel</div>
        </div>
        <div className="p-5 flex flex-col gap-4">
          {/* Model selector */}
          <div>
            <div className="text-[10px] font-semibold text-[#6B7280] uppercase tracking-wide mb-1.5">Model</div>
            <div className="flex flex-col gap-1">
              {models.map((m) => (
                <button
                  key={m.id}
                  onClick={() => m.available && setModelName(m.id)}
                  disabled={!m.available || status !== "idle"}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-[11px] text-left transition-colors"
                  style={{
                    background: modelName === m.id ? "#EEF2FF" : "#F9FAFB",
                    border: `1px solid ${modelName === m.id ? "#C7D2FE" : "#E5E7EB"}`,
                    color: !m.available ? "#9CA3AF" : modelName === m.id ? "#4338CA" : "#374151",
                    cursor: m.available && status === "idle" ? "pointer" : "not-allowed",
                  }}
                >
                  <span>{m.id === "fine_tuned" ? "★" : m.type === "local" ? "⬡" : "☁"}</span>
                  <span className="flex-1">{m.name}</span>
                  <span
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ background: m.available ? "#22C55E" : "#9CA3AF" }}
                  />
                </button>
              ))}
            </div>
          </div>

          {!hasFile ? (
            <UploadZone onFile={handleFile} />
          ) : (
            <>
              {/* Status card */}
              <div
                className="rounded-lg px-3 py-2.5"
                style={{
                  background: isReviewed ? "#F0FDF4" : "#EFF6FF",
                  border: `1px solid ${isReviewed ? "#BBF7D0" : "#BFDBFE"}`,
                }}
              >
                <div
                  className="text-[11px] font-semibold"
                  style={{ color: isReviewed ? "#15803D" : "#1D4ED8" }}
                >
                  {isReviewed ? "Review complete" : isProcessing ? "Processing…" : "Ready"}
                </div>
                {error && (
                  <div className="text-[10px] text-red-500 mt-0.5">{error}</div>
                )}
              </div>

              {isReviewed && (
                <>
                  <div className="flex gap-2">
                    <div
                      className="flex-1 text-center py-2 rounded-lg text-[12px] font-semibold"
                      style={{ background: "#F0FDF4", border: "1px solid #BBF7D0", color: "#15803D" }}
                    >
                      +{stats.added} additions
                    </div>
                    <div
                      className="flex-1 text-center py-2 rounded-lg text-[12px] font-semibold"
                      style={{ background: "#FEF2F2", border: "1px solid #FECACA", color: "#DC2626" }}
                    >
                      −{stats.removed} deletions
                    </div>
                  </div>

                  <div>
                    <div className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wide mb-2">
                      Counsel Notes
                    </div>
                    <div className="flex flex-col gap-2">
                      {clauses.map((clause) => (
                        <ClauseAnnotationCard key={clause.clauseRef} clause={clause} />
                      ))}
                    </div>
                  </div>

                  <button
                    onClick={() => taskId && downloadRedlinedDocx(taskId)}
                    className="w-full py-2.5 text-[12px] font-semibold text-white rounded-lg"
                    style={{ background: "#2D4FD6" }}
                  >
                    Export Redlined DOCX
                  </button>
                </>
              )}

              {/* Reset button */}
              <button
                onClick={reset}
                className="w-full py-2 text-[11px] text-[#6B7280] rounded-lg border border-[#E5E7EB] hover:bg-[#F9FAFB] transition-colors"
              >
                Upload another contract
              </button>
            </>
          )}
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 overflow-hidden flex flex-col bg-[#F5F6F8]">
        <PageHeader
          title="Contract Review"
          subtitle="AI redlining as legal counsel · JP/US compliance · LangGraph agent"
        />

        <div className="flex-1 overflow-hidden">
          {!isReviewed ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-8">
              <div className="text-5xl mb-4">📄</div>
              <h3
                className="text-[22px] text-[#111827] mb-2"
                style={{ fontFamily: "var(--font-dm-serif)" }}
              >
                {isProcessing ? "Analyzing contract…" : "Contract Review Agent"}
              </h3>
              <p className="text-[14px] text-[#6B7280] max-w-sm leading-relaxed">
                {isProcessing
                  ? "The AI is reviewing your contract for risk clauses and compliance issues."
                  : "Upload a contract on the left to generate an AI-powered redline with clause-by-clause risk analysis and compliance flags."}
              </p>
            </div>
          ) : (
            <DiffViewer diff={diff} filename="contract.pdf" clauses={clauses} />
          )}
        </div>
      </div>
    </div>
  );
}
