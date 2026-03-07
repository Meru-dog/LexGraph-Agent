"use client";

import { useState, useRef, useEffect } from "react";
import ChatMessage from "@/components/chat/ChatMessage";
import TypingIndicator from "@/components/chat/TypingIndicator";
import ChatInput from "@/components/chat/ChatInput";
import PageHeader from "@/components/layout/PageHeader";
import { useChat } from "@/hooks/useChat";

const TOPIC_CHIPS = [
  { label: "Corporate Law", prompt: "Explain Corporate Law implications for " },
  { label: "Securities (FIEA)", prompt: "Explain 金商法 (FIEA) implications for " },
  { label: "M&A", prompt: "Explain M&A implications for " },
  { label: "Contract", prompt: "Explain Contract Law implications for " },
];

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [jurisdiction, setJurisdiction] = useState<"JP" | "US" | "JP+US">("JP");
  const { messages, streaming, error, sendMessage } = useChat({ jurisdiction });
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  const handleSubmit = () => {
    if (!input.trim() || streaming) return;
    sendMessage(input.trim());
    setInput("");
  };

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Legal Research Chat"
        subtitle="Graph RAG · JP/US Law · LLaMA 3.1 Fine-tuned"
        right={
          <div className="flex gap-1.5 flex-wrap items-center">
            {/* Jurisdiction toggle */}
            <div className="flex rounded-full overflow-hidden border border-[#E0E4FA] text-[11px] mr-2">
              {(["JP", "US", "JP+US"] as const).map((j) => (
                <button
                  key={j}
                  onClick={() => setJurisdiction(j)}
                  className="px-3 py-1 transition-colors"
                  style={{
                    background: jurisdiction === j ? "#4F46E5" : "#F5F7FF",
                    color: jurisdiction === j ? "#fff" : "#4F46E5",
                  }}
                >
                  {j}
                </button>
              ))}
            </div>
            {TOPIC_CHIPS.map(({ label, prompt }) => (
              <button
                key={label}
                onClick={() => setInput(prompt)}
                className="text-[11px] px-3 py-1 rounded-full transition-colors"
                style={{
                  background: "#F5F7FF",
                  border: "1px solid #E0E4FA",
                  color: "#4F46E5",
                  borderRadius: "20px",
                }}
              >
                {label}
              </button>
            ))}
          </div>
        }
      />

      {/* Message thread */}
      <div className="flex-1 overflow-y-auto py-6 px-6">
        <div className="max-w-[740px] mx-auto flex flex-col gap-5">
          {messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))}
          {streaming && <TypingIndicator />}
          {error && (
            <div className="text-[12px] text-red-500 px-3 py-2 bg-red-50 rounded-lg border border-red-200">
              {error}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="bg-white border-t border-[#E5E7EB]">
        <div className="max-w-[740px] mx-auto pt-4">
          <ChatInput
            value={input}
            onChange={setInput}
            onSubmit={handleSubmit}
            disabled={streaming}
          />
          <p className="text-center text-[11px] text-[#D1D5DB] pb-3">
            LexGraph AI · JP/US Dual-Jurisdiction · Graph RAG + Fine-tuned LLaMA 3.1
          </p>
        </div>
      </div>
    </div>
  );
}
