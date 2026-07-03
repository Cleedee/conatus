# Conatus

Simulação social emergente onde múltiplos LLMs pequenos interpretam personagens que interagem num mundo compartilhado. O nome **Conatus** — termo central da *Ética* de Spinoza — representa o esforço de cada ser para perseverar e aumentar sua potência de agir.

## 📚 Fundamentos

Baseado na **Ética de Spinoza**:
- Toda interação é um **encontro** que afeta a **potência de agir**
- **Adequação** = encontro que aumenta potência (alegria)
- **Dissolução** = encontro que diminui potência (tristeza)
- Personagens evoluem entre **razão** e **paixão**

## 🗂️ Estrutura do Projeto

```
src/
├── personagem.py    # Classe Personagem (estado, memória, conhecimento)
├── encontros.py     # Motor de encontros (geração e processamento)
├── mapa.py          # Mapa e locais do mundo
├── mundo.py         # Orquestrador da simulação
└── llm.py           # Interface com LLMs (Ollama, llama.cpp)
```

## 🚀 Início Rápido

### Requisitos
- Python 3.10+
- Opcional: Ollama ou llama.cpp para decisões via LLM

### Rodar Simulação

```bash
cd src

# Simulação básica (sem LLM)
python3 mundo.py

# Teste com Ollama
python3 testar_ollama.py

# Ou importar e usar no seu código
python3 -c "
from mundo import criar_simulacao_padrao

sim = criar_simulacao_padrao()
sim.rodar(ticks=20)
"
```

### Com Ollama

1. Instale Ollama: https://ollama.ai
2. Baixe um modelo pequeno: `ollama pull qwen2.5:0.5b`
3. Rode a simulação - detectará automaticamente

## ⚙️ Componentes Principais

### Personagem (`personagem.py`)

```python
from personagem import Personagem, Personalidade

# Criar personagem
pers = Personalidade(
    nome="Maria",
    arquetipo="generoso",
    idade=35,
    descricao="Mulher calorosa",
    razao_innata=0.6
)
maria = Personagem(pers, local_inicial="vila")

# Ver conhecimento do mundo
print(maria.get_locais_conhecidos())  # ['vila']
print(maria.get_contexto_conhecimento())

# Descobrir local (automático ao chegar)
maria.descobrir_local("floresta", ["madeira", "caça"], 0.4)

# Compartilhar com outro personagem
maria.compartilhar_conhecimento(joao)
```

### Sistema de Conhecimento 🔍

Cada personagem começa sabendo apenas do local inicial. Ao explorar, descobre novos locais e seus recursos.

```python
# Verificar se conhece um local
maria.local_conhecido("floresta")  # True/False

# Ver recursos que sabe que existem
maria.get_recursos_conhecidos("floresta")  # ['madeira', 'caça']

# Ver todos os locais conhecidos
maria.get_locais_conhecidos()  # ['vila', 'floresta', 'rio']

# Ver locais ainda não descobertos
maria.get_locais_desconhecidos()  # ['montanha', 'praia', 'caverna']
```

### Mapa (`mapa.py`)

```python
from mapa import criar_mapa_padrao

mapa = criar_mapa_padrao()

# Consultar locais
local = mapa.get_local("vila")
print(local.descricao_completa())

# Buscar caminho
caminho = mapa.get_caminho("vila", "caverna")  # ['vila', 'montanha', 'caverna']
tempo = mapa.get_tempo_caminho("vila", "caverna")  # 7 ticks

# Locais com determinado recurso
locais = mapa.locais_com_recurso("comida")
```

### Motor de Encontros (`encontros.py`)

```python
from encontros import MotorEncontros

motor = MotorEncontros()

# Obter encontros disponíveis (inclui alternativas quando há escassez)
encontros = motor.obter_encontros_para_personagem(
    personagem, todos_personagens, hora, eventos
)

# Processar encontro
resultado = motor.processar_encontro(personagem, encontros[0])
```

### Simulação (`mundo.py`)

```python
from mundo import Simulacao, criar_mapa_padrao

# Criar simulação
sim = Simulacao(
    mapa=criar_mapa_padrao(),
    personagens=[...],
    usar_llm=True  # False para decisões simples
)

# Rodar
sim.rodar(ticks=100)
```

## 🎮 Mecânicas

### Sistema de Encontros

Todo encontro é um "encontro" espinozista que afeta a potência:

| Tipo | Efeito | Exemplo |
|------|--------|---------|
| Adequação | Potência ↑ (alegria) | Comer, aprender, ajuda |
| Dissolução | Potência ↓ (tristeza) | Fome, traição, perigo |
| Neutro | Sem mudança | Observar, esperar |

### Conhecimento e Descoberta 🗺️

```
┌─────────────────────────────────────────────────────────┐
│  INÍCIO: Personagem só conhece local inicial           │
│                                                         │
│  EXPLORAÇÃO: Ao chegar em novo local, descobre:        │
│  - Recursos disponíveis                                 │
│  - Nível de perigo                                      │
│                                                         │
│  COMPARTILHAMENTO: Ao conversar, troca informações     │
│  com outros personagens                                 │
│                                                         │
│  ESCASSEZ: Quando recurso acaba, busca alternativas    │
│  em locais conhecidos                                   │
└─────────────────────────────────────────────────────────┘
```

### Habilidades e Crafting 🔨

Cada personagem tem habilidades que evoluem com uso:

| Habilidade | Descrição | Arquétipos |
|------------|-----------|------------|
| Madeireiro | Cortar/processar madeira | Ativo |
| Construtor | Construir estruturas | Prudente |
| Ferreiro | Trabalhar metal | Dominador |
| Cozinheiro | Preparar alimentos | Generoso |
| Médico | Criar remédios | Filósofo |
| Artesão | Criar ferramentas | Prudente |

**Níveis de Habilidade:**
```
Ignorante (0-20%) → Iniciante (20-40%) → Capaz (40-60%) → Habilidoso (60-80%) → Mestre (80-100%)
```

**Cadeia de Produção:**
```
Matéria-prima → Processamento → Item Final

Exemplo:
  Madeira → Talar → Pranchas → Cabana
  Minério → Fundir → Metal → Picareta
  Ervas → Misturar → Remédio
```

**Receitas de Exemplo:**

| Receita | Materiais | Habilidade | Resultado |
|---------|-----------|------------|-----------|
| Talar Madeira | Madeira x2 | Madeireiro | Pranchas x4 |
| Fazer Machado | Pranchas x2, Pedra x1 | Ferreiro | Machado x1 |
| Construir Cabana | Pranchas x15, Cordas x5 | Construtor | Cabana x1 |
| Preparar Sopa | Comida x2, Água x1 | Cozinheiro | Sopa x3 |
| Preparar Remédio | Ervas x5, Cristais x2 | Médico | Remédio x1 |

### Ensino e Aprendizado 👨‍🏫

Personagens podem ensinar uns aos outros:

- **Professor** precisa ter habilidade ≥ 40%
- **Aluno** aprende mais rápido quando:
  - Professor é mestre (>80%)
  - Aluno é iniciante (<30%)
  - Há grande diferença de níveis

**Como aprender:**
1. **Ser ensinado** - Mais rápido, precisa de professor
2. **Observar** - Vê outro fazendo, aprende devagar
3. **Tentar sozinho** - Arriscado, pode falhar e perder material

### Locais do Mundo

| Local | Recursos | Perigo | Conexões |
|-------|----------|--------|----------|
| 🏘️ Vila | Comida, água, ferramentas | Baixo | Floresta, Montanha, Planície, Rio |
| 🌲 Floresta | Madeira, caça, ervas | Médio | Vila, Montanha |
| ⛰️ Montanha | Pedra, minerais, cristais | Alto | Vila, Floresta, Caverna |
| 🌾 Planície | Colheita, ervas medicinais | Baixo | Vila, Rio, Praia |
| 🌊 Rio | Água fresca, peixes | Médio | Vila, Planície, Praia |
| 🏖️ Praia | Mariscos, sal | Baixo | Rio, Planície |
| 🕳️ Caverna | Minerais, cristais, fungos | Alto | Montanha |

### Comportamento por Personalidade 🧠

Quando saciado, cada arquétipo age diferente:

| Arquétipo | Prioridade |
|-----------|------------|
| **Filósofo** | Reflexão, aprendizado, conversas profundas |
| **Ativo** | Exploração, aventura, mover-se |
| **Prudente** | Segurança, recursos, planejamento |
| **Generoso** | Ajudar outros, interação social |
| **Dominador** | Recursos valiosos, controle |
| **Medo** | Evitar riscos, ficar em locais seguros |

### Tempo e Eventos

- 1 tick ≈ 15-30 segundos
- Ciclo dia/noite afeta necessidades
- Eventos aleatórios:
  - 🌧️ Chuva/Seca
  - ⛈️ Tempestade
  - 🌾 Colheita pronta
  - 🤒 Doença
  - 🧳 Visitante

## 🧪 Testes

### Teste Rápido (sem LLM)
```bash
cd src
python3 -c "
from mundo import Simulacao, criar_simulacao_padrao
sim = Simulacao(usar_llm=False)
sim.rodar(ticks=10)
"
```

### Teste com Ollama
```bash
cd src
python3 testar_ollama.py
```

### Teste de Comportamento
```bash
cd src
python3 -c "
from encontros import GeradorEncontros
from personagem import Personagem, Personalidade

# Testar como cada personalidade decide
gerador = GeradorEncontros()
pers = Personalidade(nome='Maria', arquetipo='generoso', descricao='test')
maria = Personagem(pers, local_inicial='vila')
maria.necessidades.fome = 0.2  # com fome

encontros = gerador.gerar_encontros_locais('vila', 10, maria, [])
print([e.descricao for e in encontros])
"
```

## 📊 Personalização

### Criar Personagens

```python
from personagem import Personagem, Personalidade

pers = Personalidade(
    nome="Seu Personagem",
    arquetipo="prudente",  # filosofo, ativo, prudente, generoso, dominador, medo
    idade=30,
    descricao="Descrição do personagem",
    razao_innata=0.6,  # 0 = pura paixão, 1 = pura razão
    motivacoes={
        "sobrevivencia": 0.8,
        "conforto": 0.5,
        "poder": 0.3,
        "reputacao": 0.4,
        "ajudar_outros": 0.3,
        "curiosidade": 0.4
    },
    valores=["honestidade", "coragem"],
    medos=["solidão", "fome"]
)

personagem = Personagem(pers, local_inicial="vila")
```

### Configurar LLM

```python
from llm import ConfigLLM, ProviderLLM
from mundo import Simulacao

config = ConfigLLM(
    provider=ProviderLLM.OLLAMA,
    modelo="qwen2.5:0.5b",
    temperature=0.7,
    max_tokens=150
)

sim = Simulacao(config_llm=config, usar_llm=True)
```

## 🎯 Objetivos de Design

Ver se emergir naturalmente:
1. ✅ Exploração e descoberta do mapa
2. ✅ Compartilhamento de informações
3. ✅ Comportamento baseado em personalidade
4. ✅ Resposta à escassez de recursos
5. ✅ Habilidades e crafting
6. ✅ Ensino e aprendizado entre personagens
7. Formação de facções
8. Especialização de papéis
9. Conflito e resolução
10. Traição e perdão
11. Cultura emergente
12. Evolução de racionalidade

## 📝 Referências

- Spinoza, *Ética* (1677) - Fundamento filosófico
- The Sims - Sistema de necessidades
- Dwarf Fortress - Complexidade emergente
- AI Town (Stanford) - Simulação social com LLMs

---

*Projeto em desenvolvimento - Atualizado em 2026-07-02*
