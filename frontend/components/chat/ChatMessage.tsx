import type { ChatMessage as ChatMessageType, RouteUsed } from "@/lib/types";

interface Props {
  message: ChatMessageType;
}

export default function ChatMessage({ message }: Props) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex items-start gap-3 justify-end">
        <div
          className="max-w-[520px] rounded-[10px] px-4 py-3 text-[14px] leading-[1.75] text-white"
          style={{ background: "#2D4FD6" }}
        >
          {message.content}
        </div>
        <div
          className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-[12px] font-bold text-white"
          style={{ background: "#2D4FD6" }}
        >
          U
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      <div
        className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm"
        style={{ background: "#F0F4FF", border: "1px solid #C7D2FA" }}
      >
        ⚖
      </div>
      <div
        className="max-w-[560px] rounded-[10px] px-4 py-3 text-[14px] leading-[1.75] text-[#374151] whitespace-pre-wrap"
        style={{
          background: "#FFFFFF",
          border: "1px solid #E5E7EB",
          boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        }}
      >
        {/* Render markdown-style bold */}
        <MessageContent content={message.content} />

        {/* Route indicator + adapter mode */}
        {message.route_used && (
          <div className="mt-2 flex items-center gap-1.5">
            <RouteBadge route={message.route_used} />
            {message.adapter_mode === "thinking" && (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded"
                style={{ background: "#FEF3C7", color: "#92400E", border: "1px solid #FDE68A" }}
              >
                thinking
              </span>
            )}
          </div>
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-[#F3F4F6]">
            <div className="text-[10.5px] uppercase tracking-wide text-[#9CA3AF] mb-1.5 font-semibold">
              Citations
            </div>
            <div className="flex flex-wrap gap-1.5">
              {message.citations.map((c) => (
                <span
                  key={c.node_id}
                  className="text-[11px] px-2 py-0.5 rounded"
                  style={{
                    background: "#EEF2FF",
                    border: "1px solid #C7D2FA",
                    color: "#4F46E5",
                    fontFamily: "var(--font-ibm-plex-mono)",
                  }}
                >
                  {c.title} {c.article}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const ROUTE_META: Record<RouteUsed, { label: string; bg: string; color: string; border: string }> = {
  dd_agent:       { label: "DD Agent",       bg: "#FFF7ED", color: "#9A3412", border: "#FED7AA" },
  contract_agent: { label: "Contract Agent", bg: "#F0FDF4", color: "#15803D", border: "#BBF7D0" },
  graph_rag:      { label: "Graph RAG",      bg: "#EEF2FF", color: "#4338CA", border: "#C7D2FA" },
  vector_rag:     { label: "Vector RAG",     bg: "#F5F3FF", color: "#6D28D9", border: "#DDD6FE" },
  direct_answer:  { label: "Direct",         bg: "#F9FAFB", color: "#6B7280", border: "#E5E7EB" },
};

function RouteBadge({ route }: { route: RouteUsed }) {
  const meta = ROUTE_META[route];
  return (
    <span
      className="text-[10px] px-1.5 py-0.5 rounded font-medium"
      style={{ background: meta.bg, color: meta.color, border: `1px solid ${meta.border}` }}
    >
      {meta.label}
    </span>
  );
}

function MessageContent({ content }: { content: string }) {
  // Simple markdown bold rendering: **text** → <strong>text</strong>
  const parts = content.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return <strong key={i} className="font-semibold text-[#111827]">{part.slice(2, -2)}</strong>;
        }
        return <span key={i}>{part}</span>;
      })}
    </>
  );
}
