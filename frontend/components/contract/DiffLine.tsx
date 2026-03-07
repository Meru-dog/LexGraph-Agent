import type { DiffLine as DiffLineType } from "@/lib/types";

const LINE_STYLES = {
  added: {
    bg: "#F0FDF4",
    border: "#22C55E",
    color: "#15803D",
    prefix: "+",
    prefixColor: "#16A34A",
  },
  removed: {
    bg: "#FEF2F2",
    border: "#EF4444",
    color: "#B91C1C",
    prefix: "−",
    prefixColor: "#DC2626",
  },
  same: {
    bg: "transparent",
    border: "transparent",
    color: "#9CA3AF",
    prefix: " ",
    prefixColor: "#D1D5DB",
  },
};

interface Props {
  line: DiffLineType;
}

export default function DiffLine({ line }: Props) {
  const s = LINE_STYLES[line.type];
  return (
    <div
      className="flex text-[12px] leading-[1.9]"
      style={{
        background: s.bg,
        borderLeft: `3px solid ${s.border}`,
        fontFamily: "var(--font-ibm-plex-mono)",
      }}
    >
      <span
        className="flex-shrink-0 w-6 text-center select-none"
        style={{ color: s.prefixColor }}
      >
        {s.prefix}
      </span>
      <span style={{ color: s.color }} className="px-2 whitespace-pre-wrap break-all">
        {line.text || "\u00A0"}
      </span>
    </div>
  );
}
