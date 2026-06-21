"use client";

import { useEffect, useMemo, useState } from "react";
import { API } from "../lib";
import { BASES, ORBS, getBase, type OrbDef } from "./data";
import { applyOrb, canApply, newBase, type Item } from "./engine";

type PriceMap = Record<string, { chaos: number | null; divine: number | null }>;
type LedgerEntry = { label: string; chaos: number | null };
type CraftCard = { source_url: string; title: string; snippet: string };

const CAP: Record<Item["rarity"], number> = { normal: 0, magic: 1, rare: 3 };

function fmt(n: number): string {
  if (n >= 100) return String(Math.round(n));
  if (n >= 10) return n.toFixed(1);
  return n.toFixed(2);
}

export default function CraftPage() {
  const [baseId, setBaseId] = useState(BASES[0].id);
  const base = useMemo(() => getBase(baseId), [baseId]);
  const [item, setItem] = useState<Item>(() => newBase(getBase(BASES[0].id)));
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [past, setPast] = useState<{ item: Item; ledger: LedgerEntry[] }[]>([]);
  const [log, setLog] = useState<{ text: string; ok: boolean } | null>(null);
  const [prices, setPrices] = useState<PriceMap>({});
  const [pricesOk, setPricesOk] = useState<boolean | null>(null);
  const [slam, setSlam] = useState(0);

  // live currency prices for the cost ledger
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

  // reset the bench when the base changes
  useEffect(() => {
    setItem(newBase(base));
    setLedger([]);
    setPast([]);
    setLog(null);
  }, [base]);

  function priceChaos(orb: OrbDef): number | null {
    if (!orb.priceName) return null;
    return prices[orb.priceName]?.chaos ?? null;
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
    setLedger((l) => [...l, { label: orb.label, chaos: priceChaos(orb) }]);
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

  const totalChaos = ledger.reduce((s, e) => s + (e.chaos ?? 0), 0);
  const divineChaos = prices["Divine Orb"]?.chaos ?? null;
  const totalDiv = divineChaos && divineChaos > 0 ? totalChaos / divineChaos : null;

  return (
    <main>
      <h1>Bancada de Craft</h1>
      <p className="sub">
        Aplique orbs e veja o item evoluir — o custo é somado em tempo real com os preços do
        poe.ninja. Aprenda o fluxo do craft do PoE2 antes de gastar divine de verdade.
      </p>

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
        {/* the item altar */}
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

        {/* orbs + ledger */}
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
              {log ? `${log.ok ? "OK" : "—"} ${log.text}` : " "}
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
              <span className="big">{totalDiv != null ? `${fmt(totalDiv)} div` : "—"}</span>
              <span className="chaos">{fmt(totalChaos)} chaos</span>
            </div>
            {ledger.length === 0 ? (
              <p className="ledger-empty">Nenhum orb aplicado ainda.</p>
            ) : (
              <div className="ledger-rows">
                {ledger.map((e, i) => (
                  <div className="ledger-row" key={i}>
                    <span className="ln">{e.label}</span>
                    <span className="lc">{e.chaos != null ? `${fmt(e.chaos)} c` : "n/d"}</span>
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

      <h2 style={{ marginTop: "3rem" }}>Conhecimento de craft</h2>
      <CraftGuides />
    </main>
  );
}

function CraftGuides() {
  const [cards, setCards] = useState<CraftCard[] | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    fetch(`${API}/craft/knowledge`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => setCards(d.cards || []))
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) return <p className="meta">Não consegui carregar os guias ({err}).</p>;
  if (!cards) return <p className="meta">Carregando…</p>;
  if (cards.length === 0)
    return <p className="meta">Nenhum conhecimento de craft ainda — chega na coleta diária.</p>;

  return (
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
  );
}
