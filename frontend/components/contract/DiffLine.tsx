import type { DiffLine as DiffLineType } from "@/lib/types";

interface Props {
  line: DiffLineType;
  lineNo?: number;
}

export default function DiffLine({ line, lineNo }: Props) {
  const isAdded = line.type === "added";
  const isRemoved = line.type === "removed";
  const isSame = line.type === "same";

  return (
    <div
      className="flex text-[12px] leading-[1.75] group"
      style={{
        background: isAdded ? "#e6ffed" : isRemoved ? "#ffebe9" : "transparent",
        fontFamily: "var(--font-ibm-plex-mono)",
      }}
    >
      {/* Line number gutter */}
      <span
        className="select-none flex-shrink-0 w-10 text-right pr-3 border-r text-[11px] leading-[1.75]"
        style={{
          color: isAdded ? "#57ab5a" : isRemoved ? "#e5534b" : "#8b949e",
          borderColor: isAdded ? "#4ae168" : isRemoved ? "#ff7b72" : "#21262d",
          background: isAdded ? "#ccffd8" : isRemoved ? "#ffd7d5" : "#161b22",
        }}
      >
        {lineNo ?? ""}
      </span>

      {/* +/- prefix */}
      <span
        className="flex-shrink-0 w-5 text-center select-none font-bold"
        style={{
          color: isAdded ? "#3fb950" : isRemoved ? "#f85149" : "transparent",
        }}
      >
        {isAdded ? "+" : isRemoved ? "−" : " "}
      </span>

      {/* Line content */}
      <span
        className="flex-1 px-2 whitespace-pre-wrap break-all"
        style={{ color: isAdded ? "#1f6feb" : isRemoved ? "#da3633" : "#e6edf3" }}
      >
        {line.text || "\u00A0"}
      </span>
    </div>
  );
}
