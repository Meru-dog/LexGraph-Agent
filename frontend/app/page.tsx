"use client";

import { useState, useRef, useEffect } from "react";
import ChatMessage from "@/components/chat/ChatMessage";
import TypingIndicator from "@/components/chat/TypingIndicator";
import ChatInput from "@/components/chat/ChatInput";
import PageHeader from "@/components/layout/PageHeader";
import { useChatContext } from "@/context/ChatContext";
import { getAvailableModels } from "@/lib/api";

interface ModelOption {
  id: string;
  name: string;
  type: string;
  available: boolean;
}

const TOPIC_CHIPS = [
  { label: "Corporate Law", prompt: "Explain Corporate Law implications for " },
  { label: "Securities (FIEA)", prompt: "Explain 金商法 (FIEA) implications for " },
  { label: "M&A", prompt: "Explain M&A implications for " },
  { label: "Contract", prompt: "Explain Contract Law implications for " },
];

const ROUTE_OPTIONS = [
  { id: null,              label: "Auto",     title: "Auto-detect route (default)" },
  { id: "graph_rag",       label: "Graph",    title: "Force Graph RAG — multi-hop Neo4j traversal" },
  { id: "vector_rag",      label: "Vector",   title: "Force Vector RAG — semantic search only" },
  { id: "direct_answer",   label: "Direct",   title: "Force direct answer — no retrieval" },
  { id: "dd_agent",        label: "DD",       title: "Force DD Agent route — due diligence mode" },
  { id: "contract_agent",  label: "Contract", title: "Force Contract Agent route" },
] as const;

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [forceRoute, setForceRoute] = useState<string | null>(null);
  const { messages, streaming, error, jurisdiction, setJurisdiction, modelName, setModelName, sendMessage } =
    useChatContext();
  const bottomRef = useRef<HTMLDivElement>(null);
  const [models, setModels] = useState<ModelOption[]>([
    { id: "ollama", name: "Qwen3 Swallow 8B", type: "local", available: false },
  ]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    getAvailableModels()
      .then((data) => { if (data?.length > 0) setModels(data); })
      .catch(() => {});
  }, []);

  const handleSubmit = () => {
    if (!input.trim()) return;
    sendMessage(input.trim(), forceRoute ?? undefined);
    setInput("");
  };

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Legal Research Chat"
        subtitle="Graph RAG · JP/US Law"
        right={
          <div className="flex gap-1.5 flex-wrap items-center">
            {/* Model selector */}
            <div className="flex rounded-full overflow-hidden border border-[#E0E4FA] text-[11px] mr-2">
              {models.map((m) => (
                <button
                  key={m.id}
                  onClick={() => m.available && setModelName(m.id)}
                  disabled={!m.available}
                  title={m.available ? m.name : `${m.name} (unavailable)`}
                  className="px-3 py-1 transition-colors relative"
                  style={{
                    background: modelName === m.id ? "#4F46E5" : "#F5F7FF",
                    color: modelName === m.id ? "#fff" : m.available ? "#4F46E5" : "#9CA3AF",
                    cursor: m.available ? "pointer" : "not-allowed",
                  }}
                >
                  {m.id === "fine_tuned" ? "★ LexGraph" : m.id === "llama" ? "⬡ Llama" : "☁ Gemini"}
                </button>
              ))}
            </div>
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

      {/* Input area — never disabled, queues if AI is streaming */}
      <div className="bg-white border-t border-[#E5E7EB]">
        <div className="max-w-[740px] mx-auto pt-4">
          {/* Route override bar */}
          <div className="flex items-center gap-1 mb-2 px-1">
            <span className="text-[10px] text-[#9CA3AF] mr-1 uppercase tracking-wide">Route:</span>
            {ROUTE_OPTIONS.map(({ id, label, title }) => (
              <button
                key={String(id)}
                title={title}
                onClick={() => setForceRoute(id)}
                className="text-[10px] px-2 py-0.5 rounded transition-colors"
                style={{
                  background: forceRoute === id ? "#4F46E5" : "#F5F7FF",
                  color: forceRoute === id ? "#fff" : "#6B7280",
                  border: `1px solid ${forceRoute === id ? "#4F46E5" : "#E5E7EB"}`,
                }}
              >
                {label}
              </button>
            ))}
          </div>
          <ChatInput
            value={input}
            onChange={setInput}
            onSubmit={handleSubmit}
            disabled={false}
          />
          <p className="text-center text-[11px] text-[#D1D5DB] pb-3">
            LexGraph Agent · JP/US Dual-Jurisdiction · Graph RAG
            {streaming && " · Thinking…"}
            {forceRoute && ` · Override: ${forceRoute}`}
          </p>
        </div>
      </div>
    </div>
  );
}
