"use client";

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
type ChatResp = { answer: string; sources: { url: string; title: string }[] };
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
      <h1>Project Wraeclast</h1>
      <p className="sub">
        Auto-updating Path of Exile 2 advisor
        {state ? ` · league: ${state.league} · ${state.price_count} priced items today` : ""}
      </p>

      {stateErr && (
        <p className="err">Could not reach the API ({stateErr}). Is the backend running?</p>
      )}

      <div className="grid">
        <section className="card">
          <h2>Top farms by profit/hour</h2>
          {!state && !stateErr && <p className="meta">Loading…</p>}
          {state?.top_farms?.length ? (
            state.top_farms.map((f, i) => (
              <div className="farm" key={i}>
                <div className="name">
                  {i + 1}. {f.name}{" "}
                  {f.risk && <span className="tag">{f.risk}</span>}
                </div>
                <div className="meta">
                  <span className="profit">~{f.est_profit_per_hour ?? "?"} chaos/h</span>
                  {f.investment_required != null && ` · invest ${f.investment_required}`}
                </div>
                {f.summary && <div className="meta">{f.summary}</div>}
              </div>
            ))
          ) : (
            state && <p className="meta">No strategies curated yet.</p>
          )}
        </section>

        <section className="card">
          <h2>My build</h2>
          {state?.my_snapshot ? (
            <p>
              <strong>{state.my_snapshot.character_name || "?"}</strong> —{" "}
              {state.my_snapshot.char_class || "?"} lvl {state.my_snapshot.level || "?"}
            </p>
          ) : (
            state && <p className="meta">No character snapshot yet.</p>
          )}
        </section>

        <section className="card" style={{ gridColumn: "1 / -1" }}>
          <h2>Currency price moves (last days)</h2>
          <PriceSparklines />
        </section>

        <section className="card chat" style={{ gridColumn: "1 / -1" }}>
          <h2>Ask the league</h2>
          <Chat />
        </section>

        <section className="card chat" style={{ gridColumn: "1 / -1" }}>
          <h2>Add knowledge</h2>
          <AddKnowledge />
        </section>
      </div>

      <p className="disclaimer">
        All prices and profit/hour figures are estimates derived from poe.ninja and community
        text — not guarantees.
      </p>
    </main>
  );
}

const TOKEN_KEY = "wraeclast_chat_token";

function Chat() {
  const [q, setQ] = useState("");
  const [resp, setResp] = useState<ChatResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [token, setToken] = useState("");
  const [pwInput, setPwInput] = useState("");

  useEffect(() => {
    setToken(localStorage.getItem(TOKEN_KEY) || "");
  }, []);

  function saveToken() {
    if (!pwInput.trim()) return;
    localStorage.setItem(TOKEN_KEY, pwInput.trim());
    setToken(pwInput.trim());
    setPwInput("");
    setErr("");
  }

  function forget() {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
  }

  async function ask() {
    if (!q.trim()) return;
    setLoading(true);
    setErr("");
    setResp(null);
    try {
      const r = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "content-type": "application/json", "x-access-token": token },
        body: JSON.stringify({ question: q }),
      });
      if (r.status === 401) {
        forget();
        throw new Error("Senha inválida — digite novamente.");
      }
      if (r.status === 503) throw new Error("Chat ainda não configurado no servidor.");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResp(await r.json());
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e));
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <>
        <p className="meta">O chat é protegido por senha (evita abuso dos tokens de LLM).</p>
        <input
          type="password"
          value={pwInput}
          onChange={(e) => setPwInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && saveToken()}
          placeholder="Senha de acesso"
          style={{
            width: "100%",
            background: "#0d0b07",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "0.6rem",
            font: "inherit",
          }}
        />
        <button onClick={saveToken}>Desbloquear</button>
        {err && <p className="err">{err}</p>}
      </>
    );
  }

  return (
    <>
      <textarea
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="e.g. What's the best farm right now for a mid-budget character?"
      />
      <button onClick={ask} disabled={loading}>
        {loading ? "Thinking…" : "Ask"}
      </button>
      <button
        onClick={forget}
        style={{ marginLeft: 8, background: "transparent", color: "var(--muted)", border: "1px solid var(--border)" }}
      >
        Esquecer senha
      </button>
      {err && <p className="err">{err}</p>}
      {resp && (
        <div className="answer">
          {resp.answer}
          {resp.sources?.length > 0 && (
            <div className="sources">
              <p className="meta">Sources:</p>
              {resp.sources.map((s, i) => (
                <a key={i} href={s.url} target="_blank" rel="noreferrer">
                  {s.title || s.url}
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </>
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
      <path d={d} fill="none" stroke={up ? "#5fae6f" : "#e07b53"} strokeWidth={1.5} />
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

  if (err) return <p className="meta">Could not load price history ({err}).</p>;
  if (!series) return <p className="meta">Loading…</p>;
  if (series.length === 0)
    return <p className="meta">Not enough price history yet — needs at least two days.</p>;

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
            <span className="val">{s.latest} c</span>
            <span className={`chg ${cls}`}>{label}</span>
          </div>
        );
      })}
    </div>
  );
}

function AddKnowledge() {
  const [value, setValue] = useState("");
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);

  async function add() {
    if (!value.trim()) return;
    const token = localStorage.getItem(TOKEN_KEY) || "";
    if (!token) {
      setMsg("Desbloqueie o chat acima primeiro (mesma senha).");
      return;
    }
    setLoading(true);
    setMsg("");
    try {
      const r = await fetch(`${API}/ingest`, {
        method: "POST",
        headers: { "content-type": "application/json", "x-access-token": token },
        body: JSON.stringify({ value }),
      });
      if (r.status === 401) throw new Error("Senha inválida.");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setMsg(`✓ Adicionado: ${d.title}`);
      setValue("");
    } catch (e) {
      setMsg(String(e instanceof Error ? e.message : e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <p className="meta">Cole um link (post, guia, vídeo) ou texto que valha a pena lembrar.</p>
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="https://… ou anote sua descoberta de farming aqui"
      />
      <button onClick={add} disabled={loading}>
        {loading ? "Salvando…" : "Adicionar ao conhecimento"}
      </button>
      {msg && <p className="meta">{msg}</p>}
    </>
  );
}
