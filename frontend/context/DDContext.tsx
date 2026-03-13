"use client";

import { createContext, useContext, useState, ReactNode } from "react";
import { useDDAgent, DDAgentState, DDStatus, DDHistoryEntry } from "@/hooks/useDDAgent";

interface DDContextValue extends DDAgentState {
  prompt: string;
  jurisdiction: string;
  modelName: string;
  setPrompt: (v: string) => void;
  setJurisdiction: (v: string) => void;
  setModelName: (v: string) => void;
  runAgent: (payload: {
    prompt: string;
    jurisdiction: string;
    document_ids: string[];
    transaction_type: string;
    model_name?: string;
  }) => Promise<void>;
  approveReport: (notes: string, approved: boolean) => Promise<void>;
  reset: () => void;
}

const DDContext = createContext<DDContextValue | null>(null);

export function DDProvider({ children }: { children: ReactNode }) {
  const dd = useDDAgent();
  const [prompt, setPrompt] = useState(
    "Our company wants to invest ¥2B in TechCorp KK. Please conduct full legal due diligence as our lawyer."
  );
  const [jurisdiction, setJurisdiction] = useState("JP+US");
  const [modelName, setModelName] = useState("gemini");
  return (
    <DDContext.Provider value={{ ...dd, prompt, jurisdiction, modelName, setPrompt, setJurisdiction, setModelName }}>
      {children}
    </DDContext.Provider>
  );
}

export function useDDContext() {
  const ctx = useContext(DDContext);
  if (!ctx) throw new Error("useDDContext must be used inside DDProvider");
  return ctx;
}
