"use client";

import { createContext, useContext, ReactNode } from "react";
import { useContractReview, ContractReviewState, ReviewStatus } from "@/hooks/useContractReview";

interface ContractReviewContextValue extends ContractReviewState {
  reviewFile: (
    file: File,
    options: { jurisdiction: string; contractType: string; clientPosition: string }
  ) => Promise<void>;
  reset: () => void;
}

const ContractReviewContext = createContext<ContractReviewContextValue | null>(null);

export function ContractReviewProvider({ children }: { children: ReactNode }) {
  const review = useContractReview();
  return (
    <ContractReviewContext.Provider value={review}>
      {children}
    </ContractReviewContext.Provider>
  );
}

export function useContractReviewContext() {
  const ctx = useContext(ContractReviewContext);
  if (!ctx) throw new Error("useContractReviewContext must be used inside ContractReviewProvider");
  return ctx;
}
