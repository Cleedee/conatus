# Brainstorm: Simulação Social com LLMs Pequenos

> Documento de design — v2.0 (com mecânica spinozista de encontros)

---

## 🎯 Conceito Central

Múltiplos LLMs pequenos (Qwen2-0.5B ou similar) interpretam personagens numa simulação social emergente. Cada personagem tem memória, personalidade e reage autonomamente ao mundo e aos outros.

**Base filosófica:** Ética Espinozista — toda interação é um *encontro* que aumenta ou diminui a *potência de agir* do personagem.

---

## ⚙️ Parâmetros Definidos

| Aspecto | Decisão |
|---------|---------|
| Número de personagens | 5-10 |
| Visualização | Terminal (texto) |
| Recursos | Escassos |
| Eventos | Naturais / ambientais |
| Competição vs Cooperação | **Misto emergente** |
| Hardware | 2 computadores com CPU |
| Modelo base | Qwen2-0.5B (Q4, ~500MB) |
| Filosofia subjacente | Espinoza (encontros, potência, afetos) |

---

## 🧠 Fundamentos Espinozistas

### Conceitos Chave

| Conceito | Definição | Aplicação no Jogo |
|----------|-----------|-------------------|
| **Conatus** | Esforço de perseverar no ser | Base motivacional de todo personagem |
| **Potência de agir** | Capacidade de agir e existir | Métrica central (0.0 - 1.0) |
| **Encontro** | Interação entre partes da natureza | Mecânica unificada do jogo |
| **Adequação** | Encontro que aumenta potência | Resulta em ALEGRIA |
| **Dissolução** | Encontro que diminui potência | Resulta em TRISTEZA |
| **Razão vs Paixão** | Compreensão vs reação imediata | Eixo de desenvolvimento do personagem |

### O Princípio dos Encontros

> "Quando uma coisa concorda com a natureza de outra, isso beneficia e aumenta a potência de agir de ambas. Quando discorda, isso prejudica e diminui." — Ética, III, prop. 4-6

**Toda interação é um encontro.** Não existem ações neutras — cada encontro gera um delta de potência:

```
ENCONTRO → ADEQUAÇÃO (potência ↑) → ALEGRIA
    ou
ENCONTRO → DISSOLUÇÃO (potência ↓) → TRISTEZA
```

---

## 🎲 Mecânica Unificada de Encontros

### O que conta como "Encontro"?

| Tipo | Exemplo | Pode ser Adequação | Pode ser Dissolução |
|------|---------|-------------------|---------------------|
| **Físico** | Comer, beber, construir | Recurso satisfaz necessidade | Recurso falha ou falta |
| **Social** | Conversar, negociar, lutar | Cooperação bem-sucedida | Conflito, traição |
| **Ambiental** | Encher-se de chuva, sol | Proteção, conforto | Tempestade, frio |
| **Cognitivo** | Aprender, planejar | Compreensão nova | Confusão, erro |
| **Observacional** | Ver outros interagirem | Informação valiosa | Ameaça percebida |

### Ciclo de Encontros

```
┌─────────────────────────────────────────────────────────┐
│                    ENCONTRO                             │
│                                                         │
│  Agente: {personagem}                                   │
│  Objeto: {recurso, pessoa, evento, ambiente}            │
│  Ação: {o que o personagem faz}                         │
│                                                         │
│  Resultado:                                             │
│  ├── Potência ↑ (+delta) = ALEGRIA                      │
│  └── Potência ↓ (-delta) = TRISTEZA                     │
│                                                         │
│  Memória registra: quem, o quê, resultado               │
└─────────────────────────────────────────────────────────┘
```

### Cálculo de Delta de Potência

```python
def calcular_delta_potencia(personagem, encontro):
    base = encontro.magnitude  # quão intenso é o encontro
    
    # Modificadores
    razao = personagem.razao_vs_paixao
    memoria = personagem.memoria.buscar(encontro.objeto)
    
    # Personagem racional prevê melhor
    ajuste_razao = 1.0 + (razao * 0.3)  # até +30% eficiência
    
    # Memória anterior afeta (aprendizado)
    if memoria and memoria.resultado_anterior > 0:
        ajuste_memoria = 1.2  # confiança
    elif memoria and memoria.resultado_anterior < 0:
        ajuste_memoria = 0.7  # cautela
    else:
        ajuste_memoria = 1.0  # neutro
    
    # Cálculo final
    delta = base * ajuste_razao * ajuste_memoria * encontro.sinal
    
    return delta  # positivo = alegria, negativo = tristeza
```

---

## 👤 Estado Interno do Personagem

### Estrutura de Dados

```json
{
  "nome": "Maria",
  "idade": 35,
  
  "potencia_atual": 0.7,
  "potencia_max": 1.0,
  
  "razao_vs_paixao": 0.6,
  
  "afetos": {
    "alegria": 0.3,
    "tristeza": 0.1,
    "desejo": 0.5,
    "esperanca": 0.4,
    "temor": 0.2
  },
  
  "necessidades": {
    "energia": 0.8,
    "fome": 0.6,
    "sede": 0.7,
    "abrigo": 0.9
  },
  
  "localizacao": "vila",
  "estado": "ativo",
  
  "relacoes": {
    "joao": {
      "afeto": 0.4,
      "confianca": 0.2,
      "compreensao": 0.6,
      "encontros": 12
    }
  }
}
```

### Efeitos dos Afetos no Comportamento

| Afeto | Efeito na Decisão |
|-------|-------------------|
| **Alegria alta** | Mais propenso a cooperar, arriscar |
| **Tristeza alta** | Cauteloso, pode evitar encontros |
| **Desejo alto** | Busca ativamente encontros |
| **Esperança alta** | Planeja a longo prazo |
| **Temor alto** | Prioriza segurança, foge de riscos |

---

## 👥 Arquétipos Espinozistas

### Espectro de Racionalidade

```
MAIS RACIONAL ←————————————————————→ MAIS PASSIONAL
     │                                        │
  Compreende causas                   Reage instintivamente
  Planeja a longo prazo               Vê apenas o imediato
  Coopera por entendimento            Coopera por necessidade
  Perdoa (entende o outro)            Guarda rancor
```

### Arquétipos Possíveis

| Arquétipo | Razão | Potência | Estilo de Encontro |
|-----------|-------|----------|-------------------|
| **O Filósofo** | 0.9 | 0.6 | Busca compreender antes de agir |
| **O Ativo** | 0.4 | 0.8 | Age por impulso, aprende com erros |
| **O Prudente** | 0.7 | 0.5 | Calcula risco/recompensa |
| **O Generoso** | 0.6 | 0.7 | Entende que coletivo aumenta poder |
| **O Dominador** | 0.3 | 0.9 | Confunde poder sobre outros com poder próprio |
| **O Medo** | 0.5 | 0.3 | Conatus paralisado pelo temor |

---

## 🗺️ Sistema de Espaço

### Mapa Topográfico

```
┌─────────────────────────────────────────────────────────┐
│                    MAPA MUNDI                           │
│                                                         │
│   [Floresta]────[Rio]────[Planície]                     │
│       │           │           │                         │
│      [ ]        [ ]        [ ]                          │
│       │           │           │                         │
│   [Montanha]──[Vila]────[Praia]                         │
│                     │                                   │
│                  [Caverna]                              │
│                                                         │
│   Distâncias em "turnos de locomoção"                   │
│   Ex: Vila → Rio = 2 turnos                            │
│       Vila → Floresta = 3 turnos                       │
└─────────────────────────────────────────────────────────┘
```

### Estrutura de Local

```json
{
  "id": "vila",
  "nome": "Vila",
  "tipo": "assentamento",
  "recursos_disponiveis": ["comida", "abrigo", "ferramentas"],
  "capacidade": 10,
  "conexoes": {
    "rio": 2,
    "planicie": 3,
    "caverna": 4
  },
  "perigo": 0.1,
  "encontros_recentes": []
}
```

---

## ⏱️ Sistema de Tempo

### Unidades Temporais

```
┌─────────────────────────────────────────────────────────┐
│ ESTRUTURA TEMPORAL                                      │
├─────────────────────────────────────────────────────────┤
│ TICK = 1 ação de um personagem (~2-5s processamento)    │
│                                                         │
│ MINUTO = 4 ticks                                        │
│ HORA = 60 minutos                                       │
│ DIA = 24 horas                                          │
│ SEMANA = 7 dias                                         │
└─────────────────────────────────────────────────────────┘
```

### Ciclo Dia/Noite

```python
class Mundo:
    def tick(self):
        self.hora += 1
        
        # Efeitos do ciclo natural
        if self.hora == 6:  # amanhecer
            self.eventos.append("dia_comeca")
            for p in self.personagens:
                p.afetos.esperanca += 0.1  # nova chance
        elif self.hora == 20:  # entardecer
            self.eventos.append("noite_comeca")
            for p in self.personagens:
                p.afetos.temor += 0.1  # noite traz incerteza
        
        # Fadiga acumula
        for p in self.personagens:
            if not p.dormindo:
                p.necessidades.energia -= 0.02
            else:
                p.necessidades.energia += 0.05
        
        # Recursos regeneram (lentamente)
        for local in self.locais:
            local.recursos.regenerar(0.005)
```

---

## 🚶 Sistema de Locomoção

### Decisão de Movimento

```python
def prompt_locomocao(personagem, mapa):
    return f"""
Você está em: {personagem.local_atual}
Hora atual: {mapa.hora} ({'dia' if mapa.e_dia() else 'noite'})

Distâncias a partir daqui:
{formatar_distancias(personagem.local_atual, mapa)}

Seu estado:
- Energia: {personagem.necessidades.energia}
- Fome: {personagem.necessidades.fome}
- Sede: {personagem.necessidades.sede}
- Potência: {personagem.potencia_atual}

O que você faz?
1. Ficar no local atual
2. Mover para outro local (escolha qual)
3. Descansar/dormir (se noite ou cansado)

Responda com:
{{
  "decisao": "ficar/mover/descansar",
  "destino": "local_id" (se mover),
  "motivo": "..."
}}
"""
```

### Custo de Locomoção

```python
class Local:
    def tempo_para(self, destino, personagem, hora):
        """Retorna ticks necessários para chegar"""
        distancia = self.conexoes.get(destino.id, 999)
        
        # Modificadores
        if not (6 <= hora <= 20):  # noite
            distancia *= 1.5
        if personagem.necessidades.energia < 0.3:
            distancia *= 1.3
        
        return int(distancia)
```

---

## 🤔 Decisão de Ficar Parado

### Por que personagens ficariam parados?

| Razão | Descrição | Efeito Potencial |
|-------|-----------|------------------|
| **Aguardar** | Esperar evento ou pessoa | Encontro futuro possible |
| **Descansar** | Recuperar energia | Potência ↑ gradual |
| **Segurança** | Local desconhecido = perigo | Evita dissolução |
| **Indecisão** | Não sabe o que fazer | Neutro |
| **Guarda** | Proteger recurso/local | Defensivo |
| **Refletir** | Processar encontros recentes | Pode aumentar razão |

### Mecânica de Espera

```python
class Personagem:
    def decide_ficar(self, motivo, duracao):
        """Ficar parado é ativo, não passivo"""
        self.estado = "esperando"
        self.motivo_espera = motivo
        self.ticks_espera = duracao
    
    def tick_espera(self):
        """A cada tick esperando, verifica encontros potenciais"""
        self.ticks_espera -= 1
        
        # Checa eventos no local
        eventos = self.local_atual.eventos_recentes
        
        if eventos:
            return self.avaliar_encontros(eventos)
        
        # Chance de encontro aleatório (10% por tick)
        if random() < 0.1:
            return self.encontro_aleatorio()
        
        return None
```

---

## 👁️ Encontros Observados

### Conceito

Personagem **observa** outros interagindo sem participar diretamente.

```
┌─────────────────────────────────────────────────────────┐
│ ENCONTRO OBSERVADO                                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [Maria] ←───── observa ──────→ [João & Ana]           │
│                                    discutindo           │
│                                                         │
│  Efeito em Maria:                                       │
│  - Aprende sobre relação João-Ana                       │
│  - Forma opinião (pode gerar afeto)                     │
│  - Obtém informação (recurso, perigo)                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Processamento

```python
def processar_observacao(personagem, encontro_outros):
    prompt = f"""
Você observa de longe:
- {encontro_outros.agente_1} interage com {encontro_outros.agente_2}
- Ação: {encontro_outros.acao}
- Resultado aparente: {encontro_outros.resultado}

Você não participa, apenas observa.

O que você pensa sobre isso?
Responda com:
{{
  "observacao": "...",
  "informacao_aprendida": "...",
  "afeto_modificado": {{"quem": "...", "delta": -1.0 a 1.0}},
  "vai_reagir": true/false
}}
"""
    return personagem.llm.infer(prompt)
```

### Custos e Limitações

- **Encontros observados** usam inferência dedicada
- Personagem pode **escolher não reagir** (apenas registrar)
- Complexidade: 1 inferência extra por observador

---

## 🌍 Recursos e Eventos

### Recursos Escassos

| Recurso | Função | Renovação | Encontro Potencial |
|---------|--------|-----------|-------------------|
| **Água** | Sobrevivência | Chuva (aleatório) | Adequação: sede ↓; Dissolução: enchente |
| **Comida** | Energia | Agricultura/caça | Adequação: fome ↓; Dissolução: comida estragada |
| **Madeira** | Construção | Cresce lento | Adequação: abrigo ↑; Dissolução: não consegue cortar |
| **Ferramentas** | Eficiência | Craft | Adequação: tarefa facilitada; Dissolução: quebra |
| **Espaço** | Abrigo | Fixo | Adequação: segurança; Dissolução: superlotação |

### Eventos Naturais

| Evento | Efeito | Previsibilidade | Tipo de Encontro |
|--------|--------|-----------------|------------------|
| **Seca** | Reduz água | Semi-previsível | Dissolução ambiental |
| **Tempestade** | Destrói, enche água | Surpresa | Dissolução ou Adequação |
| **Colheita** | Abundância temporária | Sazonal | Adequação coletiva |
| **Doença** | Personagem enfraquece | Aleatório | Dissolução interna |
| **Visitante** | Novos recursos/info | Raro | Encontro social |

---

## ⚔️🤝 Competição vs Cooperação: Misto Emergente

### Princípio

O equilíbrio entre competir e cooperar **emerge** do comportamento dos personagens. Cada um tem motivação privada, mas existem incentivos à cooperação.

### Incentivos à Cooperação

1. **Bônus de eficiência** — grupo consegue mais que indivíduos
2. **Reputação** — cooperadores são mais bem-recebidos
3. **Desafios impossíveis** — alguns problemas sem solução individual
4. **Segurança** — grupo protege contra ameaças

### Consequências da Competição

1. **Desperdício** — conflito consome recursos
2. **Isolamento** — competidores tornam-se inimigos
3. **Reputação negativa** — traidores são evitados
4. **Instabilidade** — alianças frágeis

### Tabela de Motivações (exemplo)

```json
{
  "nome": "Maria",
  "motivacoes": {
    "sobrevivencia": 0.9,
    "conforto": 0.7,
    "poder": 0.5,
    "reputacao": 0.6,
    "ajudar_outros": 0.4,
    "curiosidade": 0.3
  },
  "limiares": {
    "trair_aliado_se": "sobrevivencia < 0.3",
    "cooperar_se": "beneficio_pessoal > 0.6"
  }
}
```

---

## 🎲 Mecânicas Emergentes Desejadas

Coisas que queremos ver acontecer naturalmente:

1. **Formação de facções/grupos**
   - Alianças que surgem e quebram
   - Liderança natural emergente

2. **Especialização**
   - Personagens que encontram seu "papel"
   - Dependência mútua saudável

3. **Conflito e resolução**
   - Desentendimentos sobre recursos
   - Negociação, mediação, ou escalação

4. **Traição e perdão**
   - Momentos de decisão moral
   - Consequências de longo prazo

5. **Cultura emergente**
   - Tradições, rituais
   - Normas sociais implícitas

6. **Evolução de racionalidade**
   - Personagens que aprendem com encontros
   - Passagem de paixão para razão

---

## 🖥️ Especificações Técnicas

### Hardware Disponível

```
┌────────────────────────────────────────────────────────┐
│ COMPUTADOR 1                                           │
│ - CPU: 4-8 cores                                       │
│ - RAM: 8-16 GB                                         │
│ - Modelo: Qwen2-0.5B Q4 (~500MB)                      │
│ - Instâncias simultâneas: 8-10                         │
│ - Velocidade: ~20-30 tokens/s                          │
├────────────────────────────────────────────────────────┤
│ COMPUTADOR 2                                           │
│ - CPU: 4-8 cores                                       │
│ - RAM: 8-16 GB                                         │
│ - Modelo: Qwen2-0.5B Q4 (~500MB)                      │
│ - Instâncias simultâneas: 8-10                         │
│ - Velocidade: ~20-30 tokens/s                          │
└────────────────────────────────────────────────────────┘
```

### Limitações e Soluções

| Limitação | Solução |
|-----------|---------|
| 10 personagens no mesmo local = O(n²) | Encontros em cascata (sequenciais) |
| Contexto pode exceder limite | Compressão de memória periódica |
| Latência por inferência: 2-5s | Aceitar pausa entre turnos |
| Distribuição entre máquinas | FastAPI + Redis Pub/Sub |

### Throughput Estimado

```
Cenário típico:
- 5 personagens em 2 locais diferentes
- 2-3 encontros simultâneos
- 5-8 inferências por turno
- Tempo por turno: ~15-30 segundos

Cenário complexo:
- 10 personagens num só local
- 1 encontro cascata (5 pares)
- 10 inferências sequenciais
- Tempo por turno: ~30-60 segundos
```

---

## 🔄 Ciclo de Simulação (Revisado)

```
┌─────────────────────────────────────────────────────────┐
│ 1. WORLD TICK                                          │
│    ├── Atualizar hora do dia                           │
│    ├── Processar efeitos de necessidades               │
│    ├── Resolver eventos naturais pendentes             │
│    ├── Gerar novos eventos aleatórios                  │
│    └── Verificar encontros em cada local               │
├─────────────────────────────────────────────────────────┤
│ 2. PERSONAL THINK (sequencial ou parcialmente paralelo)│
│    ├── Cada personagem avalia encontros disponíveis    │
│    ├── Decide: participar, observar, ou evitar         │
│    ├── Busca memórias relevantes                       │
│    ├── Gera: ação + fala + pensamento                  │
│    └── Calcula delta de potência                       │
├─────────────────────────────────────────────────────────┤
│ 3. ENCONTRO RESOLVE                                    │
│    ├── Processar encontros diretos (2+ personagens)    │
│    ├── Processar encontros com ambiente/recursos       │
│    ├── Processar observações                           │
│    ├── Atualizar potência e afetos                     │
│    └── Registrar tudo na memória                       │
├─────────────────────────────────────────────────────────┤
│ 4. DISPLAY                                             │
│    └── Mostrar resumo do turno no terminal             │
└─────────────────────────────────────────────────────────┘
```

### Detalhe: Personal Think

```python
def processar_turno(mundo):
    for personagem in mundo.personagens:
        # 1. Avaliar encontros disponíveis
        encontros = mundo.encontros_disponiveis(personagem)
        
        # 2. LLM decide o que fazer
        prompt = construir_prompt(personagem, encontros)
        decisao = personagem.llm.infer(prompt)
        
        # 3. Executar decisão
        if decisao.tipo == "encontro_direto":
            resultado = executar_encontro(personagem, decisao.objeto)
            personagem.aplicar_delta(resultado.delta)
        
        elif decisao.tipo == "encontro_observado":
            observacao = processar_observacao(personagem, decisao.encontro)
            personagem.memoria.registrar(observacao)
        
        elif decisao.tipo == "locomocao":
            personagem.mover(destino, mundo.calcula_distancia(...))
        
        elif decisao.tipo == "ficar":
            personagem.iniciar_espera(decisao.motivo, decisao.duracao)
        
        # 4. Registrar encontro
        mundo.registrar_encontro(personagem, decisao)
```

---

## ❓ Questões em Aberto

### Mecânicas
- [ ] Encontros entre 3+ personagens: processar em pares ou grupo?
- [ ] Como representar "multidão" (muitos personagens num local)?
- [ ] Personagem pode recusar encontro? Sempre ou com consequências?

### Técnicas
- [ ] Ollama para gerenciar múltiplas instâncias ou llama.cpp direto?
- [ ] Como sincronizar os dois computadores (clock, estado)?
- [ ] Cache de prompts para reutilização?

### Narrativa
- [ ] Começar com cenário pré-definido ou geração aleatória?
- [ ] Intervenção humana permitida (como "deus")?
- [ ] Logs para análise posterior? Formato?

### Éticos/Filosóficos
- [ ] LLMs pequenos podem gerar conteúdo problemático?
- [ ] Os personagens devem saber que são simulações?
- [ ] O que acontece quando um personagem chega a potência 0?

---

## 📚 Referências

- **Spinoza, Ética** — Fundamento filosófico
- **The Sims** — Motivações e necessidades
- **Dwarf Fortress** — Complexidade emergente
- **AI Town (Stanford)** — Simulação social com LLMs
- **Game of Life** — Regras simples, comportamento complexo
- **llama.cpp / Ollama** — Inferência local

---

## 🗺️ Próximos Passos

1. **Definir arquétipos** — 5-6 personagens com stats completos
2. **Prototipar encontro** — Mecânica básica de delta de potência
3. **Criar mapa** — Locais e conexões iniciais
4. **Testar inferência** — Validar throughput em CPU
5. **Iterar** — Refinar com base em testes

---

*Documento gerado durante brainstorm em 2026-07-02*
*Baseado na ética spinozista de encontros e potência de agir*
