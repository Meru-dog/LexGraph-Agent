"use client";

import { useState, useCallback, useRef } from "react";
import { startDDAgent, getDDAgentStatus, submitDDReview } from "@/lib/api";

export type DDStatus = "idle" | "running" | "awaiting_review" | "complete" | "error";

export interface DDHistoryEntry {
  taskId: string;
  prompt: string;
  jurisdiction: string;
  report: Record<string, unknown>;
  completedAt: string;
}

export interface DDAgentState {
  taskId: string | null;
  status: DDStatus;
  currentStep: number;
  report: Record<string, unknown> | null;
  error: string | null;
  history: DDHistoryEntry[];
}

const POLL_INTERVAL_MS = 2000;

export function useDDAgent() {
  const [state, setState] = useState<DDAgentState>({
    taskId: null,
    status: "idle",
    currentStep: 0,
    report: null,
    error: null,
    history: [],
  });

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Keep a ref to the current prompt/jurisdiction so we can save history on completion
  const pendingMeta = useRef<{ prompt: string; jurisdiction: string }>({ prompt: "", jurisdiction: "" });

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (taskId: string) => {
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const data = await getDDAgentStatus(taskId);
          const apiStatus: string = data.status ?? "running";
          const mapped = _mapStatus(apiStatus);

          setState((prev) => {
            const next: DDAgentState = {
              ...prev,
              currentStep: data.current_step ?? prev.currentStep,
              report: data.report ?? prev.report,
              status: mapped,
            };

            // Save to history when newly completed
            if (mapped === "complete" && prev.status !== "complete" && data.report) {
              next.history = [
                {
                  taskId,
                  prompt: pendingMeta.current.prompt,
                  jurisdiction: pendingMeta.current.jurisdiction,
                  report: data.report,
                  completedAt: new Date().toISOString(),
                },
                ...prev.history,
              ].slice(0, 10); // Keep last 10
            }

            return next;
          });

          if (apiStatus === "completed" || apiStatus === "error" || apiStatus === "awaiting_review") {
            stopPolling();
          }
        } catch (err) {
          setState((prev) => ({
            ...prev,
            status: "error",
            error: err instanceof Error ? err.message : String(err),
          }));
          stopPolling();
        }
      }, POLL_INTERVAL_MS);
    },
    [stopPolling]
  );

  const runAgent = useCallback(
    async (payload: {
      prompt: string;
      jurisdiction: string;
      document_ids: string[];
      transaction_type: string;
    }) => {
      pendingMeta.current = { prompt: payload.prompt, jurisdiction: payload.jurisdiction };
      setState((prev) => ({
        ...prev,
        taskId: null,
        status: "running",
        currentStep: 0,
        report: null,
        error: null,
        // history preserved
      }));
      try {
        const { task_id } = await startDDAgent(payload);
        setState((prev) => ({ ...prev, taskId: task_id }));
        startPolling(task_id);
      } catch (err) {
        setState((prev) => ({
          ...prev,
          status: "error",
          error: err instanceof Error ? err.message : String(err),
        }));
      }
    },
    [startPolling]
  );

  const approveReport = useCallback(
    async (notes: string, approved: boolean) => {
      if (!state.taskId) return;
      await submitDDReview(state.taskId, notes, approved);
      setState((prev) => ({ ...prev, status: "running" }));
      startPolling(state.taskId);
    },
    [state.taskId, startPolling]
  );

  // Reset current run → idle, preserving history
  const reset = useCallback(() => {
    stopPolling();
    setState((prev) => ({
      ...prev,
      taskId: null,
      status: "idle",
      currentStep: 0,
      report: null,
      error: null,
    }));
  }, [stopPolling]);

  return { ...state, runAgent, approveReport, reset };
}

function _mapStatus(api: string): DDStatus {
  switch (api) {
    case "completed": return "complete";
    case "awaiting_review": return "awaiting_review";
    case "error": return "error";
    default: return "running";
  }
}
