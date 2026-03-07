"use client";

import { useState, useRef } from "react";
import PageHeader from "@/components/layout/PageHeader";

const DOC_TYPES = [
  "Statute",
  "Case Law",
  "Contract",
  "Regulation",
  "SEC Filing",
  "Other",
];

type ProcessStep = {
  label: string;
  state: "pending" | "running" | "done";
};

const PROCESS_STEPS: string[] = [
  "Extracting text",
  "Chunking (512 tokens, 64 overlap)",
  "NER extraction",
  "Graph node creation",
  "Embedding indexing",
];

export default function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [docType, setDocType] = useState("Contract");
  const [file, setFile] = useState<File | null>(null);
  const [steps, setSteps] = useState<ProcessStep[]>([]);
  const [done, setDone] = useState(false);

  const startProcessing = (f: File) => {
    setFile(f);
    setDone(false);
    const initial: ProcessStep[] = PROCESS_STEPS.map((label) => ({
      label,
      state: "pending",
    }));
    setSteps(initial);

    // Advance steps sequentially
    PROCESS_STEPS.forEach((_, i) => {
      setTimeout(() => {
        setSteps((prev) => {
          const updated = [...prev];
          if (i > 0) updated[i - 1] = { ...updated[i - 1], state: "done" };
          updated[i] = { ...updated[i], state: "running" };
          return updated;
        });
      }, i * 900);

      if (i === PROCESS_STEPS.length - 1) {
        setTimeout(() => {
          setSteps((prev) => {
            const updated = [...prev];
            updated[i] = { ...updated[i], state: "done" };
            return updated;
          });
          setDone(true);
        }, (i + 1) * 900);
      }
    });
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) startProcessing(f);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) startProcessing(f);
  };

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Document Upload"
        subtitle="Ingest statutes, cases, contracts into the knowledge graph"
      />

      <div className="flex-1 overflow-y-auto bg-[#F5F6F8] p-6">
        <div className="max-w-xl mx-auto flex flex-col gap-5">
          {/* Drop zone */}
          <div
            className="rounded-[12px] px-8 py-12 flex flex-col items-center justify-center cursor-pointer transition-all text-center bg-white"
            style={{
              border: `2px dashed ${dragOver ? "#2D4FD6" : "#D1D5DB"}`,
              background: dragOver ? "#F5F7FF" : "#FFFFFF",
            }}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
          >
            <div className="text-4xl mb-3">⬆</div>
            <p className="text-[15px] font-semibold text-[#374151]">
              Drop documents here or click to browse
            </p>
            <p className="text-[12px] text-[#9CA3AF] mt-1.5">
              PDF · DOCX · TXT · HTML · Max 50MB per file
            </p>
            <input
              ref={inputRef}
              type="file"
              accept=".pdf,.docx,.txt,.html"
              className="hidden"
              onChange={handleChange}
            />
          </div>

          {/* Document type selector */}
          <div>
            <div className="text-[12px] font-semibold text-[#6B7280] uppercase tracking-wide mb-2">
              Document Type
            </div>
            <div className="grid grid-cols-3 gap-2">
              {DOC_TYPES.map((type) => (
                <button
                  key={type}
                  onClick={() => setDocType(type)}
                  className="py-2 text-[12px] rounded-lg transition-colors"
                  style={{
                    background: docType === type ? "#EEF2FF" : "#FFFFFF",
                    border: `1px solid ${docType === type ? "#C7D2FA" : "#E5E7EB"}`,
                    color: docType === type ? "#4F46E5" : "#6B7280",
                  }}
                >
                  {type}
                </button>
              ))}
            </div>
          </div>

          {/* Processing steps */}
          {steps.length > 0 && (
            <div
              className="rounded-xl p-5"
              style={{ background: "#FFFFFF", border: "1px solid #E5E7EB" }}
            >
              <div className="text-[13px] font-semibold text-[#374151] mb-1">
                {file?.name}
              </div>
              <div className="text-[11px] text-[#9CA3AF] mb-4">
                Type: {docType}
              </div>

              <div className="flex flex-col gap-3">
                {steps.map(({ label, state }) => (
                  <div key={label} className="flex items-center gap-3">
                    <div className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
                      {state === "done" ? (
                        <span className="text-[#16A34A] text-sm">✓</span>
                      ) : state === "running" ? (
                        <div
                          className="w-4 h-4 rounded-full border-2 border-[#2D4FD6] border-t-transparent animate-spin"
                        />
                      ) : (
                        <div className="w-2 h-2 rounded-full bg-[#D1D5DB]" />
                      )}
                    </div>
                    <span
                      className="text-[13px]"
                      style={{
                        color: state === "done" ? "#374151" : state === "running" ? "#2D4FD6" : "#9CA3AF",
                        fontWeight: state === "running" ? 500 : 400,
                      }}
                    >
                      {label}
                    </span>
                  </div>
                ))}
              </div>

              {done && (
                <div
                  className="mt-4 p-3 rounded-lg text-[13px] font-medium text-[#15803D]"
                  style={{ background: "#F0FDF4", border: "1px solid #BBF7D0" }}
                >
                  Document ingested successfully. Nodes and edges created in Neo4j.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
