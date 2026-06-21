"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { API, TYPE_COLORS } from "../lib";

// cast to any: the lib ships its own NodeObject types; we drive it with our own Node shape.
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false }) as any;

type Node = { id: string; label: string; type: string; x?: number; y?: number };
type GraphData = { nodes: Node[]; links: { source: string; target: string }[] };

const RADIUS: Record<string, number> = {
  league: 9,
  farm: 7,
  build: 7,
  source: 4,
  item: 4,
  gem: 4,
  currency: 5,
};

export default function CerebroPage() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<GraphData | null>(null);
  const [err, setErr] = useState("");
  const [size, setSize] = useState({ w: 800, h: 600 });
  const [selected, setSelected] = useState<Node | null>(null);

  useEffect(() => {
    fetch(`${API}/graph`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => setData({ nodes: d.nodes, links: d.links }))
      .catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    function resize() {
      const w = wrapRef.current?.clientWidth || 800;
      setSize({ w, h: Math.max(420, Math.round(window.innerHeight * 0.66)) });
    }
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, [data]);

  return (
    <main>
      <h1>Cérebro</h1>
      <p className="sub">
        Tudo que o agente sabe, ligado entre si — farms, fontes, itens, sua build, economia.
        Arraste, dê zoom, clique num nó.
      </p>
      {err && <p className="err">Não consegui carregar o grafo ({err}).</p>}

      <div className="legend">
        {Object.entries(TYPE_COLORS).map(([t, c]) => (
          <span key={t}>
            <i style={{ background: c }} /> {t}
          </span>
        ))}
      </div>

      <div className="graph-wrap" ref={wrapRef}>
        {data && (
          <ForceGraph2D
            graphData={data}
            width={size.w}
            height={size.h}
            backgroundColor="#0d0b07"
            linkColor={() => "rgba(156,139,106,0.25)"}
            cooldownTicks={120}
            onNodeClick={(n: Node) => setSelected(n)}
            nodeLabel={(n: Node) => `${n.label} (${n.type})`}
            nodePointerAreaPaint={(n: Node, color: string, ctx: CanvasRenderingContext2D) => {
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(n.x || 0, n.y || 0, (RADIUS[n.type] || 4) + 2, 0, 2 * Math.PI);
              ctx.fill();
            }}
            nodeCanvasObject={(n: Node, ctx: CanvasRenderingContext2D, scale: number) => {
              const r = RADIUS[n.type] || 4;
              ctx.fillStyle = TYPE_COLORS[n.type] || "#999";
              ctx.beginPath();
              ctx.arc(n.x || 0, n.y || 0, r, 0, 2 * Math.PI);
              ctx.fill();
              if (scale > 1.2 || r >= 7) {
                ctx.font = `${11 / scale}px ui-sans-serif, sans-serif`;
                ctx.fillStyle = "#e8dcc0";
                ctx.textAlign = "center";
                ctx.textBaseline = "top";
                ctx.fillText(n.label.slice(0, 28), n.x || 0, (n.y || 0) + r + 1);
              }
            }}
          />
        )}
        {!data && !err && <p className="meta">Carregando grafo…</p>}

        {selected && (
          <div className="node-panel">
            <button className="close" aria-label="Fechar" onClick={() => setSelected(null)}>
              ✕
            </button>
            <span className="tag" style={{ borderColor: TYPE_COLORS[selected.type] }}>
              {selected.type}
            </span>
            <p className="name">{selected.label}</p>
            {selected.id.startsWith("src:") && (
              <a href={selected.id.slice(4)} target="_blank" rel="noreferrer">
                Abrir fonte ↗
              </a>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
