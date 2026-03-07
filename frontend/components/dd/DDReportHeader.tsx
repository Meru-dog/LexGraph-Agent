import type { DDReport } from "@/lib/types";
import RiskBadge from "./RiskBadge";

interface Props {
  report: DDReport;
}

export default function DDReportHeader({ report }: Props) {
  const { summary } = report;

  return (
    <div
      className="rounded-[10px] p-[26px_30px] mb-5"
      style={{
        background: "#FFFFFF",
        border: "1px solid #E5E7EB",
        boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
      }}
    >
      {/* Header row */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <div
            className="text-[10.5px] uppercase tracking-[1.5px] text-[#9CA3AF] mb-1"
            style={{ fontFamily: "var(--font-ibm-plex-mono)" }}
          >
            Due Diligence Report · Internal Memorandum
          </div>
          <h2
            className="text-[27px] text-[#111827] leading-tight"
            style={{ fontFamily: "var(--font-dm-serif)" }}
          >
            {report.target}
          </h2>
          <p className="text-[13px] text-[#6B7280] mt-1">{report.transaction}</p>
        </div>
        <button
          className="px-4 py-2 text-[12px] font-semibold text-white rounded-lg flex-shrink-0"
          style={{ background: "#2D4FD6" }}
        >
          Export PDF
        </button>
      </div>

      {/* Metadata grid */}
      <div className="grid grid-cols-4 gap-2 mb-4">
        {[
          { label: "Prepared By", value: "LexGraph AI" },
          { label: "Report Date", value: report.date },
          { label: "Jurisdiction", value: report.jurisdiction },
          {
            label: "Total Findings",
            value: `${summary.critical + summary.high + summary.medium + summary.low}`,
          },
        ].map(({ label, value }) => (
          <div
            key={label}
            className="rounded-lg px-3.5 py-2.5"
            style={{ background: "#F9FAFB", border: "1px solid #F3F4F6" }}
          >
            <div className="text-[10px] text-[#9CA3AF] font-medium uppercase tracking-wide">{label}</div>
            <div className="text-[12px] text-[#374151] font-semibold mt-0.5">{value}</div>
          </div>
        ))}
      </div>

      {/* Risk badges */}
      <div className="flex gap-2 mb-4 flex-wrap">
        {summary.critical > 0 && (
          <span
            className="text-[11px] font-semibold px-3 py-1 rounded-full"
            style={{ background: "#FEF2F2", border: "1px solid #FECACA", color: "#DC2626" }}
          >
            {summary.critical} Critical
          </span>
        )}
        {summary.high > 0 && (
          <span
            className="text-[11px] font-semibold px-3 py-1 rounded-full"
            style={{ background: "#FFF7ED", border: "1px solid #FED7AA", color: "#EA580C" }}
          >
            {summary.high} High
          </span>
        )}
        {summary.medium > 0 && (
          <span
            className="text-[11px] font-semibold px-3 py-1 rounded-full"
            style={{ background: "#FEFCE8", border: "1px solid #FDE68A", color: "#D97706" }}
          >
            {summary.medium} Medium
          </span>
        )}
        {summary.low > 0 && (
          <span
            className="text-[11px] font-semibold px-3 py-1 rounded-full"
            style={{ background: "#F0FDF4", border: "1px solid #BBF7D0", color: "#16A34A" }}
          >
            {summary.low} Low / OK
          </span>
        )}
      </div>

      {/* Recommendation */}
      <div className="rounded-lg px-4 py-3" style={{ background: "#FFFBEB", border: "1px solid #FDE68A" }}>
        <div className="text-[11px] font-bold text-[#92400E] uppercase tracking-wide mb-1">
          Recommendation
        </div>
        <p className="text-[13px] text-[#78350F] leading-[1.65]">{summary.recommendation}</p>
      </div>
    </div>
  );
}
