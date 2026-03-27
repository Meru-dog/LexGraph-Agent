"use client";

import { useState, useCallback, useRef } from "react";
import { startContractReview, getContractReviewStatus, uploadDocument } from "@/lib/api";

export type ReviewStatus = "idle" | "uploading" | "running" | "complete" | "error";

export interface ContractReviewState {
  taskId: string | null;
  documentId: string | null;
  status: ReviewStatus;
  result: Record<string, unknown> | null;
  error: string | null;
}


const POLL_INTERVAL_MS = 2000;

export function useContractReview() {
  const [state, setState] = useState<ContractReviewState>({
    taskId: null,
    documentId: null,
    status: "idle",
    result: null,
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
          const data = await getContractReviewStatus(taskId);
          const apiStatus: string = data.status ?? "running";

          // Backend returns the full task dict directly (no nested .result key)
          setState((prev) => ({
            ...prev,
            result: data,
            status: apiStatus === "complete" ? "complete" : apiStatus === "error" ? "error" : "running",
          }));

          if (apiStatus === "complete" || apiStatus === "error") {
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

  const reviewFile = useCallback(
    async (
      file: File,
      options: { jurisdiction: string; contractType: string; clientPosition: string; modelName?: string }
    ) => {
      setState({ taskId: null, documentId: null, status: "uploading", result: null, error: null });

      try {
        // Step 1: Upload file
        const uploadData = await uploadDocument(file, options.contractType);
        const documentId: string = uploadData.document_id;

        setState((prev) => ({ ...prev, documentId, status: "running" }));

        // Step 2: Kick off contract review agent
        const reviewData = await startContractReview({
          document_id: documentId,
          jurisdiction: options.jurisdiction,
          contract_type: options.contractType,
          client_position: options.clientPosition,
          model_name: options.modelName ?? "ollama",
        });
        const taskId: string = reviewData.task_id;

        setState((prev) => ({ ...prev, taskId }));
        startPolling(taskId);
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

  const reset = useCallback(() => {
    stopPolling();
    setState({ taskId: null, documentId: null, status: "idle", result: null, error: null });
  }, [stopPolling]);

  return { ...state, reviewFile, reset };
}
