# Changelog — Conatus

Todas as modificações significativas no projeto.

## [Commit 4] `11835a5` — Simulação pausa a cada 100 ticks

**Arquivo:** `src/mundo.py`

- A simulação agora pausa com `[Enter para continuar...]` a cada 100 ticks
- Tanto modo LLM quanto modo sem LLM usam `pausa_a_cada=100`
- Antes: 50 ticks sem pausa (sem LLM) ou infinito sem pausa (com LLM)

## [Commit 3] `ae27850` — Personagens em JSON: elenco configurável

**Arquivos novos:**

### `personagens/` — 12 personagens em JSON

Cada arquivo contém: nome, arquetipo, idade, descricao, razao_innata,
local_inicial, controlado_por_llm, motivacoes, valores, medos.

| Personagem | Arquétipo | Razão | Local | Skill única |
|---|---|---|---|---|
| Maria | generoso | 0.60 | vila | liderança |
| João | prudente | 0.70 | vila | planejamento |
| Ana | ativo | 0.40 | planicie | caçador |
| Pedro | filósofo | 0.90 | montanha | pesquisador |
| Lúcia | medo | 0.50 | vila | furtividade |
| Tiago | **dominador** | 0.55 | vila | **ferreiro** |
| Helena | generoso | 0.65 | floresta | médico |
| Raul | prudente | 0.75 | vila | construtor |
| Clara | ativo | 0.45 | ruinas | atletismo |
| Otávio | filósofo | 0.85 | pantano | pesquisador |
| Sônia | medo | 0.55 | caverna | cautela |

### `elenco/` — 4 rosters

| Roster | Personagens | Uso |
|---|---|---|
| `default.json` | 5 originais (Maria, João, Ana, Pedro, Lúcia) | Compatibilidade |
| `todos.json` | Todos os 12 | Máximo de interações |
| `experimental.json` | 6 novos (Tiago, Helena, Raul, Clara, Otávio, Sônia) | Testar skills |
| `dupla.json` | 2 (Maria, Tiago) | Teste rápido |

**Arquivo modificado:** `src/mundo.py`

- `carregar_elenco(caminho)` — lê roster JSON, resolve caminhos, instancia `Personagem`
- `criar_simulacao_padrao()` agora aceita `elenco_path`
- `_criar_personagens_padrao()` — personagens hardcoded extraídos para função separada
- CLI: `--elenco` para selecionar roster, `--listar-personagens` para listar

**Como usar:**
```bash
python3 src/mundo.py --elenco elenco/todos.json
python3 src/mundo.py --elenco elenco/experimental.json --listar-personagens
```

## [Commit 2] `41272e7` — Razão vira Curiosidade e Pedidos Sociais

**Arquivo modificado:** `src/mundo.py`

### 1. Razão modula necessidades básicas (FASE 1)

- `razao_vs_paixao` reduz dinamicamente os limiares de fome e sede:
  ```
  limiar_fome  = max(0.20, 0.40 - razao × 0.15)
  limiar_sede  = max(0.20, 0.40 - razao × 0.15)
  ```
- Um sábio (razão 1.0) tolera até fome 0.25 antes de agir
- Um passional (razão 0.0) age já em 0.40
- **Filosofia:** Quanto maior a razão, maior a compreensão de que a
  privação momentânea é superada pela engenharia de longo prazo

### 2. Razão → Prioridade de engenharia (FASE 0)

- Se `razao > 0.5`: até `(razao - 0.5) × 0.5` de chance de pular
  necessidades básicas e ir direto para crafting experimental
- Prioridade: ferramentas (machado, picareta), construção
  (abrigo, cabana), processamento (metal, pranchas)
- 15% de "curiosidade inata" mesmo para personagens com baixa razão

### 3. Pedidos sociais (`_tentar_pedido`)

- Personagens com `razao >= 0.5` podem pedir ajuda a outros
- **Prioridade 1 — Ensino:** pede para aprender a skill que o outro
  domina e ele não. Escolhe a skill com maior gap.
- **Prioridade 2 — Crafting:** pede que o outro fabrique um item
  usando seus materiais, quando lhe falta a skill necessária.
- O ajudante aceita com `0.5 + relação × 0.2` de chance
- **Ambos ganham XP:** o aluno aprende, o professor consolida

### 4. Observação dá XP

- Observadores de crafting ganham `max(1, resultado.xp_ganho // 3)` XP
- Ativa aprendizado vicário (ver outro fazer ensina)

## [Commit 1] `09397f9` — Aprendizado emergente

**Arquivos modificados:** `src/habilidades.py`, `src/mundo.py`

### Habilidades (`habilidades.py`)

| Mudança | Antes | Depois | Efeito |
|---|---|---|---|
| `pode_ensinar` | nível ≥ 0.4 | nível ≥ 0.2 | Ensino começa mais cedo |
| Curva XP | × 1.5 por nível | × 1.3 por nível | Progressão mais suave |
| XP sucesso crafting | `xp_ganho` | `xp_ganho × 2` | Aprende mais rápido |
| XP falha parcial | `xp_ganho // 2` | `xp_ganho` | Aprendizado com erro |
| XP falha total | `xp_ganho // 4` | `xp_ganho // 2` | Aprendizado com erro |
| XP falha segura | `xp_ganho // 10` | `xp_ganho // 5` | Tenta sem medo |
| `listar_receitas_por_materiais()` | — | novo método | Ver receitas por materiais, ignora skill |

### Receitas de agricultura adicionadas

- `plantar` (agricultor 0.1): 1 colheita + 2 água → 4 colheita
- `adubar_solo` (agricultor 0.3): 2 colheita + 1 água + 2 grama → 6 colheita

### Sistema de perecibilidade (`TEMPOS_VALIDADE`, `Material.validade`)

- `Material` ganha `validade: int` (ticks até estragar, -1 = não perecível)
- `Inventario.tick_validade()` — decrementa validade, remove estragados
- `Inventario.esta_seco(nome)` — verifica se ainda está fresco
- Display mostra `✅ fresco`, `⏳ fresco`, `⚠️ estragando`
- Comida estragada reduz saúde do personagem

### Mundo (`mundo.py`)

| Mudança | Antes | Depois | Efeito |
|---|---|---|---|
| Crafting priority | 35% | 50% | Personagens craftam mais |
| Experimental crafts | — | tag `crafting_experimental` | Tentativas sem skill mínima |
| Bônus experimental XP | — | 1.5× XP | Incentiva experimentação |
| Sleep recovery | 0.08/tick | 0.10/tick | Recupera mais rápido |
| Wake threshold | 0.8 | 0.7 | Acorda mais cedo |
| Forced sleep | — | energia < 0.15 | Evita ciclo de exaustão |
| `_gerar_resumo_tick` | — | estação do ano + relações | Display mais rico |
| `_display_padrao` | — | diálogos + observações + relações | Display mais rico |

### Sleep melhorado

- Antes: energia < 0.3 → tenta dormir
- Agora: energia < 0.15 → **forçado a dormir** (não há escolha)
- Isso elimina o ciclo de exaustão onde o personagem ficava sem
  energia para craftar por não conseguir dormir o suficiente

## Commits anteriores (resumo)

| Hash | Mudança |
|---|---|
| `cdc7096` | Corrige conflito entre decisão LLM e sono automático |
| `cdee95c` | Mecânicas noturnas e exibição de relações |
| `b0b5c33` | Melhorias no prompt e decisão do LLM |
| `a20a1af` | Renomeia projeto para Conatus |
| `bd5f1ad` | Extrai modo interativo para `src/interface.py` |
| `67fcab3` | LLM controla apenas personagem marcado |
| `b2beb8f` | `argparse` com `--llm` para ativar LLM |
| `3c4bafe` | LLM síncrono no mesmo tick, sem pausas |
| `c0b24d8` | `--alternar N` para revezar LLM entre personagens |
| `fdcfa1f` | Expande mapa: Lago, Pântano, Ruínas |
| `23d621b` | Desenvolvimento emergente de locais (construções, níveis) |
| `f3df51b` | Clima afeta renovação de recursos |
| `7c52f05` | Estações do ano influenciam clima e eventos |
| `bda8a3b` | Prompts mais ricos para LLM (motivações, valores) |
