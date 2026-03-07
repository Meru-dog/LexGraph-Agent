"use client";

import { useState, useCallback, useRef } from "react";
import { streamChat } from "@/lib/api";
import type { ChatMessage, Citation } from "@/lib/types";

function generateId(): string {
  return Math.random().toString(36).slice(2);
}

interface UseChatOptions {
  jurisdiction?: string;
}

export function useChat({ jurisdiction = "JP" }: UseChatOptions = {}) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "init",
      role: "assistant",
      content:
        "Welcome to LexGraph AI. I can assist with Japanese and US legal research, M&A due diligence questions, and contract analysis. All responses are grounded in the knowledge graph.\n\nHow can I help you today?",
      timestamp: new Date(),
    },
  ]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionId = useRef(generateId());
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || streaming) return;
      setError(null);

      const userMsg: ChatMessage = {
        id: generateId(),
        role: "user",
        content: content.trim(),
        timestamp: new Date(),
      };

      const assistantId = generateId();
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setStreaming(true);

      const history = messages
        .filter((m) => m.id !== "init")
        .map((m) => ({ role: m.role, content: m.content }));

      abortRef.current = new AbortController();

      try {
        let accumulated = "";
        let citations: Citation[] | undefined;

        for await (const chunk of streamChat(
          content.trim(),
          jurisdiction,
          sessionId.current,
          history
        )) {
          if (chunk.done) {
            if (chunk.citations) {
              citations = chunk.citations as Citation[];
            }
            break;
          }
          if (chunk.token) {
            accumulated += chunk.token;
            const snap = accumulated;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: snap } : m
              )
            );
          }
        }

        // Attach citations after stream completes
        if (citations) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, citations } : m
            )
          );
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `[Error: ${msg}]` }
              : m
          )
        );
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [messages, streaming, jurisdiction]
  );

  const clearMessages = useCallback(() => {
    sessionId.current = generateId();
    setMessages([
      {
        id: "init",
        role: "assistant",
        content:
          "Welcome to LexGraph AI. I can assist with Japanese and US legal research, M&A due diligence questions, and contract analysis. All responses are grounded in the knowledge graph.\n\nHow can I help you today?",
        timestamp: new Date(),
      },
    ]);
    setError(null);
  }, []);

  return { messages, streaming, error, sendMessage, clearMessages };
}
