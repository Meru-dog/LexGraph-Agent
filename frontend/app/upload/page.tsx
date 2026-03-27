"use client";

import { useState, useRef } from "react";
import PageHeader from "@/components/layout/PageHeader";
import { uploadDocument, ingestDocument } from "@/lib/api";

const DOC_TYPES = [
  "Statute",
  "Case Law",
  "Contract",
  "Regulation",
  "SEC Filing",
  "Other",
];

type StepState = "pending" | "running" | "done" | "error";

interface ProcessStep {
  label: string;
  state: StepState;
  detail?: string;
}

const STEP_LABELS = [
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
  const [error, setError] = useState<string | null>(null);
  const [uploadResult, setUploadResult] = useState<{ neo4j_stored?: boolean } | null>(null);

  const setStep = (index: number, state: StepState, detail?: string) => {
    setSteps((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], state, detail };
      return updated;
    });
  };

  const markPreviousDone = (upToIndex: number) => {
    setSteps((prev) => {
      const updated = [...prev];
      for (let i = 0; i < upToIndex; i++) {
        if (updated[i].state === "running") {
          updated[i] = { ...updated[i], state: "done" };
        }
      }
      return updated;
    });
  };

  const processFile = async (f: File) => {
    setFile(f);
    setDone(false);
    setError(null);
    setUploadResult(null);
    setSteps(STEP_LABELS.map((label) => ({ label, state: "pending" })));

    try {
      // Steps 0–3: text extraction, chunking, NER, graph — handled by POST /upload
      setStep(0, "running");

      const uploadResult = await uploadDocument(f, docType.toLowerCase().replace(" ", "_"));
      setUploadResult(uploadResult);

      // Mark steps 0–3 done based on backend response
      const processingSteps: { step: string; status: string }[] = uploadResult.processing_steps ?? [];
      const stepMap: Record<string, number> = {
        text_extraction: 0,
        chunking: 1,
        ner_extraction: 2,
        graph_node_creation: 3,
      };

      markPreviousDone(4);
      for (const s of processingSteps) {
        const idx = stepMap[s.step];
        if (idx !== undefined) {
          const state: StepState = s.status === "complete" ? "done" : s.status === "skipped" ? "done" : "done";
          const detail = s.status === "skipped" ? `skipped — ${(s as { note?: string }).note ?? "Neo4j not connected"}` : undefined;
          setStep(idx, state, detail);
        }
      }

      // Step 4: embedding indexing — POST /ingest/{doc_id}
      setStep(4, "running");
      const ingestResult = await ingestDocument(uploadResult.document_id);
      if (ingestResult.embed_warning) {
        setStep(4, "done", `Skipped (${ingestResult.embed_warning.slice(0, 60)})`);
      } else {
        setStep(4, "done", `${ingestResult.vectors_indexed} vectors indexed`);
      }
      setDone(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      // Mark running step as error
      setSteps((prev) =>
        prev.map((s) => (s.state === "running" ? { ...s, state: "error" } : s))
      );
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) processFile(f);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) processFile(f);
  };

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Document Upload"
        subtitle="Ingest statutes, cases, and contracts into the LexGraph Agent knowledge graph"
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
                {steps.map(({ label, state, detail }) => (
                  <div key={label} className="flex items-center gap-3">
                    <div className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
                      {state === "done" ? (
                        <span className="text-[#16A34A] text-sm">✓</span>
                      ) : state === "error" ? (
                        <span className="text-[#DC2626] text-sm">✕</span>
                      ) : state === "running" ? (
                        <div className="w-4 h-4 rounded-full border-2 border-[#2D4FD6] border-t-transparent animate-spin" />
                      ) : (
                        <div className="w-2 h-2 rounded-full bg-[#D1D5DB]" />
                      )}
                    </div>
                    <div className="flex-1">
                      <span
                        className="text-[13px]"
                        style={{
                          color:
                            state === "done"
                              ? "#374151"
                              : state === "error"
                              ? "#DC2626"
                              : state === "running"
                              ? "#2D4FD6"
                              : "#9CA3AF",
                          fontWeight: state === "running" ? 500 : 400,
                        }}
                      >
                        {label}
                      </span>
                      {detail && (
                        <span className="text-[10px] text-[#9CA3AF] ml-2">{detail}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {done && (
                <div
                  className="mt-4 p-3 rounded-lg text-[12px] font-medium"
                  style={{
                    background: uploadResult?.neo4j_stored ? "#F0FDF4" : "#FFFBEB",
                    border: `1px solid ${uploadResult?.neo4j_stored ? "#BBF7D0" : "#FDE68A"}`,
                    color: uploadResult?.neo4j_stored ? "#15803D" : "#92400E",
                  }}
                >
                  {uploadResult?.neo4j_stored
                    ? "Document ingested. Nodes and chunks stored in Neo4j + pgvector."
                    : "Document stored. pgvector chunks indexed. Neo4j not connected — graph nodes skipped."}
                </div>
              )}

              {error && (
                <div
                  className="mt-4 p-3 rounded-lg text-[13px] font-medium text-[#DC2626]"
                  style={{ background: "#FEF2F2", border: "1px solid #FECACA" }}
                >
                  {error}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
