"use client";

import { useState } from "react";
import PageHeader from "@/components/layout/PageHeader";
import DDPromptPanel from "@/components/dd/DDPromptPanel";
import DDReportHeader from "@/components/dd/DDReportHeader";
import DDReportSection from "@/components/dd/DDReportSection";
import ReviewPanel from "@/components/dd/ReviewPanel";
import { useDDContext } from "@/context/DDContext";
import { downloadDDReport } from "@/lib/api";
import type { DDReport } from "@/lib/types";
import type { DDHistoryEntry } from "@/hooks/useDDAgent";

export default function DDAgentPage() {
  const { status, currentStep, report, error, taskId, history,
          runAgent, approveReport, reset,
          prompt, jurisdiction, modelName, setPrompt, setJurisdiction, setModelName } = useDDContext();

  // Displayed report: either the live report or a selected history entry
  const [historyView, setHistoryView] = useState<DDHistoryEntry | null>(null);

  const handleRun = () => {
    if (!prompt.trim() || status === "running") return;
    setHistoryView(null); // Clear history view when starting a new run
    runAgent({ prompt, jurisdiction, document_ids: [], transaction_type: "investment", model_name: modelName });
  };

  const handleReset = () => {
    setHistoryView(null);
    reset();
  };

  const handleSelectHistory = (entry: DDHistoryEntry) => {
    setHistoryView(entry);
  };

  // Determine which report to display
  const activeReport = (historyView?.report ?? report) as DDReport | null;
  const riskSummary = activeReport?.summary
    ? {
        critical: activeReport.summary.critical,
        high: activeReport.summary.high,
        medium: activeReport.summary.medium,
        low: activeReport.summary.low,
      }
    : undefined;

  const showReport = !!(activeReport && (
    historyView ||
    status === "running" ||
    status === "complete" ||
    status === "awaiting_review"
  ));

  return (
    <div className="flex h-full">
      <DDPromptPanel
        prompt={prompt}
        jurisdiction={jurisdiction}
        modelName={modelName}
        status={status}
        currentStep={currentStep}
        history={history}
        onPromptChange={setPrompt}
        onJurisdictionChange={setJurisdiction}
        onModelChange={setModelName}
        onRun={handleRun}
        onReset={handleReset}
        onSelectHistory={handleSelectHistory}
      />

      {/* Right panel */}
      <div className="flex-1 overflow-y-auto bg-[#F5F6F8]">
        <PageHeader
          title="Due Diligence Agent"
          subtitle="LangGraph · 8-step CFI format · JP/US jurisdiction"
          right={
            (status === "complete" || historyView) && activeReport ? (
              <button
                onClick={() => {
                  const tid = historyView?.taskId ?? taskId;
                  if (tid) downloadDDReport(tid);
                }}
                className="text-[12px] px-4 py-2 rounded-lg font-semibold transition-colors"
                style={{ background: "#2D4FD6", color: "#fff" }}
              >
                Export PDF
              </button>
            ) : null
          }
        />

        <div className="p-6">
          {error && !historyView && (
            <div className="mb-4 p-3 rounded-lg text-[12px] text-red-600 bg-red-50 border border-red-200">
              {error}
            </div>
          )}

          {/* History view banner */}
          {historyView && (
            <div
              className="mb-4 flex items-center justify-between p-3 rounded-lg text-[11px]"
              style={{ background: "#EFF6FF", border: "1px solid #BFDBFE" }}
            >
              <span style={{ color: "#1D4ED8" }}>
                Viewing past run · {new Date(historyView.completedAt).toLocaleString()}
              </span>
              <button
                onClick={() => setHistoryView(null)}
                className="text-[11px] font-medium"
                style={{ color: "#6B7280" }}
              >
                ← Back to current
              </button>
            </div>
          )}

          {/* Human review panel */}
          {status === "awaiting_review" && !historyView && (
            <ReviewPanel
              taskId={taskId ?? ""}
              riskSummary={riskSummary}
              onApprove={(notes, approved) => approveReport(notes, approved)}
            />
          )}

          {status === "idle" && !historyView && (
            <div className="flex flex-col items-center justify-center h-[60vh] text-center">
              <div className="text-5xl mb-4">🔍</div>
              <h3
                className="text-[22px] text-[#111827] mb-2"
                style={{ fontFamily: "var(--font-dm-serif)" }}
              >
                Due Diligence Agent
              </h3>
              <p className="text-[14px] text-[#6B7280] max-w-sm leading-relaxed">
                Enter a DD instruction in the left panel and click{" "}
                <strong>Run DD Agent</strong> to generate a full 8-section CFI due diligence report.
              </p>
            </div>
          )}

          {showReport && activeReport && (
            <>
              <DDReportHeader report={activeReport} />
              <div className="flex flex-col gap-3">
                {activeReport.sections?.map((section) => (
                  <DDReportSection
                    key={section.num}
                    section={section}
                    defaultOpen={section.num === "01" || section.num === "08"}
                  />
                ))}
              </div>

              <div
                className="mt-5 p-4 rounded-lg text-[11px] text-[#9CA3AF] leading-relaxed"
                style={{ background: "#F9FAFB", border: "1px solid #F3F4F6" }}
              >
                <strong className="text-[#6B7280]">⚠ Attorney Review Required.</strong> This
                report was generated by LexGraph Agent acting as analytical counsel. All findings
                require review and sign-off by a licensed attorney before reliance. This document
                does not constitute legal advice and should not be shared externally without
                attorney review.
              </div>
            </>
          )}

          {status === "running" && !activeReport && !historyView && (
            <div className="flex flex-col items-center justify-center h-[50vh]">
              <div className="text-[14px] text-[#6B7280]">Running due diligence analysis…</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
