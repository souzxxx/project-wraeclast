"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Farm = {
  name: string;
  est_profit_per_hour: number | null;
  risk: string | null;
  investment_required: number | null;
  summary: string | null;
};
type State = {
  league: string;
  price_count: number;
  top_farms: Farm[];
  my_snapshot: { character_name?: string; char_class?: string; level?: number } | null;
};
type Sparkline = {
  name: string;
  item_type: string;
  points: number[];
  latest: number;
  change_pct: number | null;
};

export default function Home() {
  const [state, setState] = useState<State | null>(null);
  const [stateErr, setStateErr] = useState<string>("");

  useEffect(() => {
    fetch(`${API}/state`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setState)
      .catch((e) => setStateErr(String(e)));
  }, []);

  return (
    <main>
      <h1>Estado da Liga</h1>
      <p className="sub">
        Consultor de Path of Exile 2 que se atualiza sozinho todo dia
        {state ? ` — ${state.league} · ${state.price_count} itens precificados hoje` : ""}.
      </p>

      {stateErr && (
        <p className="err">Não consegui falar com a API ({stateErr}). O backend está rodando?</p>
      )}

      <div className="grid">
        <section className="card">
          <h2>Top farms por lucro/hora</h2>
          {!state && !stateErr && <p className="meta">Carregando…</p>}
          {state?.top_farms?.length ? (
            state.top_farms.map((f, i) => (
              <div className="farm" key={i}>
                <div className="name">
                  {i + 1}. {f.name} {f.risk && <span className="tag">{f.risk}</span>}
                </div>
                <div className="meta">
                  <span className="profit">~{f.est_profit_per_hour ?? "?"} chaos/h</span>
                  {f.investment_required != null && ` · invest ${f.investment_required}`}
                </div>
                {f.summary && <div className="meta">{f.summary}</div>}
              </div>
            ))
          ) : (
            state && <p className="meta">Nenhuma estratégia curada ainda.</p>
          )}
        </section>

        <section className="card">
          <h2>Minha build</h2>
          {state?.my_snapshot ? (
            <p>
              <strong>{state.my_snapshot.character_name || "?"}</strong> —{" "}
              {state.my_snapshot.char_class || "?"} lvl {state.my_snapshot.level || "?"}
            </p>
          ) : (
            state && <p className="meta">Nenhum snapshot de personagem ainda.</p>
          )}
          {state?.my_snapshot && <BuildDiff />}
          <p className="meta" style={{ marginTop: "1rem" }}>
            Quer testar um craft ou perguntar pro oráculo?{" "}
            <Link href="/craft">Bancada de craft</Link> · <Link href="/chat">Chat</Link>
          </p>
        </section>

        <section className="card" style={{ gridColumn: "1 / -1" }}>
          <h2>Moedas — variação recente</h2>
          <PriceSparklines />
        </section>
      </div>

      <p className="disclaimer">
        Todos os preços e lucros/hora são estimativas derivadas do poe.ninja e de texto da
        comunidade — não são garantias.
      </p>
    </main>
  );
}

function Sparkline({ points }: { points: number[] }) {
  const w = 96;
  const h = 24;
  const pad = 2;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const step = points.length > 1 ? (w - pad * 2) / (points.length - 1) : 0;
  const d = points
    .map((p, i) => {
      const x = pad + i * step;
      const y = pad + (h - pad * 2) * (1 - (p - min) / span);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const up = points[points.length - 1] >= points[0];
  return (
    <svg width={w} height={h} aria-hidden="true">
      <path d={d} fill="none" stroke={up ? "#74b46f" : "#e07b53"} strokeWidth={1.5} />
    </svg>
  );
}

function PriceSparklines() {
  const [series, setSeries] = useState<Sparkline[] | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch(`${API}/price-history`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => setSeries(d.sparklines || []))
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return <p className="meta">Não consegui carregar o histórico ({err}).</p>;
  if (!series) return <p className="meta">Carregando…</p>;
  if (series.length === 0)
    return <p className="meta">Histórico ainda curto — precisa de pelo menos dois dias.</p>;

  return (
    <div>
      {series.map((s) => {
        const chg = s.change_pct;
        const cls = chg == null ? "flat" : chg > 0 ? "up" : chg < 0 ? "down" : "flat";
        const label = chg == null ? "—" : `${chg > 0 ? "+" : ""}${chg}%`;
        return (
          <div className="spark-row" key={s.name}>
            <span className="name">{s.name}</span>
            <Sparkline points={s.points} />
            <span className="val">{s.latest} div</span>
            <span className={`chg ${cls}`}>{label}</span>
          </div>
        );
      })}
    </div>
  );
}

type BuildDiffResp = {
  comparable: boolean;
  meta_class?: string;
  consider_adding?: string[];
  consider_cutting?: string[];
  shared?: string[];
};

function BuildDiff() {
  const [diff, setDiff] = useState<BuildDiffResp | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch(`${API}/build`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setDiff)
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return null; // 404 = no snapshot; just hide
  if (!diff) return <p className="meta">Comparando com o meta…</p>;
  if (!diff.comparable)
    return (
      <p className="meta">
        Sem build de meta pra comparar ainda (a classe pode não estar no ladder do ninja).
      </p>
    );

  const add = diff.consider_adding ?? [];
  const cut = diff.consider_cutting ?? [];
  return (
    <div className="meta" style={{ marginTop: "0.6rem" }}>
      <div>vs meta de {diff.meta_class}:</div>
      {add.length > 0 && (
        <div>
          <span className="chg up">+ considere</span> {add.slice(0, 6).join(", ")}
        </div>
      )}
      {cut.length > 0 && (
        <div>
          <span className="chg down">− considere cortar</span> {cut.slice(0, 6).join(", ")}
        </div>
      )}
      {add.length === 0 && cut.length === 0 && <div>alinhado com o meta ({(diff.shared ?? []).length} gems em comum) ✓</div>}
    </div>
  );
}
