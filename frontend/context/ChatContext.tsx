"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  useEffect,
  ReactNode,
} from "react";
import { streamChat } from "@/lib/api";
import type { ChatMessage, Citation } from "@/lib/types";

function generateId() {
  return Math.random().toString(36).slice(2);
}

const WELCOME: ChatMessage = {
  id: "init",
  role: "assistant",
  content:
    "Welcome to LexGraph Agent. I can assist with Japanese and US legal research, M&A due diligence questions, and contract analysis. All responses are grounded in the knowledge graph.\n\nHow can I help you today?",
  timestamp: new Date(),
};

interface ChatContextValue {
  messages: ChatMessage[];
  streaming: boolean;
  error: string | null;
  jurisdiction: "JP" | "US" | "JP+US";
  setJurisdiction: (j: "JP" | "US" | "JP+US") => void;
  sendMessage: (content: string) => void;
  clearMessages: () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jurisdiction, setJurisdiction] = useState<"JP" | "US" | "JP+US">("JP");

  const sessionId = useRef(generateId());
  // Queue for messages sent while a response is streaming
  const queueRef = useRef<string[]>([]);
  const streamingRef = useRef(false);

  const _stream = useCallback(
    async (content: string, currentMessages: ChatMessage[]) => {
      const assistantId = generateId();
      const userMsg: ChatMessage = {
        id: generateId(),
        role: "user",
        content,
        timestamp: new Date(),
      };
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      streamingRef.current = true;
      setStreaming(true);
      setError(null);

      const history = currentMessages
        .filter((m) => m.id !== "init")
        .map((m) => ({ role: m.role, content: m.content }));

      try {
        let accumulated = "";
        let citations: Citation[] | undefined;

        for await (const chunk of streamChat(
          content,
          jurisdiction,
          sessionId.current,
          history
        )) {
          if (chunk.done) {
            if (chunk.citations) citations = chunk.citations as Citation[];
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
            m.id === assistantId ? { ...m, content: `[Error: ${msg}]` } : m
          )
        );
      } finally {
        streamingRef.current = false;
        setStreaming(false);
      }
    },
    [jurisdiction]
  );

  // Process queue after each stream completes
  useEffect(() => {
    if (!streaming && queueRef.current.length > 0) {
      const next = queueRef.current.shift()!;
      setMessages((prev) => {
        _stream(next, prev);
        return prev;
      });
    }
  }, [streaming, _stream]);

  const sendMessage = useCallback(
    (content: string) => {
      if (!content.trim()) return;
      if (streamingRef.current) {
        // Queue the message to send after current stream finishes
        queueRef.current.push(content.trim());
        // Show it as a pending user message immediately
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: "user",
            content: content.trim(),
            timestamp: new Date(),
          },
        ]);
        return;
      }
      setMessages((prev) => {
        _stream(content.trim(), prev);
        return prev;
      });
    },
    [_stream]
  );

  const clearMessages = useCallback(() => {
    sessionId.current = generateId();
    queueRef.current = [];
    setMessages([WELCOME]);
    setError(null);
  }, []);

  return (
    <ChatContext.Provider
      value={{ messages, streaming, error, jurisdiction, setJurisdiction, sendMessage, clearMessages }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChatContext() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error("useChatContext must be used inside ChatProvider");
  return ctx;
}
