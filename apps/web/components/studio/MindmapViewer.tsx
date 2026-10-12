"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import type { StudioMindmapNode, StudioSourceRef } from "@/lib/studio";
import { studio } from "./strings";

type LayoutNode = StudioMindmapNode & {
  x: number;
  y: number;
  depth: number;
  children: LayoutNode[];
};

const NODE_W = 120;
const NODE_H = 36;
const H_GAP = 48;
const V_GAP = 16;

function buildTree(nodes: StudioMindmapNode[]): LayoutNode[] {
  const map = new Map<string, LayoutNode>();
  for (const n of nodes) {
    map.set(n.id, { ...n, x: 0, y: 0, depth: 0, children: [] });
  }
  const roots: LayoutNode[] = [];
  for (const n of map.values()) {
    if (n.parent_id && map.has(n.parent_id)) {
      map.get(n.parent_id)!.children.push(n);
    } else {
      roots.push(n);
    }
  }
  return roots.length ? roots : [...map.values()];
}

function layoutTree(node: LayoutNode, depth: number, yStart: number): number {
  node.depth = depth;
  if (node.collapsed || !node.children.length) {
    node.y = yStart;
    return yStart + NODE_H + V_GAP;
  }
  let y = yStart;
  for (const child of node.children) {
    y = layoutTree(child, depth + 1, y);
  }
  const first = node.children[0];
  const last = node.children[node.children.length - 1];
  node.y = (first.y + last.y) / 2;
  node.x = depth * (NODE_W + H_GAP);
  return y;
}

function collectVisible(node: LayoutNode, out: LayoutNode[] = []): LayoutNode[] {
  out.push(node);
  if (!node.collapsed) {
    for (const c of node.children) collectVisible(c, out);
  }
  return out;
}

export function MindmapViewer({
  nodes,
  onSelectSource,
  onToggleCollapse,
}: {
  nodes: StudioMindmapNode[];
  onSelectSource: (source: StudioSourceRef) => void;
  onToggleCollapse: (nodeId: string) => void;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [pan, setPan] = useState({ x: 40, y: 40 });
  const [zoom, setZoom] = useState(1);
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null);

  const layoutRoots = useMemo(() => {
    const roots = buildTree(nodes);
    let y = 0;
    for (const r of roots) {
      y = layoutTree(r, 0, y);
    }
    return roots;
  }, [nodes]);

  const visible = useMemo(() => layoutRoots.flatMap((r) => collectVisible(r)), [layoutRoots]);

  const edges = useMemo(() => {
    const lines: { x1: number; y1: number; x2: number; y2: number }[] = [];
    for (const n of visible) {
      if (n.parent_id) {
        const parent = visible.find((p) => p.id === n.parent_id);
        if (parent) {
          lines.push({
            x1: parent.x + NODE_W,
            y1: parent.y + NODE_H / 2,
            x2: n.x,
            y2: n.y + NODE_H / 2,
          });
        }
      }
    }
    return lines;
  }, [visible]);

  const exportSvg = useCallback(() => {
    const el = svgRef.current;
    if (!el) return;
    const blob = new Blob([new XMLSerializer().serializeToString(el)], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "mindmap.svg";
    a.click();
    URL.revokeObjectURL(url);
  }, []);

  const exportPng = useCallback(() => {
    const el = svgRef.current;
    if (!el) return;
    const xml = new XMLSerializer().serializeToString(el);
    const img = new Image();
    const url = URL.createObjectURL(new Blob([xml], { type: "image/svg+xml" }));
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = el.width.baseVal.value || 800;
      canvas.height = el.height.baseVal.value || 600;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0);
        canvas.toBlob((b) => {
          if (!b) return;
          const a = document.createElement("a");
          a.href = URL.createObjectURL(b);
          a.download = "mindmap.png";
          a.click();
        });
      }
      URL.revokeObjectURL(url);
    };
    img.src = url;
  }, []);

  if (!nodes.length) {
    return <p className="text-sm text-muted">{studio.emptyMindmap}</p>;
  }

  const maxX = Math.max(...visible.map((n) => n.x), 0) + NODE_W + 80;
  const maxY = Math.max(...visible.map((n) => n.y), 0) + NODE_H + 80;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <button type="button" className="secondary-button h-8 px-2 text-xs" onClick={exportSvg}>
          {studio.exportSvg}
        </button>
        <button type="button" className="secondary-button h-8 px-2 text-xs" onClick={exportPng}>
          {studio.exportPng}
        </button>
        <button
          type="button"
          className="secondary-button h-8 px-2 text-xs"
          onClick={() => setZoom((z) => Math.min(2, z + 0.15))}
        >
          Zoom +
        </button>
        <button
          type="button"
          className="secondary-button h-8 px-2 text-xs"
          onClick={() => setZoom((z) => Math.max(0.4, z - 0.15))}
        >
          Zoom −
        </button>
      </div>
      <div
        className="relative h-[480px] overflow-hidden rounded-2xl border border-border bg-surface"
        onPointerDown={(e) => {
          drag.current = { x: e.clientX, y: e.clientY, px: pan.x, py: pan.y };
        }}
        onPointerMove={(e) => {
          if (!drag.current) return;
          setPan({
            x: drag.current.px + (e.clientX - drag.current.x),
            y: drag.current.py + (e.clientY - drag.current.y),
          });
        }}
        onPointerUp={() => {
          drag.current = null;
        }}
        onPointerLeave={() => {
          drag.current = null;
        }}
      >
        <svg
          ref={svgRef}
          width={maxX}
          height={maxY}
          className="select-none"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transformOrigin: "0 0" }}
        >
          {edges.map((line, i) => (
            <line
              key={i}
              x1={line.x1}
              y1={line.y1}
              x2={line.x2}
              y2={line.y2}
              stroke="currentColor"
              strokeOpacity={0.25}
              strokeWidth={2}
            />
          ))}
          {visible.map((n) => {
            const hasChildren = n.children.length > 0;
            return (
              <g key={n.id} transform={`translate(${n.x}, ${n.y})`}>
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx={8}
                  fill="var(--surface-muted, #f1f5f9)"
                  stroke="var(--border, #e2e8f0)"
                  className="cursor-pointer"
                  onClick={() => {
                    if (hasChildren) onToggleCollapse(n.id);
                    if (n.source_ref) onSelectSource(n.source_ref);
                  }}
                />
                <text
                  x={NODE_W / 2}
                  y={NODE_H / 2 + 4}
                  textAnchor="middle"
                  fontSize={11}
                  fill="currentColor"
                  className="pointer-events-none"
                >
                  {n.label.length > 18 ? `${n.label.slice(0, 16)}…` : n.label}
                </text>
                {hasChildren ? (
                  <text x={NODE_W - 10} y={12} fontSize={10} fill="currentColor" className="pointer-events-none">
                    {n.collapsed ? "+" : "−"}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
