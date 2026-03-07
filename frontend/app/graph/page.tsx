"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import PageHeader from "@/components/layout/PageHeader";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Node type → color (stroke = outline + text, fill = circle fill)
const LABEL_COLOR: Record<string, { fill: string; stroke: string }> = {
  Statute:      { fill: "#6366F1", stroke: "#4338CA" },
  Case:         { fill: "#F97316", stroke: "#C2410C" },
  Provision:    { fill: "#22C55E", stroke: "#15803D" },
  LegalConcept: { fill: "#A855F7", stroke: "#7E22CE" },
  Entity:       { fill: "#F43F5E", stroke: "#BE123C" },
  Regulation:   { fill: "#10B981", stroke: "#065F46" },
  Chunk:        { fill: "#94A3B8", stroke: "#475569" },
};
const DEFAULT_COLOR = { fill: "#6B7280", stroke: "#374151" };

const NODE_TYPES = ["Statute", "Case", "Provision", "LegalConcept", "Entity", "Regulation", "Chunk"] as const;

interface RawNode {
  _id: string;
  _labels: string[];
  name?: string;
  title?: string;
  node_id?: string;
  jurisdiction?: string;
}
interface RawEdge { source: string; target: string; type: string; }
interface GraphData { nodes: RawNode[]; relationships: RawEdge[]; connected: boolean; }
interface SimNode extends RawNode { x: number; y: number; vx: number; vy: number; r: number; }

function nodeLabel(n: RawNode): string {
  return (n.name || n.title || n.node_id || n._id).slice(0, 20);
}
function primaryLabel(n: RawNode): string { return n._labels[0] ?? "Node"; }
function nodeColor(n: RawNode) { return LABEL_COLOR[primaryLabel(n)] ?? DEFAULT_COLOR; }

export default function GraphPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const simRef = useRef<SimNode[]>([]);
  const animRef = useRef<number>(0);
  const selectedRef = useRef<string | null>(null);
  const hoveredRef = useRef<string | null>(null);

  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [stats, setStats] = useState<{ connected: boolean; nodes: number; relationships: number; by_label: Record<string, number> } | null>(null);
  const [selectedNode, setSelectedNode] = useState<SimNode | null>(null);

  const authHeaders = (): HeadersInit => {
    const token = typeof window !== "undefined" ? localStorage.getItem("lexgraph_access_token") : null;
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  useEffect(() => {
    Promise.all([
      fetch(`${BASE_URL}/graph/stats`, { headers: authHeaders() }).then((r) => r.json()),
      fetch(`${BASE_URL}/graph/sample?limit=60`, { headers: authHeaders() }).then((r) => r.json()),
    ])
      .then(([s, g]) => { setStats(s); setGraphData(g); })
      .catch(() => setStats({ connected: false, nodes: 0, relationships: 0, by_label: {} }));
  }, []);

  // Run force simulation + canvas render whenever graph data loads
  useEffect(() => {
    if (!graphData || !canvasRef.current || !wrapRef.current) return;

    const canvas = canvasRef.current;
    const dpr = window.devicePixelRatio || 1;
    const W = wrapRef.current.clientWidth;
    const H = wrapRef.current.clientHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width = `${W}px`;
    canvas.style.height = `${H}px`;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);

    // Initialise simulation nodes arranged in a circle
    const nodeMap = new Map<string, SimNode>();
    const simNodes: SimNode[] = graphData.nodes.map((n, i) => {
      const angle = (i / graphData.nodes.length) * 2 * Math.PI;
      const rad = Math.min(W, H) * 0.28;
      const sn: SimNode = { ...n, x: W / 2 + rad * Math.cos(angle), y: H / 2 + rad * Math.sin(angle), vx: 0, vy: 0, r: 18 };
      nodeMap.set(n._id, sn);
      return sn;
    });
    simRef.current = simNodes;

    type SimEdge = RawEdge & { src: SimNode; tgt: SimNode };
    const edges: SimEdge[] = graphData.relationships
      .map((e) => ({ ...e, src: nodeMap.get(e.source)!, tgt: nodeMap.get(e.target)! }))
      .filter((e) => e.src && e.tgt);

    let iter = 0;
    let alpha = 1.0;

    const draw = () => {
      ctx.clearRect(0, 0, W, H);

      // Edges
      edges.forEach(({ src, tgt, type }) => {
        const dx = tgt.x - src.x;
        const dy = tgt.y - src.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;

        ctx.beginPath();
        ctx.moveTo(src.x, src.y);
        ctx.lineTo(tgt.x - (dx / dist) * tgt.r, tgt.y - (dy / dist) * tgt.r);
        ctx.strokeStyle = "#CBD5E1";
        ctx.lineWidth = 1;
        ctx.stroke();

        // Arrow
        const ang = Math.atan2(dy, dx);
        const ax = tgt.x - (dx / dist) * (tgt.r + 5);
        const ay = tgt.y - (dy / dist) * (tgt.r + 5);
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(ax - 7 * Math.cos(ang - 0.38), ay - 7 * Math.sin(ang - 0.38));
        ctx.lineTo(ax - 7 * Math.cos(ang + 0.38), ay - 7 * Math.sin(ang + 0.38));
        ctx.closePath();
        ctx.fillStyle = "#CBD5E1";
        ctx.fill();

        // Relationship type label at midpoint
        ctx.font = "7px monospace";
        ctx.fillStyle = "#94A3B8";
        ctx.textAlign = "center";
        ctx.fillText(type, (src.x + tgt.x) / 2, (src.y + tgt.y) / 2 - 3);
      });

      // Nodes
      simNodes.forEach((n) => {
        const color = nodeColor(n);
        const isSelected = selectedRef.current === n._id;
        const isHovered = hoveredRef.current === n._id;
        const r = isSelected ? n.r + 3 : n.r;

        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
        ctx.fillStyle = isHovered || isSelected ? color.stroke : color.fill;
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.font = `bold ${n.r > 14 ? 9 : 8}px sans-serif`;
        ctx.fillStyle = "#ffffff";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const lbl = nodeLabel(n);
        ctx.fillText(lbl.length > 12 ? lbl.slice(0, 11) + "…" : lbl, n.x, n.y);
      });
    };

    const step = () => {
      if (iter < 400) {
        alpha = Math.max(0.001, alpha * 0.98);

        // Repulsion between all node pairs
        for (let i = 0; i < simNodes.length; i++) {
          for (let j = i + 1; j < simNodes.length; j++) {
            const a = simNodes[i], b = simNodes[j];
            const dx = b.x - a.x || 0.01;
            const dy = b.y - a.y || 0.01;
            const d2 = dx * dx + dy * dy;
            const d = Math.sqrt(d2) || 1;
            const f = (2800 / d2) * alpha;
            a.vx -= (dx / d) * f; a.vy -= (dy / d) * f;
            b.vx += (dx / d) * f; b.vy += (dy / d) * f;
          }
        }

        // Spring attraction on edges
        edges.forEach(({ src, tgt }) => {
          const dx = tgt.x - src.x;
          const dy = tgt.y - src.y;
          const d = Math.sqrt(dx * dx + dy * dy) || 1;
          const f = (d - 110) * 0.07 * alpha;
          src.vx += (dx / d) * f; src.vy += (dy / d) * f;
          tgt.vx -= (dx / d) * f; tgt.vy -= (dy / d) * f;
        });

        // Gravity toward center
        simNodes.forEach((n) => {
          n.vx += (W / 2 - n.x) * 0.008 * alpha;
          n.vy += (H / 2 - n.y) * 0.008 * alpha;
          n.vx *= 0.88;
          n.vy *= 0.88;
          n.x = Math.max(n.r + 4, Math.min(W - n.r - 4, n.x + n.vx));
          n.y = Math.max(n.r + 4, Math.min(H - n.r - 4, n.y + n.vy));
        });

        iter++;
      }

      draw();
      animRef.current = requestAnimationFrame(step);
    };

    cancelAnimationFrame(animRef.current);
    animRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animRef.current);
  }, [graphData]);

  const pickNode = (e: React.MouseEvent<HTMLCanvasElement>): SimNode | null => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    for (const n of simRef.current) {
      const dx = n.x - x, dy = n.y - y;
      if (dx * dx + dy * dy < (n.r + 6) * (n.r + 6)) return n;
    }
    return null;
  };

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const hit = pickNode(e);
    hoveredRef.current = hit ? hit._id : null;
    if (canvasRef.current) canvasRef.current.style.cursor = hit ? "pointer" : "default";
  }, []);

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const hit = pickNode(e);
    if (hit) {
      const next = selectedRef.current === hit._id ? null : hit._id;
      selectedRef.current = next;
      setSelectedNode(next ? hit : null);
    } else {
      selectedRef.current = null;
      setSelectedNode(null);
    }
  }, []);

  return (
    <div className="flex flex-col h-full">
      <PageHeader title="Knowledge Graph" subtitle="Neo4j · JP/US statute and case law graph" />

      <div className="flex flex-1 overflow-hidden">
        {/* Left panel */}
        <div className="w-[200px] flex-shrink-0 border-r border-[#E5E7EB] bg-white overflow-y-auto flex flex-col">
          {/* Connection status */}
          <div className="px-4 pt-4 pb-3 border-b border-[#F3F4F6]">
            <div className="flex items-center gap-2 mb-2">
              <div
                className="w-2 h-2 rounded-full flex-shrink-0"
                style={{ background: stats === null ? "#D1D5DB" : stats.connected ? "#16A34A" : "#F97316" }}
              />
              <span className="text-[12px] font-semibold text-[#111827]">
                {stats === null ? "Connecting…" : stats.connected ? "Neo4j Live" : "Demo Mode"}
              </span>
            </div>
            {stats?.connected && (
              <div className="flex gap-4">
                <div>
                  <div className="text-[16px] font-bold text-[#2D4FD6]">{stats.nodes}</div>
                  <div className="text-[9px] text-[#9CA3AF]">Nodes</div>
                </div>
                <div>
                  <div className="text-[16px] font-bold text-[#2D4FD6]">{stats.relationships}</div>
                  <div className="text-[9px] text-[#9CA3AF]">Rels</div>
                </div>
              </div>
            )}
          </div>

          {/* Legend */}
          <div className="px-4 py-3">
            <div className="text-[9px] font-semibold text-[#9CA3AF] uppercase tracking-wide mb-2">Node Types</div>
            {NODE_TYPES.map((label) => {
              const color = LABEL_COLOR[label] ?? DEFAULT_COLOR;
              const count = stats?.by_label[label];
              return (
                <div key={label} className="flex items-center gap-2 py-0.5">
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: color.fill }} />
                  <span className="text-[11px] text-[#374151] flex-1">{label}</span>
                  {count != null && <span className="text-[10px] text-[#9CA3AF]">{count}</span>}
                </div>
              );
            })}
          </div>

          {/* Selected node detail */}
          {selectedNode && (
            <div className="px-4 py-3 border-t border-[#F3F4F6] mt-auto">
              <div className="text-[9px] font-semibold text-[#9CA3AF] uppercase tracking-wide mb-2">Selected</div>
              <div
                className="rounded-lg px-3 py-2"
                style={{
                  background: (nodeColor(selectedNode).fill) + "22",
                  border: `1px solid ${nodeColor(selectedNode).fill}`,
                }}
              >
                <div className="text-[11px] font-semibold text-[#111827]">{nodeLabel(selectedNode)}</div>
                <div className="text-[9px] mt-0.5" style={{ color: nodeColor(selectedNode).stroke }}>
                  {primaryLabel(selectedNode)}{selectedNode.jurisdiction ? ` · ${selectedNode.jurisdiction}` : ""}
                </div>
                {selectedNode.title && selectedNode.title !== nodeLabel(selectedNode) && (
                  <div className="text-[10px] text-[#6B7280] mt-1 leading-tight">{selectedNode.title}</div>
                )}
              </div>
              <div className="text-[9px] text-[#9CA3AF] mt-2 font-mono break-all">{selectedNode._id}</div>
            </div>
          )}

          <div className="mt-auto px-4 pb-4">
            <div className="text-[9px] text-[#D1D5DB] text-center">Click a node to inspect</div>
          </div>
        </div>

        {/* Canvas area */}
        <div ref={wrapRef} className="flex-1 relative bg-[#F8FAFC] overflow-hidden">
          <canvas
            ref={canvasRef}
            className="absolute inset-0"
            onMouseMove={handleMouseMove}
            onClick={handleClick}
          />
          {!graphData && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-[13px] text-[#9CA3AF]">Loading graph…</div>
            </div>
          )}
          {graphData && !graphData.connected && (
            <div
              className="absolute top-3 right-3 text-[10px] px-2.5 py-1 rounded-full"
              style={{ background: "#FFF7ED", border: "1px solid #FED7AA", color: "#C2410C" }}
            >
              Demo data · Neo4j not connected
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
