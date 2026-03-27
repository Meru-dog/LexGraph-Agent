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
import type { ChatMessage, Citation, RouteUsed } from "@/lib/types";

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
  modelName: string;
  setModelName: (m: string) => void;
  sendMessage: (content: string, forceRoute?: string) => void;
  clearMessages: () => void;
}

const ChatContext = createContext<ChatContextValue | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jurisdiction, setJurisdiction] = useState<"JP" | "US" | "JP+US">("JP");
  const [modelName, setModelName] = useState("ollama");

  const sessionId = useRef(generateId());
  // Queue for messages sent while a response is streaming
  const queueRef = useRef<string[]>([]);
  const streamingRef = useRef(false);

  const _stream = useCallback(
    async (content: string, currentMessages: ChatMessage[], forceRoute?: string) => {
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
        let routeUsed: RouteUsed | undefined;
        let adapterMode: "thinking" | "non_thinking" | undefined;

        for await (const chunk of streamChat(
          content,
          jurisdiction,
          sessionId.current,
          history,
          modelName,
          forceRoute
        )) {
          if (chunk.done) {
            if (chunk.citations) citations = chunk.citations as Citation[];
            if (chunk.route_used) routeUsed = chunk.route_used as RouteUsed;
            if (chunk.adapter_mode) adapterMode = chunk.adapter_mode as "thinking" | "non_thinking";
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

        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, citations, route_used: routeUsed, adapter_mode: adapterMode }
              : m
          )
        );
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
    [jurisdiction, modelName]
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
    (content: string, forceRoute?: string) => {
      if (!content.trim()) return;
      if (streamingRef.current) {
        // Queue the message (force_route not preserved in queue — acceptable for manual retries)
        queueRef.current.push(content.trim());
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
        _stream(content.trim(), prev, forceRoute);
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
      value={{ messages, streaming, error, jurisdiction, setJurisdiction, modelName, setModelName, sendMessage, clearMessages }}
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
