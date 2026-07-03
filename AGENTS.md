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
├── mapa.py         # Mapa, Local, pathfinding BFS
├── mundo.py        # Simulacao — orquestrador do tick loop
├── llm.py          # AgenteLLM, ConfigLLM, ProviderLLM
├── habilidades.py  # MotorCrafting, Habilidade, Inventario, Receitas
├── mercado.py      # Mercado, Troca, barganha
├── teste_rapido.py # Teste de conectividade Ollama
└── testar_ollama.py# Teste completo com Ollama
```

## Comandos

```bash
# Rodar simulação (sem LLM)
python3 src/mundo.py

# Rodar simulação com Ollama
python3 src/testar_ollama.py

# Testar módulo individual
python3 src/mapa.py
python3 src/personagem.py
python3 src/encontros.py
python3 src/habilidades.py
python3 src/mercado.py
python3 src/llm.py
```

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
