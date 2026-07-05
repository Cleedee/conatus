# AGENTS.md — Conatus

## Projeto

Simulação social emergente espinozista com múltiplos personagens interpretados por LLMs pequenos. O nome Conatus refere-se ao esforço fundamental de cada ser para perseverar e aumentar sua potência de agir (Ética de Spinoza). Cada interação é um "encontro" que afeta a potência de agir do personagem (adequação/dissolução).

## Stack

- **Python 3.10+** — sem frameworks, sem dependências externas
- **LLMs**: Ollama (padrão), llama.cpp, ou HTTP genérico
- Fallback para `MockLLM` (decisões rule-based) quando não há LLM disponível

## Estrutura

```
src/
├── personagem.py   # Personagem, Personalidade, Afetos, Memória, Conhecimento
├── encontros.py    # MotorEncontros, GeradorEncontros, EventoMundo
├── mapa.py         # Mapa, Local, pathfinding BFS, clima, estações
├── mundo.py        # Simulacao — orquestrador do tick loop, razão/curiosidade, pedidos
├── llm.py          # AgenteLLM, ConfigLLM, ProviderLLM
├── habilidades.py  # MotorCrafting, Habilidade, Inventario, Receitas (perecibilidade)
├── mercado.py      # Mercado, Troca, barganha
├── interface.py    # Modo interativo (REPL)
├── teste_rapido.py # Teste de conectividade Ollama
├── testar_ollama.py# Teste completo com Ollama
personagens/        # 12 personagens em arquivos JSON individuais
elenco/             # Rosters (listas de personagens para a simulação)
docs/
CHANGELOG.md        # Histórico de modificações
```

## Comandos

```bash
# Rodar simulação (sem LLM, pausa a cada 100 ticks)
python3 src/mundo.py

# Rodar com elenco específico
python3 src/mundo.py --elenco elenco/experimental.json
python3 src/mundo.py --elenco elenco/todos.json

# Listar personagens de um elenco
python3 src/mundo.py --elenco elenco/default.json --listar-personagens

# Rodar simulação com Ollama
python3 src/testar_ollama.py

# Modo interativo (REPL)
python3 src/mundo.py --interativo

# Com LLM ativado
python3 src/mundo.py --llm --model qwen2.5:0.5b

# Testar módulo individual
python3 src/mapa.py
python3 src/personagem.py
python3 src/encontros.py
python3 src/habilidades.py
python3 src/mercado.py
python3 src/llm.py
```

### Flags CLI

| Flag | Descrição |
|------|-----------|
| `--elenco PATH` | Caminho para arquivo JSON de elenco |
| `--listar-personagens` | Lista personagens do elenco e sai |
| `--llm` | Ativa LLM (Ollama) para personagem marcado |
| `--model MODELO` | Modelo LLM (ex: qwen2.5:0.5b) |
| `--provider ollama/llamacpp` | Provedor LLM |
| `--url URL` | URL do servidor LLM |
| `--alternar N` | Alterna LLM entre personagens a cada N ticks |
| `-i [N]` | Modo interativo (N ticks iniciais opcionais) |
| `-v` | Aumenta verbosidade |

Não há linter, formatador, type checker ou test framework configurados.

## Convenções

- **Imports**: `from __future__ import annotations` no topo. stdlib → módulos internos (sem pacote, imports diretos entre `src/`)
- **Separadores**: `# =====` com comentário em maiúsculo (ex: `# ===== ENUMS =====`)
- **Nomes**: `snake_case` para funções/variáveis, `PascalCase` para classes, `MAIUSCULO` para constantes
- **Docstrings**: `"""inglês (título) — português (descrição)"""` — títulos dos módulos em português
- **Tipos**: uso extensivo de `@dataclass`, `Enum`, `Optional`, tipos genéricos. Evitar `Any`
- **Enums**: com valor string explícito (ex: `ATIVO = "ativo"`)
- **Factory functions**: `criar_*` em português para criar instâncias padrão
- **Erro**: uso de `try/except` com fallback silencioso (especialmente no LLM)
- **Testes**: inline `if __name__ == "__main__":` em cada módulo — sem pytest

## Observações

- Sempre usar `urllib` (stdlib), nunca `requests` ou outras libs externas
- Filosofia: código interpretável por LLM pequeno (Qwen2-0.5B)
- Saída no terminal com emojis (🐟🌲⛏️ etc.)
- Personagens têm névoa de guerra: só conhecem locais que visitaram
- Evitar dependências externas — o projeto deve rodar com Python puro

## Funcionalidades Espinozistas Implementadas

### Razão como Curiosidade (em `mundo.py`)
- `razao_vs_paixao` reduz limiar de fome/sede: `0.40 − razao × 0.15`
- Razão > 0.5: chance de priorizar engenharia/crafting sobre necessidades básicas
- Prioridade: ferramentas → construção → processamento

### Pedidos Sociais (em `mundo.py`, método `_tentar_pedido`)
- Personagem racional (razao ≥ 0.5) pede ajuda a outro
- Prioridade 1: **ensinar** skill que o outro domina
- Prioridade 2: **craftar** item que o requerente não sabe fazer
- Chance de aceite: `0.5 + relação × 0.2`
- Ambos ganham XP

### Aprendizado Emergente (em `habilidades.py` e `mundo.py`)
- `pode_ensinar` desde nível 0.2
- Curva XP: ×1.3 por nível (mais suave)
- Crafting experimental: tenta mesmo sem nível mínimo (penalidade 0.5× no nível efetivo)
- Observação de crafting dá XP (1/4 do XP do executor)
- Sono forçado quando energia < 0.15

### Personagens em JSON
- Cada personagem é um arquivo JSON independente em `personagens/`
- Rosters em `elenco/` referenciam quais personagens usar
- Schema: nome, arquetipo, idade, razao_innata, local_inicial, motivacoes, valores, medos
