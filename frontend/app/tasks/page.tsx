"use client";

import { useEffect, useState } from "react";
import PageHeader from "@/components/layout/PageHeader";
import { listDDTasks, listReviewTasks, downloadDDReport, downloadRedlinedDocx } from "@/lib/api";

type TaskType = "dd" | "review";

interface TaskRow {
  task_id: string;
  type: TaskType;
  status: string;
  created_at: string;
  label: string;
  raw: Record<string, unknown>;
}

const STATUS_COLOR: Record<string, { bg: string; text: string; label: string }> = {
  running:         { bg: "#EFF6FF", text: "#2D4FD6", label: "Running" },
  awaiting_review: { bg: "#FFFBEB", text: "#D97706", label: "Awaiting Review" },
  complete:        { bg: "#F0FDF4", text: "#16A34A", label: "Complete" },
  error:           { bg: "#FEF2F2", text: "#DC2626", label: "Error" },
};

const RISK_COLOR: Record<string, string> = {
  critical: "#DC2626", high: "#D97706", medium: "#2D4FD6", low: "#16A34A", ok: "#16A34A",
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const [ddRaw, reviewRaw] = await Promise.all([listDDTasks(), listReviewTasks()]);

      const ddRows: TaskRow[] = (ddRaw as Record<string, unknown>[]).map((t) => ({
        task_id: t.task_id as string,
        type: "dd",
        status: t.status as string,
        created_at: t.created_at as string,
        label: ((t.request as Record<string, unknown>)?.prompt as string ?? "DD Task").slice(0, 80),
        raw: t,
      }));

      const reviewRows: TaskRow[] = (reviewRaw as Record<string, unknown>[]).map((t) => ({
        task_id: t.task_id as string,
        type: "review",
        status: t.status as string,
        created_at: t.created_at as string,
        label: `Contract Review`,
        raw: t,
      }));

      setTasks([...ddRows, ...reviewRows].sort((a, b) =>
        b.created_at.localeCompare(a.created_at)
      ));
    } catch {
      // backend may not be running
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5_000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Task Dashboard"
        subtitle="Due diligence and contract review tasks · auto-refreshes every 5s"
        right={
          <button
            onClick={refresh}
            className="text-[11px] px-3 py-1.5 rounded-lg"
            style={{ background: "#F3F4F6", color: "#4B5563", border: "1px solid #E5E7EB" }}
          >
            Refresh
          </button>
        }
      />

      <div className="flex-1 overflow-y-auto bg-[#F5F6F8] p-6">
        {loading ? (
          <div className="text-[13px] text-[#9CA3AF] mt-10 text-center">Loading…</div>
        ) : tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-[50vh] text-center">
            <div className="text-4xl mb-3">📋</div>
            <p className="text-[14px] text-[#111827] font-semibold mb-1">No tasks yet</p>
            <p className="text-[13px] text-[#6B7280]">Start a DD analysis or upload a contract for review.</p>
          </div>
        ) : (
          <div className="max-w-[780px] mx-auto flex flex-col gap-3">
            {tasks.map((task) => {
              const sc = STATUS_COLOR[task.status] ?? { bg: "#F9FAFB", text: "#6B7280", label: task.status };
              const isExpanded = expandedId === task.task_id;
              const report = task.raw.report as Record<string, unknown> | null | undefined;
              const clauses = task.raw.clause_reviews as unknown[] | undefined;

              return (
                <div
                  key={task.task_id}
                  className="rounded-xl overflow-hidden"
                  style={{ background: "#FFFFFF", border: "1px solid #E5E7EB" }}
                >
                  {/* Task header row */}
                  <div
                    className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-[#FAFAFA] transition-colors"
                    onClick={() => setExpandedId(isExpanded ? null : task.task_id)}
                  >
                    {/* Type badge */}
                    <span
                      className="text-[10px] px-2.5 py-1 rounded-full font-semibold uppercase flex-shrink-0"
                      style={{
                        background: task.type === "dd" ? "#EEF2FF" : "#F0FDF4",
                        color: task.type === "dd" ? "#4F46E5" : "#16A34A",
                      }}
                    >
                      {task.type === "dd" ? "Due Diligence" : "Contract Review"}
                    </span>

                    {/* Label */}
                    <div className="flex-1 min-w-0">
                      <div className="text-[13px] text-[#111827] truncate font-medium">{task.label}</div>
                      <div className="text-[10px] text-[#9CA3AF] font-mono mt-0.5">{task.task_id.slice(0, 12)}…</div>
                    </div>

                    {/* Status */}
                    <span
                      className="text-[11px] px-3 py-1 rounded-full font-semibold flex-shrink-0"
                      style={{ background: sc.bg, color: sc.text }}
                    >
                      {task.status === "running" && (
                        <span className="inline-block w-1.5 h-1.5 rounded-full mr-1.5 align-middle animate-pulse" style={{ background: sc.text }} />
                      )}
                      {sc.label}
                    </span>

                    {/* Date */}
                    <span className="text-[11px] text-[#9CA3AF] flex-shrink-0 hidden sm:block">
                      {task.created_at.slice(0, 16).replace("T", " ")}
                    </span>

                    {/* Chevron */}
                    <span className="text-[#9CA3AF] text-[12px] flex-shrink-0">
                      {isExpanded ? "▲" : "▼"}
                    </span>
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div className="border-t border-[#F3F4F6] px-5 py-4 flex flex-col gap-4">

                      {/* Progress / step info */}
                      {task.type === "dd" && (
                        <div>
                          <div className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wide mb-2">
                            Agent Progress
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-2 rounded-full bg-[#F3F4F6] overflow-hidden">
                              <div
                                className="h-full rounded-full transition-all"
                                style={{
                                  width: `${Math.round(((task.raw.current_step as number ?? 0) / 8) * 100)}%`,
                                  background: task.status === "complete" ? "#16A34A" : "#2D4FD6",
                                }}
                              />
                            </div>
                            <span className="text-[11px] text-[#6B7280] flex-shrink-0">
                              Step {task.raw.current_step as number ?? 0} / 8
                            </span>
                          </div>
                          {task.raw.step_label && (
                            <div className="text-[11px] text-[#9CA3AF] mt-1">
                              Last node: <span className="text-[#374151]">{task.raw.step_label as string}</span>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Error */}
                      {task.raw.error && (
                        <div className="text-[12px] text-[#DC2626] bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                          Error: {task.raw.error as string}
                        </div>
                      )}

                      {/* DD risk summary */}
                      {task.type === "dd" && report?.summary && (
                        <div>
                          <div className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wide mb-2">
                            Risk Summary
                          </div>
                          <div className="flex gap-3">
                            {(["critical", "high", "medium", "low"] as const).map((level) => {
                              const count = (report.summary as Record<string, unknown>)[level] as number ?? 0;
                              return (
                                <div key={level} className="text-center">
                                  <div
                                    className="text-[18px] font-bold"
                                    style={{ color: RISK_COLOR[level] }}
                                  >
                                    {count}
                                  </div>
                                  <div className="text-[10px] text-[#9CA3AF] capitalize">{level}</div>
                                </div>
                              );
                            })}
                          </div>
                          {(report.summary as Record<string, unknown>).recommendation && (
                            <div className="mt-2 text-[12px] text-[#374151] leading-relaxed bg-[#F9FAFB] rounded-lg px-3 py-2 border border-[#F3F4F6]">
                              {(report.summary as Record<string, unknown>).recommendation as string}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Contract review clause count */}
                      {task.type === "review" && clauses && clauses.length > 0 && (
                        <div>
                          <div className="text-[11px] font-semibold text-[#6B7280] uppercase tracking-wide mb-2">
                            Clauses Reviewed
                          </div>
                          <div className="flex flex-col gap-1.5">
                            {(clauses as { clause_id: string; risk_level: string; issues: string[] }[]).map((c) => (
                              <div key={c.clause_id} className="flex items-start gap-2">
                                <span
                                  className="text-[10px] px-1.5 py-0.5 rounded font-semibold flex-shrink-0 mt-0.5"
                                  style={{
                                    background: `${RISK_COLOR[c.risk_level] ?? "#9CA3AF"}18`,
                                    color: RISK_COLOR[c.risk_level] ?? "#9CA3AF",
                                  }}
                                >
                                  {c.risk_level}
                                </span>
                                <div>
                                  <div className="text-[12px] font-medium text-[#374151]">{c.clause_id}</div>
                                  {c.issues?.slice(0, 1).map((issue, i) => (
                                    <div key={i} className="text-[11px] text-[#6B7280]">{issue}</div>
                                  ))}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Actions */}
                      <div className="flex gap-2 flex-wrap" onClick={(e) => e.stopPropagation()}>
                        {task.status === "complete" && task.type === "dd" && (
                          <button
                            onClick={() => downloadDDReport(task.task_id)}
                            className="text-[12px] px-4 py-2 rounded-lg font-semibold"
                            style={{ background: "#2D4FD6", color: "#fff" }}
                          >
                            Export PDF Report
                          </button>
                        )}
                        {task.status === "complete" && task.type === "review" && (
                          <button
                            onClick={() => downloadRedlinedDocx(task.task_id)}
                            className="text-[12px] px-4 py-2 rounded-lg font-semibold"
                            style={{ background: "#16A34A", color: "#fff" }}
                          >
                            Export Redlined DOCX
                          </button>
                        )}
                        {task.status === "awaiting_review" && (
                          <a
                            href={task.type === "dd" ? "/dd" : "/contract"}
                            className="text-[12px] px-4 py-2 rounded-lg font-semibold"
                            style={{ background: "#FFFBEB", color: "#D97706", border: "1px solid #FDE68A" }}
                          >
                            Open for Attorney Review →
                          </a>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
