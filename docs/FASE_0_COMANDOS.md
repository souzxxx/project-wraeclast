# Fase 0 — Sequência de comandos pro Claude Code

> Cola um por vez, na ordem. Revisa o resultado antes de ir pro próximo.
> O Claude Code lê o `CLAUDE.md` e a skill `poe2-data-collection` sozinho — não precisa reexplicar.

---

## Setup inicial (uma vez)

Antes de abrir o Claude Code:
1. `git init` no diretório do projeto e coloca o `CLAUDE.md` na raiz.
2. Garante que a pasta `.claude/skills/poe2-data-collection/SKILL.md` está no lugar.
3. Cria um `.env` (e `.env.example`) com: `GLM_API_KEY`, `NEON_DATABASE_URL`. Adiciona `.env` no `.gitignore`.
4. Se for usar GLM no próprio Claude Code como motor, configura o endpoint z.ai nas settings dele.

---

## Comando 1 — Scaffold

```
Leia o CLAUDE.md. Crie a estrutura de pastas do repo exatamente como especificada,
com arquivos vazios/stub e um pyproject.toml usando httpx, pydantic, openai, psycopg
(ou asyncpg), e ruff. Crie .env.example. Não implemente lógica ainda, só o esqueleto.
```

## Comando 2 — Banco (Neon)

```
Crie a primeira migration SQL em db/migrations/ com as tabelas price_snapshot,
farm_strategy, my_snapshot e knowledge_chunk (com coluna embedding via pgvector).
Habilite a extensão pgvector. Crie um módulo db/connection.py que conecta no Neon
via NEON_DATABASE_URL. Teste a conexão.
```

## Comando 3 — Collector do ninja

```
Implemente collector/ninja_client.py seguindo a skill poe2-data-collection.
Puxe a economia de PoE2 da liga atual, normalize e grave em price_snapshot.
Faça um GET exploratório primeiro e logue o JSON pra confirmar a estrutura
antes de modelar. Adicione cache com TTL.
```

## Comando 4 — Dados de conta via ninja-build (sem OAuth!)

```
Implemente collector/ninja_build_client.py seguindo a seção 2b da skill
poe2-data-collection. Leia o meu personagem do poe.ninja (build, gear, passivas,
skills) e grave em my_snapshot. Faça GET exploratório e logue o JSON antes de modelar.
Trate o caso do char não estar no ladder (fallback documentado). Implemente também
collector/pob_parser.py como fallback universal (parse de código PoB / clipboard).
```

## Comando 5 — Scraper de comunidade

```
Implemente collector/community_scraper.py seguindo a skill. Colete posts recentes
e relevantes (filtro por upvotes + recência) do subreddit de PoE2 e/ou fórum oficial.
Deduplique por URL. Em collector/ingest.py, embede o texto e grave em knowledge_chunk.
Trate tudo como qualitativo.
```

## Comando 6 — Curadoria com GLM

```
Implemente collector/curate.py. Pegue knowledge_chunk novos + price_snapshot atual,
chame o GLM (z.ai, OpenAI-compatible, ver CLAUDE.md) pedindo as principais estratégias
de farm do dia com lucro/hora estimado. Exija saída JSON estrito, parseie com pydantic,
grave em farm_strategy. Gere também um markdown human-readable.
```

## Comando 7 — API (chat RAG + farm + build)

```
Implemente a FastAPI em api/. Rota /farm retorna o ranking de farm_strategy.
Rota /build retorna o diff do meu char (my_snapshot) vs builds populares do ninja.
Rota /chat recebe pergunta, faz retrieval semântico em knowledge_chunk (pgvector),
monta contexto + responde via GLM. api/rag.py centraliza o retrieval. Teste local.
```

## Comando 8 — Site (Next.js)

```
Crie o web/ em Next.js lendo a API. Página principal: "estado da liga hoje",
ranking de farms por lucro/hora, meu progresso de build (diff), e um chat plugado
em /chat. Design limpo e funcional. Prepare pra deploy na Vercel.
```

## Comando 9 — Export Obsidian

```
Implemente scripts/export_obsidian.py que gera um relatório markdown diário
(estado da liga, top farms, resumos curados, meu progresso) num formato bonito
pra vault Obsidian.
```

## Comando 10 — Agendamento (Cloudflare Cron)

```
Configure o collector pra rodar 1x/dia via Cloudflare Cron Trigger: ninja_client →
ninja_build_client → community_scraper → ingest → curate → export_obsidian, em
sequência, com tratamento de erro e log. Documente como fazer deploy no Cloudflare.
```

---

## Depois da Fase 0
- Fase 1 já parcialmente feita (pob_parser no comando 4). Refinar o parse de clipboard se precisar.
- Fase 2 (OPCIONAL, só se a GGG aprovar): implementar ggg_client.py com OAuth 2.1 PKCE
  pra ganhar currency do stash 24/7 + chars fora do ladder. Plugar sem refazer o resto.

## Lembrete
- O email da GGG é OPCIONAL (rascunho pronto) — só destrava a Fase 2 (currency do stash 24/7). Nada na Fase 0 ou 1 depende dele. Manda quando quiser.
- Revisa cada PR antes de mergear (CC só pusha em branches `claude/` por padrão).
