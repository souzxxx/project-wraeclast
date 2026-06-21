"use client";

import { useEffect, useRef, useState } from "react";
import { API, TOKEN_KEY } from "../lib";

type Source = { url: string; title: string };
type Msg = { role: "user" | "assistant"; content: string; sources?: Source[] };

export default function ChatPage() {
  const [token, setToken] = useState("");
  const [pwInput, setPwInput] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setToken(localStorage.getItem(TOKEN_KEY) || "");
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

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
    setMessages([]);
  }

  async function send() {
    const question = input.trim();
    if (!question || loading) return;
    // send only the recent window (server replays the last few; this caps payload + matches the
    // server's history bound so a long thread never trips request validation).
    const history = messages.slice(-12).map((m) => ({ role: m.role, content: m.content }));
    setMessages((m) => [...m, { role: "user", content: question }]);
    setInput("");
    setLoading(true);
    setErr("");
    try {
      const r = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "content-type": "application/json", "x-access-token": token },
        body: JSON.stringify({ question, history }),
      });
      if (r.status === 401) {
        forget();
        throw new Error("Senha inválida — entre de novo.");
      }
      if (r.status === 503) throw new Error("Chat ainda não configurado no servidor.");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      if (!d || typeof d.answer !== "string")
        throw new Error("Resposta vazia do servidor.");
      setMessages((m) => [...m, { role: "assistant", content: d.answer, sources: d.sources }]);
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e));
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <main>
        <h1>Oráculo</h1>
        <p className="sub">
          O chat é protegido por senha — ele gasta tokens de LLM, então fica fechado pra evitar
          abuso.
        </p>
        <div className="card" style={{ maxWidth: 420 }}>
          <input
            type="password"
            value={pwInput}
            onChange={(e) => setPwInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && saveToken()}
            placeholder="Senha de acesso"
          />
          <button onClick={saveToken}>Desbloquear</button>
          {err && <p className="err">{err}</p>}
        </div>
      </main>
    );
  }

  return (
    <main>
      <h1>Oráculo</h1>
      <p className="sub">
        Pergunte sobre a liga — farms, preços, craft, sua build. Ele lembra do papo e responde a
        partir do conhecimento curado + seu perfil.
      </p>

      <div className="thread">
        {messages.length === 0 && (
          <div className="bubble assistant">
            <div className="who">Oráculo</div>
            Pergunte algo como “qual o melhor farm pra mid-budget agora?” ou “como faço um +3 spell
            skills wand barato?”.
          </div>
        )}
        {messages.map((m, i) => (
          <div className={`bubble ${m.role}`} key={i}>
            <div className="who">{m.role === "user" ? "Você" : "Oráculo"}</div>
            {m.content}
            {m.sources && m.sources.length > 0 && (
              <div className="sources">
                <p className="meta">Fontes:</p>
                {m.sources.map((s, j) => (
                  <a key={j} href={s.url} target="_blank" rel="noreferrer">
                    {s.title || s.url}
                  </a>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="bubble assistant thinking">
            <div className="who">Oráculo</div>
            Consultando os ecos de Wraeclast…
          </div>
        )}
        <div ref={endRef} />
      </div>

      {err && <p className="err">{err}</p>}

      <div className="composer">
        <div className="composer-row">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="Escreva sua pergunta… (Enter envia, Shift+Enter quebra linha)"
          />
          <button onClick={send} disabled={loading || !input.trim()}>
            {loading ? "…" : "Enviar"}
          </button>
        </div>
        <button
          className="btn-ghost"
          style={{ alignSelf: "flex-start" }}
          onClick={forget}
        >
          Esquecer senha
        </button>
      </div>

      <AddKnowledge />
    </main>
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
      setMsg("Desbloqueie o chat primeiro (mesma senha).");
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
    <details className="addknow">
      <summary>+ Alimentar o conhecimento</summary>
      <p className="meta">Cole um link (post, guia, vídeo) ou texto que valha a pena lembrar.</p>
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="https://… ou anote sua descoberta aqui"
      />
      <button onClick={add} disabled={loading}>
        {loading ? "Salvando…" : "Adicionar"}
      </button>
      {msg && <p className="meta">{msg}</p>}
    </details>
  );
}
