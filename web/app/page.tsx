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

        <section className="card chat" style={{ gridColumn: "1 / -1" }}>
          <h2>Ask the league</h2>
          <Chat />
        </section>
      </div>

      <p className="disclaimer">
        All prices and profit/hour figures are estimates derived from poe.ninja and community
        text — not guarantees.
      </p>
    </main>
  );
}

function Chat() {
  const [q, setQ] = useState("");
  const [resp, setResp] = useState<ChatResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  async function ask() {
    if (!q.trim()) return;
    setLoading(true);
    setErr("");
    setResp(null);
    try {
      const r = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResp(await r.json());
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
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
