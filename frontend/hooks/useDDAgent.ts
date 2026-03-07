"use client";

import { useState, useCallback, useRef } from "react";
import { startDDAgent, getDDAgentStatus, submitDDReview } from "@/lib/api";

export type DDStatus = "idle" | "running" | "awaiting_review" | "complete" | "error";

export interface DDAgentState {
  taskId: string | null;
  status: DDStatus;
  currentStep: number;
  report: Record<string, unknown> | null;
  error: string | null;
}

const POLL_INTERVAL_MS = 2000;

export function useDDAgent() {
  const [state, setState] = useState<DDAgentState>({
    taskId: null,
    status: "idle",
    currentStep: 0,
    report: null,
    error: null,
  });

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

          setState((prev) => ({
            ...prev,
            currentStep: data.current_step ?? prev.currentStep,
            report: data.report ?? prev.report,
            status: _mapStatus(apiStatus),
          }));

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
      setState({ taskId: null, status: "running", currentStep: 0, report: null, error: null });
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

  const reset = useCallback(() => {
    stopPolling();
    setState({ taskId: null, status: "idle", currentStep: 0, report: null, error: null });
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
