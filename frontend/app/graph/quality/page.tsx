"use client";

import { useEffect, useState } from "react";
import PageHeader from "@/components/layout/PageHeader";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface QualityData {
  connected: boolean;
  total_nodes?: number;
  archived_nodes?: number;
  archived_ratio?: number;
  active_by_label?: Record<string, number>;
  orphaned_count?: number;
  unverified_count?: number;
  unverified_nodes?: { node_id: string; law_name: string; last_verified: string | null; labels: string[] }[];
  stale_laws?: { node_id: string; name: string; last_verified: string | null; jurisdiction: string }[];
  error?: string;
}

interface IntegrityData {
  errors?: number;
  warnings?: number;
  orphaned_nodes?: unknown[];
  active_with_amendment?: unknown[];
  future_effective_active?: unknown[];
  skipped?: boolean;
  reason?: string;
}

function StatCard({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: string }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-5 flex flex-col gap-1 shadow-sm">
      <span className="text-xs text-gray-500 font-medium uppercase tracking-wide">{label}</span>
      <span className={`text-3xl font-bold ${accent ?? "text-gray-900"}`}>{value}</span>
      {sub && <span className="text-xs text-gray-400">{sub}</span>}
    </div>
  );
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span className={`inline-block w-2 h-2 rounded-full mr-2 ${ok ? "bg-green-500" : "bg-red-500"}`} />
  );
}

export default function GraphQualityPage() {
  const [quality, setQuality] = useState<QualityData | null>(null);
  const [integrity, setIntegrity] = useState<IntegrityData | null>(null);
  const [loading, setLoading] = useState(true);

  const authHeaders = (): HeadersInit => {
    const token = typeof window !== "undefined" ? localStorage.getItem("lexgraph_access_token") : null;
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const load = () => {
    setLoading(true);
    Promise.all([
      fetch(`${BASE_URL}/graph/quality`, { headers: authHeaders() }).then((r) => r.json()),
      fetch(`${BASE_URL}/graph/integrity`, { headers: authHeaders() }).then((r) => r.json()),
    ])
      .then(([q, i]) => {
        setQuality(q);
        setIntegrity(i);
      })
      .catch((e) => setQuality({ connected: false, error: String(e) }))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const archivedPct = quality?.archived_ratio != null
    ? `${(quality.archived_ratio * 100).toFixed(1)}%`
    : "—";

  const nodeLabels = Object.entries(quality?.active_by_label ?? {});

  return (
    <div className="flex flex-col h-full bg-gray-50">
      <PageHeader
        title="Graph Quality Dashboard"
        subtitle="RDD §10.6 — Knowledge graph health metrics"
      />

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Connection status */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">
            <StatusDot ok={quality?.connected ?? false} />
            {quality?.connected ? "Neo4j connected" : "Neo4j disconnected"}
          </span>
          <button
            onClick={load}
            className="text-sm px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-100 text-gray-700"
          >
            Refresh
          </button>
        </div>

        {loading && (
          <div className="text-center py-16 text-gray-400 text-sm">Loading quality metrics…</div>
        )}

        {!loading && quality?.error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
            {quality.error}
          </div>
        )}

        {!loading && quality?.connected && (
          <>
            {/* KPI row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard
                label="Total Nodes"
                value={quality.total_nodes ?? 0}
                sub="all labels"
              />
              <StatCard
                label="ARCHIVED Ratio"
                value={archivedPct}
                sub={`${quality.archived_nodes ?? 0} archived`}
                accent={(quality.archived_ratio ?? 0) > 0.3 ? "text-amber-600" : "text-gray-900"}
              />
              <StatCard
                label="Orphaned Nodes"
                value={quality.orphaned_count ?? 0}
                sub="no edges"
                accent={(quality.orphaned_count ?? 0) > 0 ? "text-orange-500" : "text-green-600"}
              />
              <StatCard
                label="Unverified (>90d)"
                value={quality.unverified_count ?? 0}
                sub="needs review"
                accent={(quality.unverified_count ?? 0) > 0 ? "text-red-600" : "text-green-600"}
              />
            </div>

            {/* Integrity check summary */}
            {integrity && !integrity.skipped && (
              <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Integrity Checks (§10.4)</h3>
                <div className="flex gap-6 text-sm">
                  <span>
                    <StatusDot ok={(integrity.errors ?? 0) === 0} />
                    <span className="font-medium">{integrity.errors ?? 0}</span> errors
                  </span>
                  <span>
                    <StatusDot ok={(integrity.warnings ?? 0) === 0} />
                    <span className="font-medium">{integrity.warnings ?? 0}</span> warnings
                  </span>
                  {(integrity.active_with_amendment?.length ?? 0) > 0 && (
                    <span className="text-amber-600">
                      {integrity.active_with_amendment!.length} ACTIVE+AMENDED_BY conflicts
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Active nodes by label */}
            {nodeLabels.length > 0 && (
              <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Active Nodes by Type</h3>
                <div className="space-y-2">
                  {nodeLabels.map(([label, count]) => {
                    const max = Math.max(...nodeLabels.map(([, c]) => c));
                    const pct = max > 0 ? (count / max) * 100 : 0;
                    return (
                      <div key={label} className="flex items-center gap-3">
                        <span className="w-32 text-xs text-gray-600 truncate">{label}</span>
                        <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-indigo-500 rounded-full"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="w-10 text-right text-xs text-gray-500">{count}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Stale statutes */}
            {(quality.stale_laws?.length ?? 0) > 0 && (
              <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">
                  Stalest Statutes (oldest last_verified)
                </h3>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-gray-400 border-b border-gray-100">
                      <th className="pb-2 font-medium">Statute</th>
                      <th className="pb-2 font-medium">Jurisdiction</th>
                      <th className="pb-2 font-medium">Last Verified</th>
                      <th className="pb-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {quality.stale_laws!.map((law) => {
                      const daysAgo = law.last_verified
                        ? Math.floor((Date.now() - new Date(law.last_verified).getTime()) / 86_400_000)
                        : null;
                      const isStale = daysAgo === null || daysAgo > 90;
                      return (
                        <tr key={law.node_id} className="border-b border-gray-50 hover:bg-gray-50">
                          <td className="py-2 text-gray-800 font-medium">{law.name ?? law.node_id}</td>
                          <td className="py-2 text-gray-500">{law.jurisdiction ?? "—"}</td>
                          <td className="py-2 text-gray-500">
                            {law.last_verified ? new Date(law.last_verified).toLocaleDateString() : "never"}
                          </td>
                          <td className="py-2">
                            <span
                              className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                isStale
                                  ? "bg-red-100 text-red-700"
                                  : "bg-green-100 text-green-700"
                              }`}
                            >
                              {daysAgo === null ? "unverified" : `${daysAgo}d ago`}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Unverified nodes sample */}
            {(quality.unverified_nodes?.length ?? 0) > 0 && (
              <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
                <h3 className="text-sm font-semibold text-gray-700 mb-1">
                  Unverified Nodes — Sample (top 20)
                </h3>
                <p className="text-xs text-gray-400 mb-3">
                  Nodes with <code>last_verified</code> older than 90 days or never set. Requires manual review.
                </p>
                <div className="space-y-1 max-h-60 overflow-y-auto">
                  {quality.unverified_nodes!.map((n) => (
                    <div key={n.node_id} className="flex items-center gap-2 text-xs py-1 border-b border-gray-50">
                      <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-[10px]">
                        {n.labels[0] ?? "Node"}
                      </span>
                      <span className="text-gray-700 font-medium truncate flex-1">
                        {n.node_id}
                      </span>
                      {n.law_name && (
                        <span className="text-gray-400 truncate max-w-[120px]">{n.law_name}</span>
                      )}
                      <span className="text-red-400 shrink-0">
                        {n.last_verified ? new Date(n.last_verified).toLocaleDateString() : "never"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {!loading && !quality?.connected && !quality?.error && (
          <div className="text-center py-16 text-gray-400 text-sm">
            Neo4j is not connected. Start the database to see quality metrics.
          </div>
        )}
      </div>
    </div>
  );
}
