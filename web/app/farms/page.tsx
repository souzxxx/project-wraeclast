"use client";

import { useEffect, useState } from "react";
import { API } from "../lib";

type Guide = {
  name: string;
  profit_per_hour: number | null;
  risk: string | null;
  target_currency: string | null;
  overview: string | null;
  steps: string[];
  items: { name: string; purpose: string }[];
  atlas: string | null;
  faq: { q: string; a: string }[];
  sources: { url: string; title: string }[];
};

export default function FarmsPage() {
  const [guides, setGuides] = useState<Guide[] | null>(null);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState<number | null>(0);

  useEffect(() => {
    fetch(`${API}/farm/guides`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => setGuides(d.guides))
      .catch((e) => setErr(String(e)));
  }, []);

  return (
    <main>
      <h1>Farms</h1>
      <p className="sub">Guias passo-a-passo das estratégias consolidadas. Tudo é estimativa.</p>
      {err && <p className="err">Não consegui carregar ({err}).</p>}
      {!guides && !err && <p className="meta">Carregando…</p>}
      {guides && guides.length === 0 && (
        <p className="meta">Nenhum guia ainda — eles são gerados na coleta diária.</p>
      )}

      <div className="guides">
        {guides?.map((g, i) => (
          <article className="card guide" key={i}>
            <button className="guide-head" onClick={() => setOpen(open === i ? null : i)}>
              <span className="name">{g.name}</span>
              <span className="meta">
                {g.profit_per_hour != null && <span className="profit">~{g.profit_per_hour} div/h</span>}
                {g.risk && <span className="tag">{g.risk}</span>}
                <span className="chev">{open === i ? "▲" : "▼"}</span>
              </span>
            </button>

            {open === i && (
              <div className="guide-body">
                {g.overview && <p>{g.overview}</p>}

                {g.steps?.length > 0 && (
                  <>
                    <h3>Passo a passo</h3>
                    <ol>{g.steps.map((s, j) => <li key={j}>{s}</li>)}</ol>
                  </>
                )}

                {g.items?.length > 0 && (
                  <>
                    <h3>Itens necessários</h3>
                    <ul className="items">
                      {g.items.map((it, j) => (
                        <li key={j}>
                          <strong>{it.name}</strong>
                          {it.purpose ? ` — ${it.purpose}` : ""}
                        </li>
                      ))}
                    </ul>
                  </>
                )}

                {g.atlas && (
                  <>
                    <h3>Atlas — como montar e upar</h3>
                    <p>{g.atlas}</p>
                  </>
                )}

                {g.faq?.length > 0 && (
                  <>
                    <h3>Dúvidas comuns</h3>
                    {g.faq.map((f, j) => (
                      <div key={j} className="faq">
                        <p className="q">{f.q}</p>
                        <p className="a">{f.a}</p>
                      </div>
                    ))}
                  </>
                )}

                {g.sources?.length > 0 && (
                  <div className="sources">
                    <p className="meta">Fontes:</p>
                    {g.sources.map((s, j) => (
                      <a key={j} href={s.url} target="_blank" rel="noreferrer">
                        {s.title || s.url}
                      </a>
                    ))}
                  </div>
                )}
              </div>
            )}
          </article>
        ))}
      </div>
    </main>
  );
}
