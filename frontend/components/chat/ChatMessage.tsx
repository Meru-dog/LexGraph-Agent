import type { ChatMessage as ChatMessageType } from "@/lib/types";

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
