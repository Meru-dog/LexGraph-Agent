import type { ClauseAnnotation } from "@/lib/types";
import RiskBadge from "@/components/dd/RiskBadge";

interface Props {
  clause: ClauseAnnotation;
}

export default function ClauseAnnotationCard({ clause }: Props) {
  return (
    <div
      className="rounded-lg p-3 cursor-default transition-shadow"
      style={{
        background: "#FFFFFF",
        border: "1px solid #E5E7EB",
      }}
      onMouseEnter={(e) =>
        ((e.currentTarget as HTMLElement).style.boxShadow = "0 2px 8px rgba(0,0,0,0.07)")
      }
      onMouseLeave={(e) =>
        ((e.currentTarget as HTMLElement).style.boxShadow = "none")
      }
    >
      <div className="flex items-center gap-2 mb-1.5">
        <span
          className="text-[10px] font-semibold"
          style={{ color: "#4F46E5", fontFamily: "var(--font-ibm-plex-mono)" }}
        >
          {clause.clauseRef}
        </span>
        <span className="text-[11px] font-semibold text-[#374151] flex-1">{clause.title}</span>
        <RiskBadge level={clause.risk} />
      </div>
      <p className="text-[11px] text-[#6B7280] leading-[1.55]">{clause.notes}</p>
    </div>
  );
}
