# Project Wraeclast — Agente/Consultor PoE2 Auto-Atualizável

> Spec de planejamento. Liga alvo: **0.5.0 Return of the Ancients** (live desde 29/mai/2026, última liga de Early Access antes do 1.0).
> Autor: Leonardo (`souzxxx`) + Claude. Status: planejamento, pré-bootstrap.

---

## 1. Visão

Um sistema que **todo dia** coleta o estado da liga (economia, builds meta, conhecimento da comunidade) e os **meus próprios dados de conta** (build, gear, currency), cruza tudo, e me deixa:

1. **Perguntar** qualquer coisa da liga e receber resposta fundamentada em dados atuais (chat RAG).
2. Ver **ranking de farm por lucro/hora** ao vivo, não achismo.
3. Receber **diff da minha build vs a meta** (relevante com as ~200 gems novas da 0.5.0).
4. Ter um **site auto-atualizado** + **relatório diário no Obsidian** com estratégias, prints, alertas de craft.

O "mega cérebro" não é o modelo aprendendo (os pesos não mudam). É o **corpus crescente e curado** num índice (RAG): todo dia ingere material novo, embeda, e na hora da pergunta recupera o relevante + meu perfil e responde.

---

## 2. Decisões de arquitetura (e porquê)

| Camada | Escolha | Porquê |
|---|---|---|
| Coleta agendada | **Cloudflare Cron Triggers** | Grátis, confiável, não dorme (Render free dorme). Igual stack do Bip. |
| Curadoria inteligente | **Claude Code Routine** (1x/dia) | Roda script no repo + interpreta resultado e escreve resumo. Não precisa Mac ligado. |
| Banco (fonte da verdade) | **Neon Postgres + pgvector** | SQL de verdade p/ lucro/hora histórico e diff de build. pgvector evita 2º serviço. Não pausa por inatividade. |
| Storage de mídia | **Cloudflare R2** | Prints/snapshots; egress grátis. |
| Site | **Next.js + Vercel** | Já domino; lê do Neon. |
| Leitura humana | **Export Markdown → Obsidian** | Vault versionado, navegável; gerado a partir do Neon. |
| Chat LLM | **Claude API** (análise pesada) + **Groq/Llama 3.3** (chat barato) | Custo controlado; Groq free no chat trivial, Claude no julgamento. |

**Regra de ouro de fontes:** dados de *conta* (char/stash) → API oficial GGG (OAuth). Dados de *economia/preço* → poe.ninja. Texto de comunidade (Reddit/fórum) → contexto qualitativo, **nunca** fonte primária de número.

---

## 3. Realidade do acesso à conta (gargalo de cronograma)

- API oficial GGG **já tem endpoints PoE2** (`/character/poe2`, stash). PoB importa via **OAuth 2.1 + PKCE**.
- **OAuth não é self-service:** registro via email `oauth@grindinggear.com` (canal **não 100% confirmado** — veio de fonte secundária; se quicar, conferir `pathofexile.com/developer/docs`, pode ser formulário). Aprovação ~**1–4 semanas**.
- Até aprovar: **parser de clipboard** (copio item/char no jogo, colo, o agente lê).
- GGG avisa: APIs que retornam *info de jogo* PoE2 ainda são limitadas → preço vem do ninja.

### Regras de OAuth confirmadas na doc oficial (importante)
- É **OAuth 2.1**, não 2.0.
- **Confidential client** (backend com segredo, ex.: FastAPI): redirect URI **obrigatoriamente HTTPS com domínio registrado controlado por mim**. **Não aceitam IP nem localhost, nem em desenvolvimento.** O `.vercel.app` grátis serve (é HTTPS + domínio). Access token dura 28 dias, refresh 90 dias.
- **Public client** (sem segredo armazenado, ex.: app desktop — modelo do Path of Building): público + PKCE, sem exigência de domínio HTTPS. Como o agente é pessoal e só lê meus dados, **é candidato forte** p/ simplificar.
- **DECISÃO PENDENTE antes da Fase 2:** confidential (precisa domínio, guarda segredo no backend) vs public (mais leve, PKCE puro). Isso muda o conteúdo do registro.

### Fases (escada de fallback — dados de conta NÃO são bloqueio)

- **Fase 0 — dia 1, não depende de aprovação de ninguém:** ninja (preço) + **ninja-build** (meu char) + scraper comunidade → Neon → site + chat RAG + **diff de build**. Entrega farm/hora, conhecimento, site diário E o diff de build, tudo sem OAuth.
- **Fase 1 — complemento:** parser de **código PoB / clipboard** — universal, qualquer char/nível, instantâneo. Fallback quando char não está no ladder do ninja.
- **Fase 2 — UPGRADE OPCIONAL (só se a GGG aprovar):** OAuth 2.1 24/7. Ganho exclusivo: **currency do stash** (patrimônio) + chars fora do ladder. Pluga sem refazer.

### Escada de fallback p/ dados de conta (preferência)
1. **poe.ninja Builds** — automático. Mostra equipamento, passivas, skill gems e stats simulados via PoB. Exporta "Copy PoB code". **Pegadinha:** char precisa atingir nível mínimo do ladder da liga p/ aparecer via API (usa a ladder API da GGG). Serve p/ endgame, não p/ char baixo/teste.
2. **Código PoB / clipboard** — manual, universal, offline, qualquer char. Custo: não é 24/7.
3. **GGG OAuth 2.1** — ideal (24/7, currency do stash, qualquer char). Opcional.

**Só o OAuth dá:** currency do stash em tempo real + chars fora do ladder. Build/gear/passivas/skills vêm do ninja ou PoB sem ele. Validação: já existe MCP server open-source de PoE2 que lê build do char direto do ninja (perfil público) sem OAuth — abordagem comprovada.

**Ação opcional:** disparar email de registro OAuth (rascunho pronto). Não bloqueia nada; é só pra destravar a Fase 2 se vier.

---

## 4. Orquestração: híbrido recomendado

- **Cloudflare Cron** faz a **coleta bruta** (confiável, grátis): roda scraper + puxa ninja + grava no Neon. Sem inteligência aqui.
- **Claude Code Routine** 1x/dia faz a **curadoria inteligente** sobre os dados já coletados: "leia o coletado, identifique as 3 estratégias de farm que ganharam tração hoje, escreva o resumo em markdown, commita no repo". Gera o relatório do Obsidian.

Notas de plataforma (research preview):
- Routines rodam na **nuvem da Anthropic**, **sem acesso a arquivos locais** — o scraper precisa ser **código no repo** (script Python fazendo HTTP), não "Claude navegando".
- Cap incluído: ~15 runs/dia/conta; consome do mesmo limite da assinatura. 1 run/madrugada sobra.
- Push só em branches `claude/` por padrão → reviso antes de mergear.
- Alternativa mais robusta p/ credenciais: **Claude Managed Agents** (schedule + vault de env vars + browser), beta na Claude Platform — bom p/ guardar token OAuth com segurança na Fase 2.

---

## 5. Schema inicial do Neon (rascunho)

```sql
-- Economia (snapshot diário, do ninja)
CREATE TABLE price_snapshot (
  id BIGSERIAL PRIMARY KEY,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  league TEXT NOT NULL,
  item_type TEXT NOT NULL,          -- currency | unique | base | gem
  name TEXT NOT NULL,
  chaos_value NUMERIC,
  divine_value NUMERIC,
  listing_count INT
);

-- Estratégias de farm (curado pela routine)
CREATE TABLE farm_strategy (
  id BIGSERIAL PRIMARY KEY,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  league TEXT NOT NULL,
  name TEXT NOT NULL,
  est_profit_per_hour NUMERIC,      -- calculado: drop x preço x clear time
  investment_required NUMERIC,
  risk TEXT,                         -- low | med | high
  summary TEXT,                      -- prosa curada
  sources JSONB                      -- links comunidade
);

-- Meu perfil (clipboard na F1, OAuth na F2)
CREATE TABLE my_snapshot (
  id BIGSERIAL PRIMARY KEY,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  character_name TEXT,
  class TEXT,
  level INT,
  total_currency_chaos NUMERIC,     -- patrimônio normalizado
  gear JSONB,
  gems JSONB,
  passive_tree JSONB
);

-- Conhecimento textual p/ RAG
CREATE TABLE knowledge_chunk (
  id BIGSERIAL PRIMARY KEY,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_url TEXT,
  title TEXT,
  content TEXT,
  embedding VECTOR(1536)            -- pgvector
);
```

---

## 6. Os 4 pilares (interdependentes)

```
            ┌─────────────────────────────┐
 CRON ─────►│ Coleta: ninja + GGG + scraper│
            └──────────────┬───────────────┘
                           ▼
            ┌─────────────────────────────┐
            │ Neon (Postgres + pgvector)   │ ◄── fonte da verdade
            └──────────────┬───────────────┘
     ┌──────────┬──────────┴────────┬──────────┐
     ▼          ▼                   ▼          ▼
 [1]FARM    [2]BUILD            [3]CHAT     [4]SITE
 lucro/h    diff vs meta        RAG+perfil  Next + Obsidian
```

1. **Farm** — cruza drop × preço ninja × clear time → ranking lucro/hora.
2. **Build** — meu perfil × builds populares do ninja → o que trocar (foco nas 200 gems novas).
3. **Chat** — endpoint FastAPI monta contexto (RAG + perfil) → LLM responde.
4. **Site** — Next lê Neon: "estado da liga hoje", farms rankeados, progresso, alertas de craft. Job gera markdown gêmeo p/ Obsidian.

---

## 7. Estrutura de pastas proposta

```
project-wraeclast/
├─ collector/                 # roda no Cloudflare Cron / Routine
│  ├─ ninja_client.py
│  ├─ ggg_client.py           # OAuth PKCE (F2) + clipboard parser (F1)
│  ├─ community_scraper.py
│  └─ ingest.py               # grava Neon + embeddings
├─ api/                       # FastAPI
│  ├─ main.py
│  ├─ routes/{farm,build,chat}.py
│  └─ rag.py
├─ web/                       # Next.js (Vercel)
├─ routines/
│  └─ daily_curation.md       # def da Claude Code Routine
├─ db/migrations/
└─ docs/                      # este spec + email OAuth
```

---

## 8. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Aprovação OAuth demora 1–4 sem | Fase 0 não depende dela; clipboard na F1. |
| Rate limit API GGG | Cache + RateLimiter (httpx async), respeitar headers `x-rate-limit`. |
| Scraping ruidoso | Filtrar por upvotes/recência; tratar como qualitativo, não numérico. |
| Custo de token (Claude) | Híbrido Groq/Claude; routine só na curadoria. |
| Preview instável (Routines) | Cloudflare Cron como base confiável; routine é camada extra. |
| Meta muda a cada liga | Schema agnóstico a liga (campo `league`); fontes dinâmicas. |

---

## 9. Próximos passos

- [ ] Disparar email de registro OAuth p/ GGG (hoje).
- [ ] Bootstrap Fase 0 com Claude Code (collector ninja + scraper + Neon + chat RAG).
- [ ] Subir site mínimo Next no Vercel lendo Neon.
- [ ] Implementar export markdown → Obsidian.
- [ ] (Pós-registro) Clipboard parser → diff de build.
- [ ] (Pós-aprovação) Trocar p/ OAuth 24/7.
