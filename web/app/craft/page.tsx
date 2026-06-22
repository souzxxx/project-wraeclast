"use client";

import { useEffect, useMemo, useState } from "react";
import { API } from "../lib";
import { BASES, ORBS, getBase, type OrbDef } from "./data";
import { applyOrb, canApply, newBase, type Item } from "./engine";

type PriceMap = Record<string, { chaos: number | null; divine: number | null }>;
type LedgerEntry = { label: string; div: number | null };
type CraftCard = { source_url: string; title: string; snippet: string };
type EVMethod = {
  name: string;
  item_base: string;
  output: string;
  mechanics: string[];
  success_prob: number | null;
  expected_cost_div: number | null;
  roi_pct: number | null;
  priced: boolean;
  missing_prices: string[];
};
type Guide = {
  name: string;
  item_base: string;
  budget: string | null;
  mechanics: string[];
  expected_cost_div: number | null;
  roi_pct: number | null;
  overview: string;
  steps: string[];
  items: { name: string; purpose: string }[];
  faq: { q: string; a: string }[];
  sources: { url: string; title: string }[];
};

const CAP: Record<Item["rarity"], number> = { normal: 0, magic: 1, rare: 3 };

function fmt(n: number): string {
  if (n >= 100) return String(Math.round(n));
  if (n >= 10) return n.toFixed(1);
  return n.toFixed(2);
}

// Near-zero-cost crafts produce astronomical ROI %, so show those as a multiplier instead.
function fmtRoi(roi: number | null): string {
  if (roi == null) return "—";
  if (roi >= 1000) return `+${(roi / 100).toFixed(1)}×`;
  if (roi === 0) return "0%";
  return `${roi > 0 ? "+" : ""}${roi}%`;
}

function roiClass(roi: number | null): "up" | "down" | "flat" {
  if (roi == null || roi === 0) return "flat";
  return roi > 0 ? "up" : "down";
}

function pct(p: number | null): string {
  return p == null ? "—" : `${Math.round(p * 100)}% sucesso`;
}

function Mechs({ list }: { list: string[] }) {
  if (!list?.length) return null;
  return (
    <div className="mech-chips">
      {list.map((m, idx) => (
        <span className="mech" key={`${m}-${idx}`}>
          {m}
        </span>
      ))}
    </div>
  );
}

export default function CraftPage() {
  return (
    <main>
      <h1>Craft</h1>
      <p className="sub">
        O que vale craftar agora (rankeado por ROI calculado dos preços vivos), os guias
        passo-a-passo, e a bancada pra você treinar o fluxo antes de gastar divine.
      </p>
      <CraftAlerts />
      <CraftRanking />
      <CraftGuideList />
      <Bench />
      <CraftKnowledge />
    </main>
  );
}

type Alert = {
  name: string;
  kind: "into_profit" | "out_of_profit";
  from_roi: number | null;
  to_roi: number | null;
  cost_div: number | null;
};

function CraftAlerts() {
  const [alerts, setAlerts] = useState<Alert[] | null>(null);

  useEffect(() => {
    fetch(`${API}/craft/alerts`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error())))
      .then((d) => setAlerts(d.alerts || []))
      .catch(() => setAlerts([]));
  }, []);

  if (!alerts || alerts.length === 0) return null;

  return (
    <section
      className="craft-alerts"
      aria-label="Alertas de craft de hoje"
      role="status"
      aria-live="polite"
    >
      <h2>🔔 Mudou de status hoje</h2>
      {alerts.map((a) => (
        <div className={`alert ${a.kind === "into_profit" ? "into" : "out"}`} key={a.name}>
          <span className="dot" aria-hidden="true" />
          <span className="atext">
            <strong>{a.name}</strong>{" "}
            {a.kind === "into_profit"
              ? `cruzou pra lucro — ROI ${fmtRoi(a.from_roi)} → ${fmtRoi(a.to_roi)}` +
                (a.cost_div != null ? ` (~${fmt(a.cost_div)} div)` : "")
              : `saiu do lucro — ROI ${fmtRoi(a.from_roi)} → ${fmtRoi(a.to_roi)}`}
          </span>
        </div>
      ))}
    </section>
  );
}

function CraftRanking() {
  const [methods, setMethods] = useState<EVMethod[] | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch(`${API}/craft/ev`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => setMethods(d.methods || []))
      .catch((e) => setErr(String(e)));
  }, []);

  return (
    <section className="craft-section">
      <h2>Melhores crafts por ROI</h2>
      <p className="meta">
        Custo dos insumos é ao vivo (poe.ninja); chance de sucesso e valor de saída são
        estimativas. ROI = lucro ÷ custo esperado (já com retries). ROI negativo = prejuízo hoje.
      </p>
      {err && <p className="meta">Não consegui carregar o ranking ({err}).</p>}
      {!methods && !err && <p className="meta">Carregando…</p>}
      {methods && methods.length === 0 && (
        <p className="meta">Nenhum método ainda — chega na coleta de hoje à noite.</p>
      )}
      {methods && methods.length > 0 && (
        <div className="ev-list">
          {methods.map((m, i) => {
            const cls = roiClass(m.roi_pct);
            return (
              <div className="ev-row card" key={i}>
                <div className="ev-rank">{i + 1}</div>
                <div className="ev-main">
                  <div className="ev-name">{m.name}</div>
                  <div className="meta">→ {m.output}</div>
                  <Mechs list={m.mechanics} />
                </div>
                <div className="ev-econ">
                  {m.priced && m.roi_pct != null ? (
                    <>
                      <span className={`roi ${cls}`}>{fmtRoi(m.roi_pct)}</span>
                      <span className="ev-sub">
                        ~{fmt(m.expected_cost_div ?? 0)} div · {pct(m.success_prob)}
                      </span>
                    </>
                  ) : (
                    <span className="ev-sub">
                      custo n/d
                      {m.missing_prices?.length ? ` · faltam ${m.missing_prices.length}` : ""}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function CraftGuideList() {
  const [guides, setGuides] = useState<Guide[] | null>(null);
  const [open, setOpen] = useState<number | null>(0);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch(`${API}/craft/guides`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => setGuides(d.guides || []))
      .catch((e) => setErr(String(e)));
  }, []);

  return (
    <section className="craft-section">
      <h2>Guias de craft (passo a passo)</h2>
      <p className="meta">Tutoriais em PT-BR gerados na coleta diária. Custo/ROI são calculados.</p>
      {err && <p className="meta">Não consegui carregar os guias ({err}).</p>}
      {!guides && !err && <p className="meta">Carregando…</p>}
      {guides && guides.length === 0 && (
        <p className="meta">Nenhum guia ainda — eles são gerados na coleta de hoje à noite.</p>
      )}
      <div className="guides">
        {guides?.map((g, i) => {
          const cls = roiClass(g.roi_pct);
          return (
            <article className="card guide" key={i}>
              <button
                className="guide-head"
                onClick={() => setOpen(open === i ? null : i)}
                aria-expanded={open === i}
                aria-controls={`craft-guide-${i}`}
              >
                <span className="name">{g.name}</span>
                <span className="meta">
                  {g.roi_pct != null && <span className={`roi ${cls}`}>{fmtRoi(g.roi_pct)}</span>}
                  {g.budget && <span className="tag">{g.budget}</span>}
                  <span className="chev" aria-hidden="true">{open === i ? "▲" : "▼"}</span>
                </span>
              </button>
              {open === i && (
                <div className="guide-body" id={`craft-guide-${i}`}>
                  <Mechs list={g.mechanics} />
                  {g.expected_cost_div != null && (
                    <p className="meta">
                      Custo esperado ~{fmt(g.expected_cost_div)} div (preços vivos)
                      {g.item_base ? ` · base ${g.item_base}` : ""}
                    </p>
                  )}
                  {g.overview && <p>{g.overview}</p>}
                  {g.steps?.length > 0 && (
                    <>
                      <h3>Passo a passo</h3>
                      <ol>{g.steps.map((s, j) => <li key={j}>{s}</li>)}</ol>
                    </>
                  )}
                  {g.items?.length > 0 && (
                    <>
                      <h3>Insumos</h3>
                      <ul>
                        {g.items.map((it, j) => (
                          <li key={j}>
                            <strong>{it.name}</strong>
                            {it.purpose ? ` — ${it.purpose}` : ""}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                  {g.faq?.length > 0 && (
                    <>
                      <h3>Dúvidas comuns</h3>
                      <div className="faq">
                        {g.faq.map((f, j) => (
                          <div key={j}>
                            <p className="q">{f.q}</p>
                            <p className="a">{f.a}</p>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                  {g.sources?.length > 0 && (
                    <div className="sources">
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
          );
        })}
      </div>
    </section>
  );
}

function Bench() {
  const [baseId, setBaseId] = useState(BASES[0].id);
  const base = useMemo(() => getBase(baseId), [baseId]);
  const [item, setItem] = useState<Item>(() => newBase(getBase(BASES[0].id)));
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [past, setPast] = useState<{ item: Item; ledger: LedgerEntry[] }[]>([]);
  const [log, setLog] = useState<{ text: string; ok: boolean } | null>(null);
  const [prices, setPrices] = useState<PriceMap>({});
  const [pricesOk, setPricesOk] = useState<boolean | null>(null);
  const [slam, setSlam] = useState(0);

  useEffect(() => {
    fetch(`${API}/prices`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => {
        const map: PriceMap = {};
        for (const p of d.prices || [])
          map[p.name] = { chaos: p.chaos_value ?? null, divine: p.divine_value ?? null };
        setPrices(map);
        setPricesOk(true);
      })
      .catch(() => setPricesOk(false));
  }, []);

  useEffect(() => {
    setItem(newBase(base));
    setLedger([]);
    setPast([]);
    setLog(null);
  }, [base]);

  // PoE2's feed is divine-denominated (divine_value set, chaos_value NULL); use it directly, and
  // only fall back to converting a chaos price via the Divine Orb rate (PoE1-style feeds).
  const divineInChaos = prices["Divine Orb"]?.chaos ?? null;
  function orbDiv(orb: OrbDef): number | null {
    const p = orb.priceName ? prices[orb.priceName] : null;
    if (!p) return null;
    if (p.divine != null) return p.divine;
    if (p.chaos != null && divineInChaos && divineInChaos > 0) return p.chaos / divineInChaos;
    return null;
  }

  function onOrb(orb: OrbDef) {
    if (!canApply(base, item, orb.id)) return;
    const res = applyOrb(base, item, orb.id, Math.random);
    if (!res.ok) {
      setLog({ text: res.reason, ok: false });
      return;
    }
    setPast((p) => [...p.slice(-49), { item, ledger }]);
    setItem(res.item);
    setLedger((l) => [...l, { label: orb.label, div: orbDiv(orb) }]);
    setLog({ text: res.log, ok: true });
    setSlam((s) => s + 1);
  }

  function undo() {
    const prev = past[past.length - 1];
    if (!prev) return;
    setPast((p) => p.slice(0, -1));
    setItem(prev.item);
    setLedger(prev.ledger);
    setLog(null);
  }

  function reset() {
    setItem(newBase(base));
    setLedger([]);
    setPast([]);
    setLog(null);
  }

  const prefixes = item.mods.filter((m) => m.affix === "prefix");
  const suffixes = item.mods.filter((m) => m.affix === "suffix");
  const cap = CAP[item.rarity];

  const totalDiv = ledger.reduce((s, e) => s + (e.div ?? 0), 0);
  const unpricedCount = ledger.filter((e) => e.div == null).length;

  return (
    <section className="craft-section">
      <h2>Bancada — treine o fluxo</h2>
      <p className="meta">Aplique orbs e veja o item evoluir, com o custo somado ao vivo.</p>

      <div className="base-picker">
        {BASES.map((b) => (
          <button
            key={b.id}
            className={`base-chip ${b.id === baseId ? "active" : ""}`}
            onClick={() => setBaseId(b.id)}
          >
            {b.name}
          </button>
        ))}
      </div>

      <div className="bench">
        <div className="altar" data-rarity={item.rarity}>
          {slam > 0 && <span className="altar-flash" key={slam} aria-hidden="true" />}
          <div>
            <div className="item-base">{item.name}</div>
            <div className="item-ilvl">
              {item.category} · ilvl {item.itemLevel} · {item.rarity}
            </div>
          </div>
          <div className="affix-divider" />
          {item.mods.length === 0 ? (
            <div className="affix-empty">
              Item base, sem modificadores. Comece com Transmutation (vira Magic) ou Alchemy
              (vira Rare direto).
            </div>
          ) : (
            <div className="affix-list">
              {prefixes.map((m, i) => (
                <div className="affix" key={`p${i}`}>
                  <span className="kind">prefix</span>
                  {m.text}
                </div>
              ))}
              {suffixes.map((m, i) => (
                <div className="affix" key={`s${i}`}>
                  <span className="kind">suffix</span>
                  {m.text}
                </div>
              ))}
            </div>
          )}
          <div className="affix-caps">
            prefixos {prefixes.length}/{cap} · sufixos {suffixes.length}/{cap}
          </div>
        </div>

        <div className="bench-side">
          <div className="card">
            <h2>Orbs</h2>
            <div className="orb-palette">
              {ORBS.map((orb) => (
                <button
                  key={orb.id}
                  className="orb"
                  style={{ "--orb": orb.color } as React.CSSProperties}
                  disabled={!canApply(base, item, orb.id)}
                  onClick={() => onOrb(orb)}
                  aria-label={`${orb.label}: ${orb.blurb}`}
                  title={`${orb.blurb}${orb.priceName ? "" : " (sem preço)"}`}
                >
                  <span className="bead" />
                  <span className="orb-name">{orb.label}</span>
                </button>
              ))}
            </div>
            <p
              className={`bench-log ${log ? (log.ok ? "ok" : "no") : ""}`}
              role="status"
              aria-live="polite"
            >
              {log ? `${log.ok ? "OK" : "—"} ${log.text}` : " "}
            </p>
            <div className="bench-actions">
              <button className="btn-ghost" onClick={undo} disabled={past.length === 0}>
                ↶ Desfazer
              </button>
              <button className="btn-ghost" onClick={reset} disabled={ledger.length === 0}>
                ⟲ Recomeçar
              </button>
            </div>
          </div>

          <div className="card ledger">
            <h2>Custo (ao vivo)</h2>
            <div className="ledger-total">
              <span className="big">{`${fmt(totalDiv)} div`}</span>
              <span className="chaos">{unpricedCount > 0 ? `${unpricedCount} sem preço` : ""}</span>
            </div>
            {ledger.length === 0 ? (
              <p className="ledger-empty">Nenhum orb aplicado ainda.</p>
            ) : (
              <div className="ledger-rows">
                {ledger.map((e, i) => (
                  <div className="ledger-row" key={i}>
                    <span className="ln">{e.label}</span>
                    <span className="lc">{e.div != null ? `${fmt(e.div)} div` : "n/d"}</span>
                  </div>
                ))}
              </div>
            )}
            {pricesOk === false && (
              <p className="meta" style={{ marginTop: "0.6rem" }}>
                Preços indisponíveis agora — a bancada funciona, mas sem custo.
              </p>
            )}
          </div>
        </div>
      </div>

      <p className="honesty">
        As transições determinísticas (mudança de raridade, limites de afixo, regras dos orbs)
        seguem o PoE2 0.5 à risca. Já o pool de mods aqui é um subconjunto curado e ilustrativo —
        não os pesos reais da GGG — então use pra aprender o fluxo, não pra prever seu roll exato.
        O <strong>custo é real</strong> (preços vivos do poe.ninja).
      </p>
    </section>
  );
}

function CraftKnowledge() {
  const [cards, setCards] = useState<CraftCard[] | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch(`${API}/craft/knowledge`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => setCards(d.cards || []))
      .catch((e) => setErr(String(e)));
  }, []);

  return (
    <section className="craft-section">
      <h2>Conhecimento & fontes</h2>
      {err && <p className="meta">Não consegui carregar ({err}).</p>}
      {!cards && !err && <p className="meta">Carregando…</p>}
      {cards && cards.length === 0 && (
        <p className="meta">Nenhum conhecimento de craft ainda — chega na coleta diária.</p>
      )}
      {cards && cards.length > 0 && (
        <div className="craft-cards">
          {cards.map((c, i) => (
            <article className="card craft-card" key={i}>
              <p className="title">{c.title}</p>
              {c.snippet && <p className="snippet">{c.snippet}…</p>}
              <a href={c.source_url} target="_blank" rel="noreferrer">
                Abrir fonte ↗
              </a>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
