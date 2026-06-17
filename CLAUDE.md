# CLAUDE.md — Project Wraeclast

> Contexto persistente para o Claude Code. Leia isto inteiro antes de qualquer tarefa.
> Dono: Leonardo (`souzxxx`). Idioma de conversa: PT-BR casual. **Todo código, comentário, commit e doc técnico em inglês.**

---

## O que é este projeto

Agente/consultor pessoal de **Path of Exile 2** que se auto-atualiza diariamente. Coleta economia + meta + conhecimento da comunidade + os dados de conta do dono, cruza tudo, e expõe via chat (RAG) e site. Liga alvo: **0.5.0 Return of the Ancients** (última de Early Access antes do 1.0).

Pilares: (1) farm rankeado por lucro/hora, (2) diff de build vs meta, (3) chat que sabe a liga, (4) site diário + export Obsidian.

**Não é fine-tuning.** A "inteligência" é RAG: corpus cresce e é curado todo dia; na pergunta recupera relevante + perfil e responde.

---

## Stack (fixa — não trocar sem pedir)

| Camada | Tecnologia |
|---|---|
| Coleta agendada | Cloudflare Cron Triggers (Workers) |
| Banco | Neon Postgres + pgvector |
| Storage mídia | Cloudflare R2 |
| API backend | FastAPI (Python) |
| Site | Next.js + Vercel |
| LLM (chat + curadoria) | **GLM via z.ai**, OpenAI-compatible |
| Economia | poe.ninja (público) |
| Conta | API oficial GGG (OAuth 2.1 + PKCE) |
| Export | Markdown → vault Obsidian |

### Config do GLM (z.ai — confirmado)
- Endpoint OpenAI-compatible: `https://api.z.ai/api/openai/v1`
- SDK: cliente OpenAI padrão, só trocar `base_url` e `api_key`
- Env var: `GLM_API_KEY`
- Modelo de runtime: usar o tier que o dono assina (Coding Plan). Default sugerido p/ chat+curadoria: `glm-4.7-flash` (203K contexto, grátis) como fallback; modelo pago se configurado.
- **Nunca** hardcodar a key. Sempre via env.

```python
from openai import OpenAI
import os
client = OpenAI(api_key=os.environ["GLM_API_KEY"],
                base_url="https://api.z.ai/api/openai/v1")
```

---

## Fases (respeitar a ordem)

**Princípio: dados de conta NÃO são bloqueio. São uma escada de fallback.** O OAuth da GGG é o ideal mas opcional; o projeto funciona inteiro sem ele.

- **Fase 0 (foco AGORA, não depende de aprovação de ninguém):**
  - Economia: ninja price → Neon.
  - Comunidade: scraper → embeddings → Neon.
  - Curadoria GLM → farm rankeado.
  - **Dados de conta via ninja-build** (ver escada abaixo, nível 1): lê build/gear/passivas/skills do meu char no ninja. Já habilita o diff de build SEM OAuth.
  - Chat RAG + site + export Obsidian.
- **Fase 1 (complemento, sem depender de ninguém):** parser de **código PoB / clipboard** — universal, qualquer char/nível, instantâneo. Fallback quando o char não está no ladder do ninja.
- **Fase 2 (UPGRADE OPCIONAL, só se a GGG aprovar):** OAuth 2.1 24/7. Único ganho exclusivo: **currency do stash em tempo real** (patrimônio) e chars fora do ladder. Código desenhado pra plugar sem refazer nada.

### Escada de fallback p/ dados de conta (ordem de preferência)
1. **poe.ninja Builds** — automático, sem login complicado. PEGADINHA: char precisa atingir o nível mínimo do ladder da liga p/ aparecer via API. Ótimo p/ char de endgame; não serve p/ char baixo/teste. Dá build, gear, passivas, skills, e exporta **código PoB** ("Copy PoB code").
2. **Código PoB / clipboard** — manual mas universal. Funciona p/ qualquer char, offline. Custo: não é 24/7, eu colo quando quero atualizar.
3. **GGG OAuth** — ideal (24/7, currency do stash, qualquer char). Só se aprovado.

O que SÓ o OAuth dá: currency do stash em tempo real + chars fora do ladder. Build/gear/passivas/skills vêm do ninja ou PoB sem ele.

Aprovação OAuth GGG leva ~1-4 semanas (email a `oauth@grindinggear.com` — canal não 100% confirmado; se quicar, ver `pathofexile.com/developer/docs`). **Não bloquear NADA por causa disso.**

### Regras de OAuth da GGG (confirmadas na doc oficial)
- É **OAuth 2.1** (não 2.0), seguindo de perto a spec 2.1.
- **Confidential client** (backend com segredo): redirect URI DEVE ser HTTPS com **domínio registrado controlado por você**. **NÃO** aceitam IP nem `localhost`, nem em dev. Access token 28 dias, refresh 90 dias. Rate-limit individual por client.
- **Public client** (sem segredo; ex.: app desktop): é o modelo que o Path of Building usa (público + PKCE). Como o agente é pessoal e só lê os próprios dados, **avaliar usar public client** p/ evitar a exigência de domínio HTTPS.
- **Decisão pendente:** confidential vs public. Confidential = backend FastAPI guarda o segredo, precisa de domínio (`.vercel.app` serve). Public = mais leve, sem segredo, PKCE puro. Decidir antes de finalizar Fase 2.
- Tokens: implementar refresh (28d access / 90d refresh) no design do confidential.

---

## Regra de ouro das fontes

- Dados de *conta* (char/stash) → API oficial GGG.
- Dados de *economia/preço* → poe.ninja.
- Texto de comunidade (Reddit/fórum) → contexto **qualitativo**, NUNCA fonte primária de número.
- "Melhor farm" = lucro/hora **calculado** (drop × preço ninja × clear time), não texto solto.

---

## Estrutura do repo

```
project-wraeclast/
├─ CLAUDE.md                  # este arquivo
├─ collector/                 # roda no Cloudflare Cron
│  ├─ ninja_client.py         # economia (preços)
│  ├─ ninja_build_client.py   # build/gear/passivas do meu char (Fase 0, nível 1 da escada)
│  ├─ pob_parser.py           # parse de código PoB / clipboard (Fase 1, nível 2)
│  ├─ ggg_client.py           # OAuth 2.1 PKCE (Fase 2, nível 3 — opcional)
│  ├─ youtube_client.py       # YouTube Data API (fonte de farming) → knowledge
│  ├─ rss_client.py           # feeds RSS/Atom (opcional) → knowledge
│  ├─ add_knowledge.py        # curadoria manual: URL/texto → knowledge (endpoint /ingest)
│  ├─ ingest.py               # grava Neon + embeddings (Gemini)
│  ├─ curate.py               # GLM resume/rankeia → farm_strategy + markdown
│  └─ guides.py               # GLM gera guias completos → farm_guide
├─ api/                       # FastAPI
│  ├─ main.py
│  ├─ routes/{farm,build,chat}.py
│  └─ rag.py
├─ web/                       # Next.js (Vercel)
├─ db/migrations/             # SQL
├─ scripts/export_obsidian.py # gera markdown do vault
└─ docs/                      # spec + email OAuth
```

---

## Convenções

- Python: type hints sempre, `httpx` async p/ HTTP, `pydantic` p/ schemas, `ruff` p/ lint.
- Segredos só em env (`.env` local, secrets no Cloudflare/Vercel). Nunca commitar.
- Respeitar rate limits da GGG (headers `x-rate-limit`) e do ninja. Ver skill `poe2-data-collection`.
- Schema agnóstico a liga: sempre campo `league`, nada hardcoded a uma liga.
- Commits: conventional commits em inglês (`feat:`, `fix:`, `chore:`).
- Dono usa Mac, teclado US, VSCode. Direto ao ponto, profundidade > brevidade.

---

## Definition of done — Fase 0

- [ ] `collector` puxa ninja e grava `price_snapshot` no Neon.
- [ ] `ninja_build_client` lê meu char do ninja e grava `my_snapshot` (build/gear/passivas/skills).
- [ ] `youtube_client`/`rss_client`/`add_knowledge` coletam e `ingest` embeda em `knowledge_chunk`.
- [ ] `curate.py` gera `farm_strategy` rankeado por lucro/hora via GLM.
- [ ] API `/chat` responde com RAG (recupera chunks + GLM).
- [ ] API `/farm` retorna ranking atual.
- [ ] API `/build` retorna diff do meu char vs builds populares do ninja.
- [ ] Site Next mostra "estado da liga hoje" + farms + meu progresso de build.
- [ ] `export_obsidian.py` gera relatório markdown diário.
- [ ] Tudo roda via Cloudflare Cron 1x/dia sem intervenção.
