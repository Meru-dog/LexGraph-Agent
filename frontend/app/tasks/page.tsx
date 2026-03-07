"use client";

import { useEffect, useState } from "react";
import PageHeader from "@/components/layout/PageHeader";
import RiskBadge from "@/components/dd/RiskBadge";
import { listDDTasks, listReviewTasks, downloadDDReport, downloadRedlinedDocx } from "@/lib/api";
import type { RiskLevel } from "@/lib/types";

type TaskType = "dd" | "review";

interface TaskRow {
  task_id: string;
  type: TaskType;
  status: string;
  created_at: string;
  label: string;
  risk?: RiskLevel;
}

const STATUS_COLORS: Record<string, string> = {
  running:         "#2D4FD6",
  awaiting_review: "#D97706",
  complete:        "#16A34A",
  error:           "#DC2626",
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskRow[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try {
      const [ddRaw, reviewRaw] = await Promise.all([listDDTasks(), listReviewTasks()]);

      const ddRows: TaskRow[] = (ddRaw as Record<string, unknown>[]).map((t) => ({
        task_id: t.task_id as string,
        type: "dd",
        status: t.status as string,
        created_at: t.created_at as string,
        label: ((t.request as Record<string, unknown>)?.prompt as string ?? "DD Task").slice(0, 60),
      }));

      const reviewRows: TaskRow[] = (reviewRaw as Record<string, unknown>[]).map((t) => ({
        task_id: t.task_id as string,
        type: "review",
        status: t.status as string,
        created_at: t.created_at as string,
        label: `Contract Review — ${(t.task_id as string).slice(0, 8)}`,
      }));

      setTasks([...ddRows, ...reviewRows].sort((a, b) =>
        b.created_at.localeCompare(a.created_at)
      ));
    } catch {
      // silently fail — backend may not be running
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
        title="Attorney Task Dashboard"
        subtitle="Active DD + contract review tasks · auto-refreshes every 5s"
        right={
          <button
            onClick={refresh}
            className="text-[11px] px-3 py-1.5 rounded-lg transition-colors"
            style={{ background: "#F3F4F6", color: "#4B5563", border: "1px solid #E5E7EB" }}
          >
            Refresh
          </button>
        }
      />

      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="text-[13px] text-[#9CA3AF] mt-10 text-center">Loading tasks…</div>
        ) : tasks.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-[50vh] text-center">
            <div className="text-4xl mb-3">📋</div>
            <h3 className="text-[18px] text-[#111827] mb-1" style={{ fontFamily: "var(--font-dm-serif)" }}>
              No tasks yet
            </h3>
            <p className="text-[13px] text-[#6B7280]">
              Start a DD analysis or upload a contract for review.
            </p>
          </div>
        ) : (
          <div className="max-w-[860px] mx-auto">
            <table className="w-full border-collapse text-[12px]">
              <thead>
                <tr style={{ borderBottom: "2px solid #E5E7EB" }}>
                  {["Type", "Task", "Status", "Created", "Actions"].map((h) => (
                    <th key={h} className="text-left py-2 px-3 text-[11px] font-semibold text-[#6B7280] uppercase tracking-wide">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr
                    key={task.task_id}
                    className="transition-colors hover:bg-[#F9FAFB]"
                    style={{ borderBottom: "1px solid #F3F4F6" }}
                  >
                    {/* Type */}
                    <td className="py-3 px-3">
                      <span
                        className="text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase"
                        style={{
                          background: task.type === "dd" ? "#EEF2FF" : "#F0FDF4",
                          color: task.type === "dd" ? "#4F46E5" : "#16A34A",
                        }}
                      >
                        {task.type === "dd" ? "Due Diligence" : "Contract Review"}
                      </span>
                    </td>

                    {/* Label */}
                    <td className="py-3 px-3 text-[#374151] max-w-[260px]">
                      <span className="block truncate">{task.label}</span>
                      <span className="text-[10px] text-[#9CA3AF] font-mono">{task.task_id.slice(0, 8)}…</span>
                    </td>

                    {/* Status */}
                    <td className="py-3 px-3">
                      <span
                        className="text-[10px] px-2 py-0.5 rounded-full font-semibold"
                        style={{
                          background: `${STATUS_COLORS[task.status] ?? "#9CA3AF"}18`,
                          color: STATUS_COLORS[task.status] ?? "#9CA3AF",
                        }}
                      >
                        {task.status === "awaiting_review" ? "⚠ Awaiting Review" : task.status}
                      </span>
                    </td>

                    {/* Date */}
                    <td className="py-3 px-3 text-[#9CA3AF] whitespace-nowrap">
                      {task.created_at.slice(0, 16).replace("T", " ")}
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-3">
                      <div className="flex gap-2">
                        {task.status === "complete" && task.type === "dd" && (
                          <button
                            onClick={() => downloadDDReport(task.task_id)}
                            className="text-[10px] px-2.5 py-1 rounded font-semibold transition-colors"
                            style={{ background: "#EEF2FF", color: "#4F46E5" }}
                          >
                            Export PDF
                          </button>
                        )}
                        {task.status === "complete" && task.type === "review" && (
                          <button
                            onClick={() => downloadRedlinedDocx(task.task_id)}
                            className="text-[10px] px-2.5 py-1 rounded font-semibold transition-colors"
                            style={{ background: "#F0FDF4", color: "#16A34A" }}
                          >
                            Export DOCX
                          </button>
                        )}
                        {task.status === "awaiting_review" && (
                          <a
                            href={task.type === "dd" ? "/dd" : "/contract"}
                            className="text-[10px] px-2.5 py-1 rounded font-semibold"
                            style={{ background: "#FFFBEB", color: "#D97706" }}
                          >
                            Review Now →
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
