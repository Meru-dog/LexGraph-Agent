"use client";

import { useState } from "react";
import type { DDSection, RiskLevel } from "@/lib/types";
import RiskBadge from "./RiskBadge";

interface Props {
  section: DDSection;
  defaultOpen?: boolean;
}

function getHighestRisk(items: DDSection["items"]): RiskLevel | null {
  const priority: RiskLevel[] = ["critical", "high", "medium", "warn", "ok"];
  for (const level of priority) {
    if (items.some((item) => item.status === level)) return level;
  }
  return null;
}

export default function DDReportSection({ section, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const highestRisk = getHighestRisk(section.items);
  const showBadge = highestRisk && highestRisk !== "ok";

  return (
    <div
      className="rounded-[8px] overflow-hidden"
      style={{ border: "1px solid #E5E7EB", background: "#FFFFFF" }}
    >
      {/* Accordion header */}
      <button
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-[#FAFAFA] transition-colors"
        onClick={() => setOpen(!open)}
      >
        <span
          className="flex-shrink-0 text-[9.5px] font-bold px-2 py-1 rounded"
          style={{
            background: "#F0F4FF",
            color: "#4F46E5",
            fontFamily: "var(--font-ibm-plex-mono)",
          }}
        >
          §{section.num}
        </span>
        <span className="flex-1 text-[14px] font-semibold text-[#111827]">{section.title}</span>
        {showBadge && <RiskBadge level={highestRisk!} />}
        <span className="text-[11px] text-[#9CA3AF] mr-1">{section.items.length} items</span>
        <span className="text-[#9CA3AF] text-sm">{open ? "▲" : "▼"}</span>
      </button>

      {/* Accordion body */}
      {open && (
        <div className="border-t border-[#F3F4F6]">
          {section.items.map((item, i) => (
            <div
              key={i}
              className="flex gap-3 px-4 py-3"
              style={{ background: i % 2 === 0 ? "#FFFFFF" : "#FAFAFA" }}
            >
              <RiskBadge level={item.status} className="flex-shrink-0 mt-0.5" />
              <p className="text-[13px] text-[#374151] leading-[1.7]">{item.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
