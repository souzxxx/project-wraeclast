# Skill: poe2-data-collection

Guia de coleta de dados de Path of Exile 2. Consulte ANTES de escrever qualquer cliente de API (ninja, GGG) ou scraper. Encoda armadilhas que não estão na memória do modelo e evitam retrabalho.

## Quando usar
Sempre que a tarefa envolver: puxar economia do poe.ninja, acessar a API oficial da GGG (char/stash), fazer scraping de Reddit/fórum PoE, ou calcular lucro/hora de farm.

---

## 1. poe.ninja (economia)

- API pública, sem auth. Base: `https://poe.ninja/api/data/`.
- Há endpoints separados p/ currency overview e item overview. Sempre passar o parâmetro de **league** (ex.: a liga atual da 0.5.0) — nunca hardcodar; ler de config/env.
- **PoE2 vs PoE1:** confirmar que a rota usada é a da economia de PoE2, não PoE1. A estrutura de resposta pode diferir. Se em dúvida, fazer um GET exploratório e logar o JSON antes de modelar.
- Cachear respostas (TTL de horas). É snapshot diário; não martelar o endpoint.
- Persistir em `price_snapshot` normalizando para um valor base (ex.: chaos ou divine equivalente) p/ permitir histórico comparável.
- **Sempre** defensivo: campos podem faltar; usar `.get()` e validar com pydantic.

> **Nota de campo (2026-06-17, descoberta no bootstrap):** O site poe.ninja PoE2 migrou para Astro SPA; os paths clássicos (`/api/data/currencyoverview`, `/poe2/api/data/getindexstate`) retornam 404 publicamente. **Armadilha confirmada:** ao raspar a página `/poe2/economy/...` o JSON embutido trouxe ligas como "Mirage" com `passiveTree: PassiveTree-3.28` / `atlasTree: AtlasTree-3.28` — versionamento **3.x = PoE1**, ou seja eram dados de **PoE1**, não PoE2. **"Mirage" é liga de PoE1, NÃO sirva como liga PoE2.** A liga PoE2 é a 0.5.0 (spec: "Return of the Ancients"); o endpoint de dados e o slug exato da liga precisam ser confirmados com um GET exploratório no ambiente de deploy (`python -m collector.ninja_client explore`). Por isso `POE2_LEAGUE`, `NINJA_BASE_URL` e o template de endpoint são **config-driven via env**, nunca hardcoded — sempre validar que a resposta é PoE2 (versão 0.x), não PoE1.

## 2. API oficial GGG (conta — Fase 2, OPCIONAL)

**Antes de implementar isto, lembre: dados de conta têm escada de fallback (ver CLAUDE.md). O ninja-build (seção 2b) é a fonte primária e NÃO precisa de OAuth. OAuth é upgrade opcional.**

- Docs: `https://www.pathofexile.com/developer/docs/reference`.
- PoE2 tem endpoints próprios (`/character/poe2`, stash). APIs de *info de jogo* PoE2 ainda são limitadas — não assumir paridade com PoE1.
- **OAuth 2.1 + PKCE** (Authorization Code), scopes `account:characters`, `account:stashes`. Mesmo fluxo do Path of Building. NOTA: confidential client exige redirect HTTPS com domínio registrado (não aceita localhost/IP); public client (PKCE puro) não exige — decisão registrada no CLAUDE.md.
- **Rate limit:** ler e respeitar headers `x-rate-limit-*` em TODA resposta. Implementar `RateLimiter` async que pausa conforme os headers. Exceder = ban temporário.
- **User-Agent obrigatório e descritivo** (ex.: `Project-Wraeclast/0.1 (contact)`), senão a GGG bloqueia.
- Token expira: implementar refresh e cache do token com checagem de expiração antes de cada chamada.
- **Fase 1 (fallback universal):** parser de **código PoB / clipboard**. O dono copia char/item do jogo OU exporta o "Copy PoB code" do ninja, cola, e o parser extrai. Funciona p/ qualquer char/nível, offline. Implementar como `pob_parser.py`.

## 2b. poe.ninja Builds (conta — FONTE PRIMÁRIA, Fase 0, SEM auth)

Esta é a forma preferida de ler os dados de build do dono, e **não exige OAuth nem login complicado**.

- O ninja tem seção de Builds PoE2 (`poe.ninja/poe2/builds/`). Cada char detalhado mostra equipamento, passivas, skill gems e stats simulados via Path of Building.
- O dono loga 1x no ninja p/ linkar o perfil; depois o char fica acessível.
- **PEGADINHA crítica:** o char só aparece via API se atingir o **nível mínimo do ladder** da liga atual (o ninja usa a ladder API da GGG). Funciona p/ char de endgame; NÃO funciona p/ char baixo/teste → nesse caso cair pro `pob_parser` (seção 2/Fase 1).
- Implementar `ninja_build_client.py`: buscar o char do dono, extrair gear/passivas/skills, gravar em `my_snapshot`.
- Também é possível obter o **código PoB** do char pelo ninja e parsear com o mesmo `pob_parser` — reuso de código.
- Fazer GET exploratório e logar o JSON antes de modelar (estrutura PoE2 pode diferir de PoE1).
- **Limite:** o ninja NÃO expõe currency do stash. Patrimônio em tempo real só via OAuth (Fase 2). Build/gear/passivas/skills: ok sem OAuth.


## 3. Scraper de comunidade (Reddit / fórum)

- Reddit: preferir a API oficial (`https://oauth.reddit.com`) com app registrado, ou o JSON público (`.json` no fim da URL) p/ leitura leve. Respeitar User-Agent e rate limit.
- Filtrar por **upvotes mínimos + recência** (ex.: posts da última semana com score relevante). Lixo de baixo karma não entra.
- Tratar todo texto coletado como **qualitativo**: vira `knowledge_chunk` p/ RAG, dá *contexto* ("por que tal farm é bom"), nunca número de preço/drop.
- Deduplicar por URL antes de embedar.
- Não fazer scraping agressivo: 1 passada/dia na janela noturna basta.

## 4. Cálculo de lucro/hora (o coração do pilar Farm)

Fórmula conceitual por estratégia:
```
profit_per_hour = (drops_esperados_por_mapa × preço_unitário_ninja − custo_entrada_por_mapa)
                  ÷ tempo_de_clear_em_horas
```
- `preço_unitário_ninja`: do `price_snapshot` mais recente.
- `drops_esperados` e `tempo_de_clear`: vêm de conhecimento curado (comunidade) — aproximações, marcar como estimativa.
- Sempre gravar `est_profit_per_hour` + `risk` + `investment_required` + `sources` em `farm_strategy`.
- Deixar claro na UI/resposta que é **estimativa**, não garantia.

## 5. Curadoria com GLM (curate.py)

- Pegar os `knowledge_chunk` novos do dia + `price_snapshot` atual.
- Prompt ao GLM: identificar as N estratégias de farm com mais tração hoje, estimar lucro/hora cruzando com os preços, escrever resumo em prosa.
- Pedir saída em **JSON estrito** (sem markdown, sem preâmbulo) p/ parsear e gravar em `farm_strategy`. Validar com try/except + pydantic.
- Gerar também um markdown human-readable p/ o export Obsidian.

## Checklist antes de dar PR
- [ ] Nenhuma key/segredo hardcoded.
- [ ] Rate limits respeitados (headers GGG, TTL ninja).
- [ ] User-Agent descritivo em toda request externa.
- [ ] `league` parametrizado, nada hardcoded.
- [ ] Respostas externas validadas defensivamente (campos podem faltar).
- [ ] Texto de comunidade tratado como qualitativo.
