const STEPS = [
  { label: "Scope Planning", detail: "Transaction type · Jurisdiction routing" },
  { label: "Corporate Records Review", detail: "Entity registry · Cap table · Articles" },
  { label: "Financial Information", detail: "Audited financials · Tax returns" },
  { label: "Indebtedness Review", detail: "Loan agreements · Security interests" },
  { label: "Employment & Labor", detail: "Officers · Compensation · Labor law" },
  { label: "Agreements & Contracts", detail: "Scanning material contracts..." },
  { label: "Regulatory & Legal", detail: "FSA · SEC · Litigation · Licenses" },
  { label: "Risk Synthesis & Report", detail: "Aggregating findings → Final report" },
];

type StepState = "pending" | "active" | "done";

interface Props {
  currentStep: number; // 0-indexed; -1 = idle
}

export default function StepProgress({ currentStep }: Props) {
  return (
    <div className="mt-4">
      <div className="text-[11px] uppercase tracking-wide text-[#9CA3AF] font-semibold mb-3">
        Workflow
      </div>
      <div className="flex flex-col gap-0">
        {STEPS.map((step, i) => {
          const state: StepState =
            i < currentStep ? "done" : i === currentStep ? "active" : "pending";

          return (
            <div key={i} className="flex gap-3 relative">
              {/* Connector line */}
              {i < STEPS.length - 1 && (
                <div
                  className="absolute left-[11px] top-[22px] w-[2px]"
                  style={{
                    height: "calc(100% - 4px)",
                    background: state === "done" ? "#2D4FD6" : "#F0F2F5",
                  }}
                />
              )}

              {/* Step circle */}
              <div className="flex-shrink-0 z-10">
                {state === "done" ? (
                  <div
                    className="w-[22px] h-[22px] rounded-full flex items-center justify-center text-white text-[10px] font-bold"
                    style={{ background: "#2D4FD6" }}
                  >
                    ✓
                  </div>
                ) : state === "active" ? (
                  <div
                    className="step-active w-[22px] h-[22px] rounded-full flex items-center justify-center text-[11px] font-bold"
                    style={{
                      background: "#EEF2FF",
                      border: "2px solid #2D4FD6",
                      color: "#2D4FD6",
                    }}
                  >
                    ●
                  </div>
                ) : (
                  <div
                    className="w-[22px] h-[22px] rounded-full flex items-center justify-center text-[11px] text-[#9CA3AF]"
                    style={{ background: "#F3F4F6" }}
                  >
                    {i + 1}
                  </div>
                )}
              </div>

              {/* Step text */}
              <div className="pb-4">
                <div
                  className="text-[12px] font-medium"
                  style={{ color: state === "active" ? "#2D4FD6" : state === "done" ? "#111827" : "#9CA3AF" }}
                >
                  {step.label}
                </div>
                <div className="text-[10.5px] text-[#9CA3AF] leading-snug">{step.detail}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
