"use client";

import { useState } from "react";
import RiskBadge from "./RiskBadge";

interface Props {
  taskId: string;
  riskSummary?: { critical: number; high: number; medium: number; low: number };
  onApprove: (notes: string, approved: boolean) => void;
}

export default function ReviewPanel({ taskId, riskSummary, onApprove }: Props) {
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (approved: boolean) => {
    setSubmitting(true);
    await onApprove(notes, approved);
    setSubmitting(false);
  };

  const risk = riskSummary ?? { critical: 0, high: 0, medium: 0, low: 0 };

  return (
    <div
      className="rounded-xl p-5 mb-5"
      style={{ background: "#FFFBEB", border: "1px solid #FCD34D" }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div
          className="w-2 h-2 rounded-full animate-pulse"
          style={{ background: "#D97706" }}
        />
        <span
          className="text-[13px] font-semibold"
          style={{ color: "#92400E", fontFamily: "var(--font-dm-serif)" }}
        >
          Attorney Review Required
        </span>
      </div>

      <p className="text-[12px] text-[#78350F] mb-4 leading-relaxed">
        The due diligence analysis is complete. Please review the risk findings below
        and approve or return for re-investigation.
      </p>

      {/* Risk summary */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {risk.critical > 0 && (
          <div className="flex items-center gap-1.5">
            <RiskBadge level="critical" />
            <span className="text-[11px] text-[#374151]">{risk.critical}</span>
          </div>
        )}
        {risk.high > 0 && (
          <div className="flex items-center gap-1.5">
            <RiskBadge level="high" />
            <span className="text-[11px] text-[#374151]">{risk.high}</span>
          </div>
        )}
        {risk.medium > 0 && (
          <div className="flex items-center gap-1.5">
            <RiskBadge level="medium" />
            <span className="text-[11px] text-[#374151]">{risk.medium}</span>
          </div>
        )}
        {risk.low > 0 && (
          <div className="flex items-center gap-1.5">
            <RiskBadge level="ok" />
            <span className="text-[11px] text-[#374151]">{risk.low} low</span>
          </div>
        )}
      </div>

      {/* Attorney notes */}
      <div className="mb-4">
        <label className="text-[11px] font-semibold text-[#78350F] uppercase tracking-wide mb-1.5 block">
          Attorney Notes (optional)
        </label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={submitting}
          rows={3}
          placeholder="Add review notes, flag items for re-investigation, or specify conditions..."
          className="w-full text-[12px] p-3 rounded-lg resize-y outline-none leading-[1.55]"
          style={{
            background: "#FFFEF7",
            border: "1px solid #FCD34D",
            fontFamily: "var(--font-ibm-plex-sans)",
            color: "#374151",
          }}
        />
      </div>

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          onClick={() => handleSubmit(true)}
          disabled={submitting}
          className="flex-1 py-2.5 text-[12px] font-semibold text-white rounded-lg transition-colors"
          style={{ background: submitting ? "#9CA3AF" : "#16A34A" }}
        >
          {submitting ? "Submitting…" : "Approve & Generate Report"}
        </button>
        <button
          onClick={() => handleSubmit(false)}
          disabled={submitting}
          className="flex-1 py-2.5 text-[12px] font-semibold rounded-lg transition-colors"
          style={{
            background: submitting ? "#F3F4F6" : "#FEF2F2",
            border: "1px solid #FECACA",
            color: submitting ? "#9CA3AF" : "#DC2626",
          }}
        >
          Return for Re-investigation
        </button>
      </div>
    </div>
  );
}
