import type { RiskLevel } from "@/lib/types";

const RISK_STYLES: Record<string, { bg: string; border: string; color: string; label: string }> = {
  critical: { bg: "#FEF2F2", border: "#FECACA", color: "#DC2626", label: "CRITICAL" },
  high:     { bg: "#FFF7ED", border: "#FED7AA", color: "#EA580C", label: "HIGH" },
  medium:   { bg: "#FEFCE8", border: "#FDE68A", color: "#D97706", label: "MEDIUM" },
  low:      { bg: "#F9FAFB", border: "#E5E7EB", color: "#6B7280", label: "LOW" },
  ok:       { bg: "#F0FDF4", border: "#BBF7D0", color: "#16A34A", label: "OK" },
  warn:     { bg: "#FEFCE8", border: "#FDE68A", color: "#D97706", label: "WARN" },
};

const FALLBACK_STYLE = { bg: "#F9FAFB", border: "#E5E7EB", color: "#6B7280", label: "—" };

interface Props {
  level: RiskLevel;
  className?: string;
}

export default function RiskBadge({ level, className = "" }: Props) {
  const s = RISK_STYLES[level] ?? FALLBACK_STYLE;
  return (
    <span
      className={`inline-flex items-center justify-center px-2 py-0.5 rounded text-[9px] font-bold tracking-wide ${className}`}
      style={{
        background: s.bg,
        border: `1px solid ${s.border}`,
        color: s.color,
        fontFamily: "var(--font-ibm-plex-mono)",
        minWidth: "60px",
      }}
    >
      {s.label}
    </span>
  );
}
