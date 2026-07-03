<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/status-alpha-orange" alt="Alpha">
  <img src="https://img.shields.io/badge/dependencies-none-brightgreen" alt="No Dependencies">
</p>

<h1 align="center">⚡ Conatus</h1>
<p align="center">
  <em>Simulação social emergente espinozista com múltiplos personagens interpretados por LLMs pequenos</em>
</p>
<p align="center">
  <code>pip install conatus</code> ·
  <a href="#-início-rápido">Início Rápido</a> ·
  <a href="#-fundamentos">Fundamentos</a> ·
  <a href="#-componentes">Componentes</a>
</p>

---

**Conatus** é um motor de simulação social onde cada personagem — interpretado por um LLM pequeno (Qwen2-0.5B, Llama 3.2, etc.) — age movido pelo *conatus*: o esforço fundamental de perseverar e aumentar sua **potência de agir**, conforme a *Ética* de Spinoza.

Cada interação é um **encontro** que pode aumentar a potência (*alegria*, *adequação*) ou diminuí-la (*tristeza*, *dissolução*). A simulação roda **sem dependências externas** — apenas Python puro.

---

## ✨ Destaques

- 🧠 **Personagens com livre-arbítrio** — decisões via LLM local (Ollama, llama.cpp) ou mock rule-based
- 🌍 **Mundo persistente** — mapa com locais, recursos, clima, distâncias e pathfinding BFS
- 🔨 **Crafting & habilidades** — cadeias de produção, ensino entre personagens, níveis que evoluem
- 🤝 **Sistema social** — trocas, barganha, reputação, compartilhamento de conhecimento
- 🗺️ **Névoa de guerra** — cada personagem só conhece os locais que visitou
- 📦 **Zero dependências** — apenas `urllib` da stdlib para comunicação com LLMs

---

## 📚 Fundamentos

Baseado na **Ética de Spinoza** (1677):

| Conceito | Na Simulação |
|----------|-------------|
| **Conatus** | Impulso de cada personagem para perseverar e expandir sua potência de agir |
| **Potência de agir** | Medida de quão capaz o personagem é de realizar seus desejos |
| **Adequação** | Encontro que aumenta a potência → alegria, crescimento, aprendizado |
| **Dissolução** | Encontro que diminui a potência → tristeza, fome, perigo |
| **Razão** | Decisões pensadas, de longo prazo, aumentam potência consistentemente |
| **Paixão** | Decisões impulsivas, de curto prazo, podem aumentar ou diminuir |
| **Alegria** | Afeto positivo — passagem para maior potência |
| **Tristeza** | Afeto negativo — passagem para menor potência |

> *"Cada coisa esforça-se, tanto quanto está em seu poder, por perseverar em seu ser."* — Spinoza, Ética III, Proposição 6

---

## 🚀 Início Rápido

### Requisitos

- **Python 3.10+**
- **Opcional:** [Ollama](https://ollama.ai) com modelo pequeno (`ollama pull qwen2.5:0.5b`) para decisões via LLM

### Instalação

```bash
# Via git
git clone https://github.com/Cleedee/conatus.git
cd conatus

# (recomendado) Ambiente virtual
python3 -m venv venv
source venv/bin/activate
```

### Rodar a simulação

```bash
cd src

# Simulação básica — sem LLM (decisões rule-based)
python3 mundo.py

# Simulação com Ollama (se instalado)
python3 testar_ollama.py

# Modo interativo (REPL para explorar ao vivo)
python3 mundo.py --interativo

# Com LLM ativado por argparse
python3 mundo.py --llm
```

### Modo interativo (REPL)

```
🐟 Conatus — Modo Interativo

> olhar vila
> status maria
> lista
> tick
> ajuda
```

---

## 🗂️ Estrutura do Projeto

```
conatus/
├── src/
│   ├── __init__.py        # Pacote Python
│   ├── personagem.py      # Personagem, Personalidade, Afetos, Memória, Conhecimento
│   ├── encontros.py       # MotorEncontros, GeradorEncontros, EventoMundo
│   ├── mapa.py            # Mapa, Local, pathfinding BFS, clima
│   ├── mundo.py           # Simulacao — orquestrador do tick loop
│   ├── llm.py             # AgenteLLM, ConfigLLM, ProviderLLM (Ollama, llama.cpp, HTTP)
│   ├── habilidades.py     # MotorCrafting, Habilidade, Inventario, Receitas
│   ├── mercado.py         # Mercado, Troca, barganha, reputação
│   ├── interface.py       # Modo interativo (cmd.Cmd)
│   ├── testar_ollama.py   # Teste completo com Ollama
│   └── teste_rapido.py    # Teste de conectividade Ollama
├── docs/
│   └── brainstorm_simulacao_social.md  # Documento de design
├── AGENTS.md              # Instruções para o agente de código
├── pyproject.toml         # Metadados do projeto
├── LICENSE                # MIT
└── README.md              # Este arquivo
```

---

## ⚙️ Componentes Principais

### Personagem (`personagem.py`)

```python
from personagem import Personagem, Personalidade

pers = Personalidade(
    nome="Maria",
    arquetipo="generoso",
    idade=35,
    descricao="Mulher calorosa que gosta de ajudar",
    razao_innata=0.6,  # 0 = pura paixão, 1 = pura razão
    motivacoes={
        "sobrevivencia": 0.8,
        "conforto": 0.5,
        "ajudar_outros": 0.7,
        "curiosidade": 0.4,
    },
    medos=["solidão", "fome"],
)
maria = Personagem(pers, local_inicial="vila")

# Conhecimento do mundo (névoa de guerra)
print(maria.get_locais_conhecidos())   # ['vila']
print(maria.get_recursos_conhecidos("vila"))

# Descobrir local ao explorar
maria.descobrir_local("floresta", ["madeira", "caça"], perigo=0.4)

# Compartilhar conhecimento com outro personagem
maria.compartilhar_conhecimento(joao)
```

### Mapa (`mapa.py`)

```python
from mapa import criar_mapa_padrao

mapa = criar_mapa_padrao()

local = mapa.get_local("vila")
print(local.descricao_completa())

# Pathfinding BFS
caminho = mapa.get_caminho("vila", "caverna")   # ['vila', 'montanha', 'caverna']
tempo = mapa.get_tempo_caminho("vila", "caverna")  # 7 ticks

# Locais com determinado recurso
locais = mapa.locais_com_recurso("comida")
```

### Motor de Encontros (`encontros.py`)

```python
from encontros import MotorEncontros

motor = MotorEncontros()

encontros = motor.obter_encontros_para_personagem(
    personagem, todos_personagens, hora, eventos
)
resultado = motor.processar_encontro(personagem, encontros[0])
```

### Habilidades e Crafting (`habilidades.py`)

```python
from habilidades import Habilidade, Inventario, MotorCrafting

# Criar item via crafting
motor = MotorCrafting()
sucesso, mensagem = motor.tentar_craftar(
    personagem, "prancha",
    materiais=[("madeira", 2)]
)
```

### Mercado e Trocas (`mercado.py`)

```python
from mercado import Mercado, criar_mercado_padrao

mercado = criar_mercado_padrao()
troca = mercado.propor_troca(maria, joao,
    oferece={"madeira": 5},
    recebe={"comida": 3}
)
```

---

## 🎮 Mecânicas em Detalhe

### Sistema de Encontros

| Tipo | Efeito | Exemplo |
|------|--------|---------|
| ✅ Adequação | Potência ↑ (alegria) | Comer, aprender, ajudar |
| ❌ Dissolução | Potência ↓ (tristeza) | Fome, traição, perigo |
| ➖ Neutro | Sem mudança | Observar, esperar |

### Locais do Mundo

| Local | Recursos | Perigo | Conecta a |
|-------|----------|--------|-----------|
| 🏘️ Vila | Comida, água, ferramentas | Baixo | Floresta, Montanha, Planície, Rio |
| 🌲 Floresta | Madeira, caça, ervas | Médio | Vila, Montanha |
| ⛰️ Montanha | Pedra, minerais, cristais | Alto | Vila, Floresta, Caverna |
| 🌾 Planície | Colheita, ervas medicinais | Baixo | Vila, Rio, Praia |
| 🌊 Rio | Água fresca, peixes | Médio | Vila, Planície, Praia |
| 🏖️ Praia | Mariscos, sal | Baixo | Rio, Planície |
| 🕳️ Caverna | Minerais, cristais, fungos | Alto | Montanha |

### Habilidades

| Habilidade | Descrição | Arquétipos |
|------------|-----------|------------|
| 🪓 Madeireiro | Cortar/processar madeira | Ativo |
| 🔨 Construtor | Construir estruturas | Prudente |
| ⚒️ Ferreiro | Trabalhar metal | Dominador |
| 🍳 Cozinheiro | Preparar alimentos | Generoso |
| 💊 Médico | Criar remédios | Filósofo |
| 🛠️ Artesão | Criar ferramentas | Prudente |

**Níveis:** `Ignorante → Iniciante → Capaz → Habilidoso → Mestre`

### Cadeias de Produção

```
Matéria-prima → Processamento → Item Final

Madeira → Talar → Pranchas → Cabana
Minério → Fundir → Metal → Picareta
Ervas   → Misturar → Remédio
```

### Comportamento por Personalidade

| Arquétipo | Prioridade |
|-----------|------------|
| 🧠 **Filósofo** | Reflexão, aprendizado, conversas profundas |
| 🏃 **Ativo** | Exploração, aventura, mover-se |
| 🛡️ **Prudente** | Segurança, recursos, planejamento |
| 💝 **Generoso** | Ajudar outros, interação social |
| 👑 **Dominador** | Recursos valiosos, controle |
| 😨 **Medo** | Evitar riscos, ficar em locais seguros |

---

## 🧪 Testes Individuais

Cada módulo tem um bloco `if __name__ == "__main__":` — rode direto:

```bash
cd src

python3 mapa.py          # Testar mapa e pathfinding
python3 personagem.py    # Testar personagem e personalidades
python3 encontros.py     # Testar motor de encontros
python3 habilidades.py   # Testar crafting e habilidades
python3 mercado.py       # Testar trocas e barganha
python3 llm.py           # Testar conexão com LLM
```

---

## 📊 Personalização

### Criar personagens customizados

```python
from personagem import Personagem, Personalidade

pers = Personalidade(
    nome="Helena",
    arquetipo="filosofo",  # filosofo, ativo, prudente, generoso, dominador, medo
    idade=28,
    descricao="Pensadora inquieta que busca compreender o mundo",
    razao_innata=0.8,
    motivacoes={
        "sobrevivencia": 0.3,
        "conforto": 0.2,
        "poder": 0.1,
        "reputacao": 0.5,
        "ajudar_outros": 0.6,
        "curiosidade": 0.9
    },
    valores=["sabedoria", "verdade", "compaixao"],
    medos=["ignorancia", "estagnacao"]
)

helena = Personagem(pers, local_inicial="vila")
```

### Configurar LLM externo

```python
from llm import ConfigLLM, ProviderLLM
from mundo import Simulacao

config = ConfigLLM(
    provider=ProviderLLM.OLLAMA,
    modelo="qwen2.5:0.5b",
    temperature=0.7,
    max_tokens=150,
    host="http://localhost:11434"
)

sim = Simulacao(config_llm=config, usar_llm=True)
```

---

## 🧠 Objetivos de Design

Verificar se emergem naturalmente:

1. ✅ Exploração e descoberta do mapa
2. ✅ Compartilhamento de informações entre personagens
3. ✅ Comportamento consistente com a personalidade
4. ✅ Resposta à escassez de recursos
5. ✅ Habilidades e crafting
6. ✅ Ensino e aprendizado entre personagens
7. ⬜ Formação de facções e alianças
8. ⬜ Especialização de papéis
9. ⬜ Conflito e resolução
10. ⬜ Traição e perdão
11. ⬜ Cultura emergente (nomes, rituais, histórias)
12. ⬜ Evolução da racionalidade coletiva

---

## 📝 Referências

- **Spinoza**, *Ética* (1677) — Fundamento filosófico de todo o sistema
- **The Sims** (Maxis) — Sistema de necessidades e livre-arbítrio
- **Dwarf Fortress** (Tarn Adams) — Complexidade emergente e simulação de mundo
- **Generative Agents** (Stanford, 2023) — Simulação social com LLMs
- **AI Town** (a16z) — Arquitetura de agentes sociais com LLMs

---

<p align="center">
  <sub>Feito com ☕ e 🐍 — <a href="https://github.com/Cleedee/conatus">Conatus</a> · MIT License</sub>
</p>
