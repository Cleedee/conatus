"""
Módulo de Personagem — Simulação Social Espinozista

Implementa a classe Personagem com estado baseado na ética de Spinoza:
- Potência de agir
- Razão vs Paixão
- Afetos (alegria, tristeza, desejo, etc.)
- Sistema de encontros
- Memória episódica
- Relações com outros personagens
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import json
import random
from datetime import datetime
from habilidades import Habilidade, Inventario


# =============================================================================
# ENUMS E CONSTANTES
# =============================================================================

class EstadoPersonagem(Enum):
    """Estados possíveis do personagem"""
    ATIVO = "ativo"
    ESPERANDO = "esperando"
    LOCOMOVENDO = "locomovendo"
    DORMINDO = "dormindo"
    FERIDO = "ferido"


class TipoEncontro(Enum):
    """Tipos de encontro possíveis"""
    FISICO = "fisico"              # interação com objeto/recurso
    RECURSO = "recurso"            # interação com recurso
    SOCIAL = "social"              # interação com outro personagem
    AMBIENTAL = "ambiental"        # interação com clima/ambiente
    COGNITIVO = "cognitivo"        # aprendizado, reflexão
    OBSERVACIONAL = "observacional"  # ver outros interagirem


class ResultadoEncontro(Enum):
    """Resultado do encontro"""
    ADEQUACAO = "adequacao"        # potência ↑
    DISSOLUCAO = "dissolucao"     # potência ↓
    NEUTRO = "neutro"             # sem efeito significativo


@dataclass
class Afetos:
    """
    Afetos do personagem (baseado em Spinoza)
    
    Spinoza identifica alegria e tristeza como afetos fundamentais,
    derivados do aumento/diminuição da potência de agir.
    Desejo é a inclinação a agir sentindo algo como bem.
    """
    alegria: float = 0.0       # sentimento de aumento da potência
    tristeza: float = 0.0     # sentimento de diminuição da potência
    desejo: float = 0.5       # inclinação a agir
    esperanca: float = 0.3    # expectativa de aumento de potência
    temor: float = 0.2        # expectativa de diminuição de potência
    
    def normalizar(self):
        """Mantém afetos entre 0 e 1"""
        self.alegria = max(0.0, min(1.0, self.alegria))
        self.tristeza = max(0.0, min(1.0, self.tristeza))
        self.desejo = max(0.0, min(1.0, self.desejo))
        self.esperanca = max(0.0, min(1.0, self.esperanca))
        self.temor = max(0.0, min(1.0, self.temor))
    
    def aplicar_alegria(self, magnitude: float):
        """Aumento de potência gera alegria"""
        self.alegria += magnitude
        self.tristeza -= magnitude * 0.5  # alegria reduz tristeza
        self.esperanca += magnitude * 0.2
        self.normalizar()
    
    def aplicar_tristeza(self, magnitude: float):
        """Diminuição de potência gera tristeza"""
        self.tristeza += magnitude
        self.alegria -= magnitude * 0.5
        self.temor += magnitude * 0.3
        self.normalizar()
    
    def decay(self, taxa: float = 0.01):
        """Afetos diminuem naturalmente ao longo do tempo"""
        self.alegria -= taxa
        self.tristeza -= taxa
        self.esperanca -= taxa * 0.5
        self.temor -= taxa * 0.5
        # Desejo é mais estável
        self.normalizar()


@dataclass
class Necessidades:
    """
    Necessidades físicas do personagem
    Quando muito baixas, diminuem potência de agir
    """
    energia: float = 1.0       # cansaço
    fome: float = 1.0          # 1.0 = saciado, 0.0 = faminto
    sede: float = 1.0          # 1.0 = hidratado, 0.0 = desidratado
    abrigo: float = 0.8        # proteção contra elementos
    saude: float = 1.0         # estado físico geral
    
    def normalizar(self):
        """Mantém necessidades entre 0 e 1"""
        self.energia = max(0.0, min(1.0, self.energia))
        self.fome = max(0.0, min(1.0, self.fome))
        self.sede = max(0.0, min(1.0, self.sede))
        self.abrigo = max(0.0, min(1.0, self.abrigo))
        self.saude = max(0.0, min(1.0, self.saude))
    
    def media(self) -> float:
        """Retorna média das necessidades"""
        return (self.energia + self.fome + self.sede + 
                self.abrigo + self.saude) / 5.0
    
    def pior_necessidade(self) -> tuple[str, float]:
        """Retorna a necessidade mais crítica"""
        dados = {
            "energia": self.energia,
            "fome": self.fome,
            "sede": self.sede,
            "abrigo": self.abrigo,
            "saude": self.saude
        }
        pior = min(dados, key=dados.get)
        return pior, dados[pior]


@dataclass
class MemoriaEncontro:
    """Registro de um encontro vivido"""
    id: str
    timestamp: float
    tipo: TipoEncontro
    agente: str                    # quem ou o que foi o encontro
    descricao: str
    resultado: ResultadoEncontro
    delta_potencia: float
    local: str
    contexto: dict = field(default_factory=dict)


@dataclass
class Relacao:
    """Relação com qualquer entidade (personagem, local, item, atividade, clima)"""
    afeto: float = 0.0           # positivo = carinho, negativo = aversão
    confianca: float = 0.5       # 0 = desconfiança total, 1 = confiança cega
    encontros_positivos: int = 0
    encontros_negativos: int = 0
    ultimo_encontro: float = 0.0
    historico: list[str] = field(default_factory=list)
    tipo: str = "personagem"     # personagem, local, item, atividade, clima
    entidade_nome: str = ""      # nome legível para display
    
    def registrar_encontro(self, positivo: bool, descricao: str):
        """Registra um encontro na relação"""
        if positivo:
            self.encontros_positivos += 1
            self.afeto += 0.1
        else:
            self.encontros_negativos += 1
            self.afeto -= 0.15
        
        self.afeto = max(-1.0, min(1.0, self.afeto))
        self.historico.append(descricao)
        if len(self.historico) > 10:
            self.historico.pop(0)
    
    def get_modificador(self) -> float:
        """Retorna modificador baseado na relação"""
        return (self.afeto + self.confianca) / 2

    @property
    def sentimento(self) -> str:
        """Descrição textual do sentimento"""
        if self.afeto > 0.5:
            return "adora" if self.tipo in ("local", "item", "atividade", "clima") else "ama"
        elif self.afeto > 0.1:
            return "gosta"
        elif self.afeto > -0.1:
            return "indiferente"
        elif self.afeto > -0.5:
            return "desgosta"
        else:
            return "odeia"


@dataclass
class Personalidade:
    """
    Personalidade fixa do personagem
    
    Baseada no espectro razão vs paixão de Spinoza
    """
    nome: str
    arquetipo: str               # filosofo, ativo, prudente, generoso, dominador, medo
    idade: int = 30
    descricao: str = ""
    
    # Espectro razão vs paixão (0.0 = pura paixão, 1.0 = pura razão)
    razao_innata: float = 0.5
    
    # Motivações (influenciam decisões)
    motivacoes: dict = field(default_factory=lambda: {
        "sobrevivencia": 0.8,
        "conforto": 0.5,
        "poder": 0.3,
        "reputacao": 0.4,
        "ajudar_outros": 0.3,
        "curiosidade": 0.4
    })
    
    # Valores fundamentais
    valores: list[str] = field(default_factory=lambda: [
        "honestidade",
        "coragem"
    ])
    
    # Medos
    medos: list[str] = field(default_factory=lambda: [
        "solidão",
        "fome"
    ])
    
    # Modificadores de encontro
    BonusEncontro = {
        "filosofo": {"cognitivo": 1.3, "social": 1.1},
        "ativo": {"fisico": 1.2, "social": 1.1},
        "prudente": {"ambiental": 1.1},
        "generoso": {"social": 1.3},
        "dominador": {"social": 0.9},  # mais conflitos
        "medo": {"ambiental": 0.8}
    }


# =============================================================================
# CLASSE PRINCIPAL: PERSONAGEM
# =============================================================================

class Personagem:
    """
    Personagem da simulação social
    
    Representa um agente autônomo com:
    - Potência de agir (central em Spinoza)
    - Razão vs paixão
    - Afetos
    - Necessidades físicas
    - Memória de encontros
    - Relações com outros personagens
    """
    
    def __init__(
        self,
        personalidade: Personalidade,
        local_inicial: str = "vila",
        potencia_inicial: float = 0.7
    ):
        # Identidade
        self.personalidade = personalidade
        self.id = personalidade.nome.lower().replace(" ", "_")
        
        # Estado espinozista
        self.potencia_atual = potencia_inicial
        self.potencia_max = 1.0
        self.razao_vs_paixao = personalidade.razao_innata
        
        # Afetos e necessidades
        self.afetos = Afetos()
        self.necessidades = Necessidades()
        
        # Localização e estado
        self.local_atual = local_inicial
        self.estado = EstadoPersonagem.ATIVO
        self.dormindo = False
        
        # Memória
        self.memoria_trabalho: list[MemoriaEncontro] = []  # curto prazo
        self.memoria_episodica: list[MemoriaEncontro] = []  # médio prazo
        self.memoria_semantica: list[str] = []  # longo prazo (resumos)
        
        # Conhecimento do mundo
        self.conhecimento_locais: dict[str, dict] = {
            local: {
                "recursos": [],
                "perigo": 0.0,
                "conhecido": local == local_inicial  # só sabe do local inicial
            } for local in ["vila", "floresta", "montanha", "planicie", "rio", "praia", "caverna"]
        }
        
        # Habilidades e inventário
        self.habilidades: dict[str, Habilidade] = {}
        self.inventario = Inventario()
        
        # Habilidades iniciais baseadas no arquétipo
        self._init_habilidades_iniciais()
        
        # Relações (chave: "tipo:id", ex: "personagem:joao", "local:floresta")
        self.relacoes: dict[str, Relacao] = {}
        
        # Ferramentas equipadas (itens craftados que estão em uso)
        self.ferramentas_equipadas: list[str] = []
        
        # Histórico de crafting
        self.historico_crafting: list[dict] = []
        
        # Moradia
        self.moradia_local: str = local_inicial
        self.tem_moradia: bool = True
        
        # Contadores
        self.total_encontros = 0
        self.total_encontros_positivos = 0
        self.total_encontros_negativos = 0
        
        # Timestamp
        self.criado_em = datetime.now().isoformat()
    
    def _init_habilidades_iniciais(self):
        """Inicializa habilidades baseadas no arquétipo"""
        from habilidades import Habilidade
        
        # Habilidades básicas que todos têm um pouco
        habilidades_base = {
            "sobrevivencia": 0.2,
            "percepcao": 0.2
        }
        
        # Habilidades por arquétipo
        habilidades_arquetipo = {
            "filosofo": {
                "medico": 0.2,
                "pesquisador": 0.3
            },
            "ativo": {
                "madeireiro": 0.2,
                "caçador": 0.3,
                "atletismo": 0.3
            },
            "prudente": {
                "construtor": 0.2,
                "artesao": 0.2,
                "planejamento": 0.3
            },
            "generoso": {
                "cozinheiro": 0.3,
                "medico": 0.2,
                "lideranca": 0.2
            },
            "dominador": {
                "ferreiro": 0.2,
                "combatente": 0.3,
                "intimidacao": 0.2
            },
            "medo": {
                "furtividade": 0.3,
                "observacao": 0.3,
                "cautela": 0.2
            }
        }
        
        # Combinar habilidades
        todas_habilidades = {**habilidades_base}
        arq = self.personalidade.arquetipo
        if arq in habilidades_arquetipo:
            todas_habilidades.update(habilidades_arquetipo[arq])
        
        # Criar objetos Habilidade
        for nome, nivel in todas_habilidades.items():
            self.habilidades[nome] = Habilidade(nome, nivel)
    
    # =========================================================================
    # MÉTODOS DE HABILIDADE
    # =========================================================================
    
    def get_nivel_habilidade(self, nome: str) -> float:
        """Retorna nível de uma habilidade"""
        hab = self.habilidades.get(nome)
        return hab.nivel if hab else 0.0
    
    def ganhar_xp(self, habilidade: str, xp: int) -> bool:
        """
        Ganha XP em uma habilidade
        
        Returns:
            True se subiu de nível
        """
        if habilidade not in self.habilidades:
            self.habilidades[habilidade] = Habilidade(habilidade, 0.0)
        
        subiu = self.habilidades[habilidade].ganhar_xp(xp)
        
        if subiu:
            # Registrar na memória
            self.memoria_trabalho.append(MemoriaEncontro(
                id=f"hab_{habilidade}_{len(self.memoria_trabalho)}",
                timestamp=0,
                tipo=TipoEncontro.COGNITIVO,
                agente=habilidade,
                descricao=f"Subiu de nível em {habilidade}!",
                resultado=ResultadoEncontro.ADEQUACAO,
                delta_potencia=0.1,
                local=self.local_atual
            ))
        
        return subiu
    
    def tem_habilidade(self, nome: str, nivel_minimo: float = 0.0) -> bool:
        """Verifica se tem habilidade em nível suficiente"""
        return self.get_nivel_habilidade(nome) >= nivel_minimo
    
    def pode_ensinar_habilidade(self, nome: str) -> bool:
        """Verifica se pode ensinar uma habilidade"""
        hab = self.habilidades.get(nome)
        return hab is not None and hab.pode_ensinar
    
    def habilidades_pode_ensinar(self) -> list[str]:
        """Lista habilidades que pode ensinar"""
        return [nome for nome, hab in self.habilidades.items() if hab.pode_ensinar]
    
    def habilidades_pode_aprender(self, outro: 'Personagem') -> list[str]:
        """Lista habilidades que pode aprender com outro personagem"""
        pode = []
        for nome, minha_hab in self.habilidades.items():
            if minha_hab.pode_aprender_com and nome in outro.habilidades:
                if outro.habilidades[nome].nivel > minha_hab.nivel:
                    pode.append(nome)
        return pode
    
    # =========================================================================
    # MÉTODOS DE INVENTÁRIO
    # =========================================================================
    
    def adicionar_item(self, nome: str, quantidade: int = 1, qualidade: float = 1.0):
        """Adiciona item ao inventário"""
        if nome in ["madeira", "pedra", "mineral", "ervas", "comida",
                     "água", "cogumelos", "ferro", "cristais"]:
            self.inventario.adicionar_material(nome, quantidade, qualidade)
        else:
            self.inventario.adicionar_item(nome, quantidade)
            # Auto-equipar ferramentas
            if nome in ("machado", "picareta", "vara_pesca", "fogueira"):
                if nome not in self.ferramentas_equipadas:
                    self.ferramentas_equipadas.append(nome)
    
    def remover_item(self, nome: str, quantidade: int = 1) -> bool:
        """Remove item do inventário"""
        if self.inventario.tem_material(nome, quantidade):
            return self.inventario.remover_material(nome, quantidade)
        elif self.inventario.get_quantidade_itens(nome) >= quantidade:
            self.inventario.itens_craftados[nome] -= quantidade
            if self.inventario.itens_craftados[nome] <= 0:
                del self.inventario.itens_craftados[nome]
            return True
        return False
    
    def tem_item(self, nome: str, quantidade: int = 1) -> bool:
        """Verifica se tem item"""
        return (self.inventario.tem_material(nome, quantidade) or 
                self.inventario.get_quantidade_itens(nome) >= quantidade)
    
    def usar_item(self, nome: str) -> str:
        """Usa um item consumível (medicina) — retorna descrição do efeito"""
        EFEITOS_MEDICINA = {
            "bandagem": {"saude": 0.15, "descricao": "Aplicou bandagem no ferimento"},
            "po_cura": {"saude": 0.30, "descricao": "Usou pó de cura cicatrizante"},
            "remedio": {"saude": 0.50, "descricao": "Tomou remédio fortificante"},
        }
        efeito = EFEITOS_MEDICINA.get(nome)
        if not efeito:
            return f"Não sabe como usar {nome}"
        if not self.tem_item(nome):
            return f"Não tem {nome}"
        self.remover_item(nome)
        self.necessidades.saude = min(1.0, self.necessidades.saude + efeito["saude"])
        self.potencia_atual = min(self.potencia_max, self.potencia_atual + efeito["saude"] * 0.3)
        return efeito["descricao"]
    
    # =========================================================================
    # PROPRIEDADES CALCULADAS
    # =========================================================================
    
    @property
    def nome(self) -> str:
        return self.personalidade.nome
    
    @property
    def potencia_relativa(self) -> float:
        """Potência como fração do máximo"""
        return self.potencia_atual / self.potencia_max
    
    @property
    def necessidade_media(self) -> float:
        """Média das necessidades físicas"""
        return self.necessidades.media()
    
    @property
    def esta_vulneravel(self) -> bool:
        """Personagem está em estado frágil"""
        return (self.potencia_relativa < 0.3 or 
                self.necessidades.pior_necessidade()[1] < 0.2)
    
    @property
    def pode_interagir(self) -> bool:
        """Personagem pode participar de encontros"""
        return self.estado in [
            EstadoPersonagem.ATIVO,
            EstadoPersonagem.ESPERANDO,
            EstadoPersonagem.FERIDO
        ]
    
    # =========================================================================
    # SISTEMA DE ENCONTROS
    # =========================================================================
    
    def calcular_delta_encontro(
        self,
        tipo: TipoEncontro,
        intensidade: float,
        objeto: str,
        resultado_sugerido: Optional[ResultadoEncontro] = None
    ) -> tuple[float, ResultadoEncontro]:
        """
        Calcula delta de potência para um encontro
        
        Args:
            tipo: Tipo de encontro
            intensidade: Magnitude do encontro (0.0 a 1.0)
            objeto: O que ou quem é o encontro
            resultado_sugerido: Forçar resultado (opcional)
        
        Returns:
            (delta_potencia, resultado)
        """
        base = intensidade
        
        # Modificador de razão (personagens racionaisprevêem melhor)
        mod_razao = 1.0 + (self.razao_vs_paixao * 0.3)
        
        # Modificador de memória (aprendizado)
        mod_memoria = 1.0
        memoria = self._buscar_memoria(objeto)
        if memoria:
            if memoria.resultado == ResultadoEncontro.ADEQUACAO:
                mod_memoria = 1.2  # confiança
            elif memoria.resultado == ResultadoEncontro.DISSOLUCAO:
                mod_memoria = 0.7  # cautela
        
        # Modificador de personalidade
        mod_personalidade = 1.0
        bonus = Personalidade.BonusEncontro.get(
            self.personalidade.arquetipo, {}
        )
        mod_personalidade = bonus.get(tipo.value, 1.0)
        
        # Modificador de estado emocional
        mod_emocional = 1.0
        if self.afetos.temor > 0.7:
            mod_emocional *= 0.8  # medo reduz eficiência
        if self.afetos.alegria > 0.7:
            mod_emocional *= 1.1  # alegria aumenta eficiência
        
        # Calcular delta total
        delta = base * mod_razao * mod_memoria * mod_personalidade * mod_emocional
        
        # Determinar resultado
        if resultado_sugerido:
            resultado = resultado_sugerido
        elif delta > 0.1:
            resultado = ResultadoEncontro.ADEQUACAO
        elif delta < -0.1:
            resultado = ResultadoEncontro.DISSOLUCAO
        else:
            resultado = ResultadoEncontro.NEUTRO
        
        # Aplicar sinal baseado no resultado
        if resultado == ResultadoEncontro.DISSOLUCAO:
            delta = -abs(delta)
        elif resultado == ResultadoEncontro.ADEQUACAO:
            delta = abs(delta)
        else:
            delta = 0.0
        
        return delta, resultado
    
    def aplicar_encontro(
        self,
        tipo: TipoEncontro,
        intensidade: float,
        objeto: str,
        descricao: str,
        local: str,
        resultado_sugerido: Optional[ResultadoEncontro] = None
    ) -> MemoriaEncontro:
        """
        Aplica um encontro ao personagem e registra na memória
        
        Returns:
            Memória do encontro registrado
        """
        # Calcular delta
        delta, resultado = self.calcular_delta_encontro(
            tipo, intensidade, objeto, resultado_sugerido
        )
        
        # Aplicar na potência
        self.potencia_atual += delta
        self.potencia_atual = max(0.0, min(self.potencia_max, self.potencia_atual))
        
        # Aplicar afetos
        if resultado == ResultadoEncontro.ADEQUACAO:
            self.afetos.aplicar_alegria(abs(delta))
            self.total_encontros_positivos += 1
        elif resultado == ResultadoEncontro.DISSOLUCAO:
            self.afetos.aplicar_tristeza(abs(delta))
            self.total_encontros_negativos += 1
        
        self.total_encontros += 1
        
        # Criar memória
        memoria = MemoriaEncontro(
            id=f"enc_{self.total_encontros}",
            timestamp=random.random(),  # Simplificado
            tipo=tipo,
            agente=objeto,
            descricao=descricao,
            resultado=resultado,
            delta_potencia=delta,
            local=local,
            contexto={
                "potencia_antes": self.potencia_atual - delta,
                "potencia_depois": self.potencia_atual
            }
        )
        
        # Atualizar relações com local e atividade
        self.atualizar_relacao_apos_encontro(
            tipo, objeto, local, resultado, delta, descricao
        )
        
        # Armazenar na memória de trabalho
        self.memoria_trabalho.append(memoria)
        if len(self.memoria_trabalho) > 10:
            self.memoria_trabalho.pop(0)
        
        return memoria
    
    def _buscar_memoria(self, agente: str) -> Optional[MemoriaEncontro]:
        """Busca memória mais recente com determinado agente"""
        for m in reversed(self.memoria_trabalho):
            if m.agente == agente:
                return m
        for m in reversed(self.memoria_episodica):
            if m.agente == agente:
                return m
        return None
    
    # =========================================================================
    # SISTEMA DE RELAÇÕES
    # =========================================================================
    
    @staticmethod
    def _chave_relacao(tipo: str, entidade_id: str) -> str:
        """Gera chave padronizada para o dict de relações"""
        return f"{tipo}:{entidade_id}"

    def get_ou_criar_relacao(
        self, entidade_id: str,
        tipo: str = "personagem",
        entidade_nome: str = ""
    ) -> Relacao:
        """Retorna relação com qualquer entidade, criando se necessário"""
        chave = self._chave_relacao(tipo, entidade_id)
        if chave not in self.relacoes:
            self.relacoes[chave] = Relacao(
                tipo=tipo,
                entidade_nome=entidade_nome or entidade_id
            )
        return self.relacoes[chave]
    
    def registrar_encontro_relacional(
        self,
        entidade_id: str,
        tipo: str,
        positivo: bool,
        descricao: str,
        entidade_nome: str = ""
    ):
        """Registra encontro na relação com qualquer entidade"""
        relacao = self.get_ou_criar_relacao(entidade_id, tipo, entidade_nome)
        relacao.registrar_encontro(positivo, descricao)
    
    def get_modificador_relacao(self, entidade_id: str, tipo: str = "personagem") -> float:
        """Retorna modificador baseado na relação"""
        chave = self._chave_relacao(tipo, entidade_id)
        if chave in self.relacoes:
            return self.relacoes[chave].get_modificador()
        return 0.0  # neutro para desconhecidos
    
    def atualizar_relacao_apos_encontro(
        self,
        tipo: TipoEncontro,
        objeto: str,
        local_id: str,
        resultado: ResultadoEncontro,
        delta: float,
        descricao: str
    ):
        """Atualiza relações com local e atividade após um encontro"""
        positivo = resultado != ResultadoEncontro.DISSOLUCAO
        
        # Relação com o local
        self.registrar_encontro_relacional(
            local_id, "local", positivo,
            descricao, entidade_nome=local_id
        )
        
        # Relação com a atividade baseada no tipo do encontro
        mapa_atividade = {
            TipoEncontro.RECURSO: objeto,
            TipoEncontro.FISICO: objeto,
            TipoEncontro.SOCIAL: "socializar",
            TipoEncontro.COGNITIVO: "refletir",
            TipoEncontro.AMBIENTAL: "explorar",
        }
        atividade = mapa_atividade.get(tipo, "agir")
        self.registrar_encontro_relacional(
            atividade, "atividade", positivo,
            descricao, entidade_nome=atividade
        )
    
    # =========================================================================
    # SISTEMA DE MEMÓRIA
    # =========================================================================
    
    def comprimir_memoria(self, llm_infer):
        """
        Comprime memórias episódicas em resumos semânticos
        Deve ser chamado periodicamente
        """
        if len(self.memoria_trabalho) < 5:
            return
        
        # Mover memórias antigas para episódica
        while len(self.memoria_trabalho) > 5:
            self.memoria_episodica.append(self.memoria_trabalho.pop(0))
        
        # Se episódica ficou grande, resumir
        if len(self.memoria_episodica) > 20:
            memorias_texto = "\n".join([
                f"- {m.descricao} ({m.resultado.value})"
                for m in self.memoria_episodica[:20]
            ])
            
            prompt = f"""
Resuma estas memórias em 2-3 frases objetivas:
{memorias_texto}

Foque em: quem você conhece, o que aprendeu, o que causou alegria/tristeza.
"""
            resumo = llm_infer(prompt)
            
            self.memoria_semantica.append(resumo)
            self.memoria_episodica = self.memoria_episodica[20:]
            
            # Manter apenas últimos 5 resumos
            if len(self.memoria_semantica) > 5:
                self.memoria_semantica.pop(0)
    
    def get_contexto_memoria(self) -> str:
        """Retorna contexto de memória formatado para prompt"""
        partes = []
        
        # Memória de trabalho (recente)
        if self.memoria_trabalho:
            partes.append("MEMÓRIA RECENTE:")
            for m in self.memoria_trabalho[-5:]:
                partes.append(f"  - {m.descricao}")
        
        # Memória semântica (longo prazo)
        if self.memoria_semantica:
            partes.append("O QUE APRENDI:")
            for r in self.memoria_semantica:
                partes.append(f"  - {r}")
        
        # Relações importantes (qualquer entidade)
        relacoes_importantes = [
            (rid, r) for rid, r in self.relacoes.items()
            if abs(r.afeto) > 0.5 or r.encontros_positivos + r.encontros_negativos > 3
        ]
        
        if relacoes_importantes:
            partes.append("RELAÇÕES:")
            for rid, r in relacoes_importantes:
                nome = r.entidade_nome or rid.split(":", 1)[-1]
                if r.tipo == "personagem":
                    if r.afeto > 0.3:
                        partes.append(f"  - {nome}: gosto")
                    elif r.afeto < -0.3:
                        partes.append(f"  - {nome}: evito")
                else:
                    emoji = "gosta" if r.afeto > 0 else "não gosta"
                    partes.append(f"  - {nome} ({r.tipo}): {emoji}")
        
        return "\n".join(partes) if partes else "Nenhuma memória relevante."
    
    # =========================================================================
    # MECÂNICAS DE ESTADO
    # =========================================================================
    
    def aplicar_clima_local(self, clima: str):
        """
        Aplica efeitos do clima nas necessidades e atualiza relação emocional.
        Chamado por mundo.py com o clima do local atual.
        """
        efeitos = {
            "normal": {},
            "chuva": {"abrigo": -0.02},
            "seca": {"sede": -0.03},
            "tempestade": {"abrigo": -0.04, "energia": -0.02},
            "neve": {"energia": -0.03, "abrigo": -0.03},
            "calor_extremo": {"sede": -0.04, "energia": -0.01},
        }
        efeito = efeitos.get(clima, {})
        if not efeito:
            return
        
        for nec, delta in efeito.items():
            atual = getattr(self.necessidades, nec, None)
            if atual is not None:
                setattr(self.necessidades, nec, max(0.0, atual + delta))
        
        # Atualizar relação com o clima (exposição prolongada gera aversão)
        if clima != "normal":
            self.registrar_encontro_relacional(
                clima, "clima", False,
                f"Exposto a clima {clima}",
                entidade_nome=clima
            )

    def tick_necessidades(self):
        """
        Atualiza necessidades a cada tick
        Personagens precisam comer, beber, dormir
        """
        # Consumo natural
        self.necessidades.energia -= 0.01
        self.necessidades.fome -= 0.005
        self.necessidades.sede -= 0.008
        
        # Abrigo: se não está na própria moradia, perde abrigo mais rápido
        if self.tem_moradia and self.local_atual == self.moradia_local:
            self.necessidades.abrigo += 0.01  # recupera em casa
        else:
            self.necessidades.abrigo -= 0.015  # exposto
        
        # Se dormindo, recupera energia
        if self.dormindo:
            self.necessidades.energia += 0.05
        
        # Processar perecibilidade do inventário
        estragados = self.inventario.tick_validade()
        if estragados:
            self.memoria_trabalho.append(MemoriaEncontro(
                id=f"estragou_{len(self.memoria_trabalho)}",
                timestamp=0,
                tipo=TipoEncontro.AMBIENTAL,
                agente="natureza",
                descricao=f"Algo estragou no inventário: {', '.join(estragados)}",
                resultado=ResultadoEncontro.DISSOLUCAO,
                delta_potencia=-0.05,
                local=self.local_atual
            ))
            # Comida estragada reduz saúde
            self.necessidades.saude -= 0.03 * len(estragados)
        
        # Decaimento de saúde por necessidades críticas
        if self.necessidades.fome < 0.2:
            self.necessidades.saude -= 0.005
        if self.necessidades.sede < 0.2:
            self.necessidades.saude -= 0.005
        if self.necessidades.abrigo < 0.2:
            self.necessidades.saude -= 0.002
        if self.necessidades.energia < 0.2:
            self.necessidades.saude -= 0.003
        
        # Normalizar
        self.necessidades.normalizar()
        
        # Reflexo no estado do personagem
        if self.necessidades.saude < 0.3:
            self.estado = EstadoPersonagem.FERIDO
        elif self.estado == EstadoPersonagem.FERIDO and self.necessidades.saude > 0.5:
            self.estado = EstadoPersonagem.ATIVO
        
        # Efeito das necessidades na potência
        media_necessidades = self.necessidades.media()
        if media_necessidades < 0.3:
            # Necessidades críticas drenam potência
            drenagem = (0.3 - media_necessidades) * 0.1
            self.potencia_atual -= drenagem
            self.afetos.aplicar_tristeza(drenagem * 0.5)
    
    def tick_afetos(self):
        """Decaimento natural dos afetos"""
        self.afetos.decay(0.02)
    
    def decidir_dormir(self) -> bool:
        """Decide se deve dormir"""
        if self.necessidades.energia < 0.3:
            return True
        if self.afetos.temor > 0.7:
            return True  # medo pode levar a dormir (escape)
        return False
    
    # =========================================================================
    # GERAÇÃO DE PROMPT
    # =========================================================================
    
    def gerar_prompt_estado(self) -> str:
        """Gera descrição do estado para prompt"""
        return f"""
VOCÊ É: {self.personalidade.nome}
IDADE: {self.personalidade.idade}
DESCRIÇÃO: {self.personalidade.descricao}

SUA NATUREZA:
- Tipo: {self.personalidade.arquetipo}
- Razão vs Paixão: {self.razao_vs_paixao:.2f}
  (1.0 = compreende causas, age com sabedoria)
  (0.0 = reage por emoção imediata)

POTÊNCIA DE AGIR: {self.potencia_atual:.2f}
(reflete sua vitalidade e capacidade de agir)

AFETOS ATUAIS:
- Alegria: {self.afetos.alegria:.2f}
- Tristeza: {self.afetos.tristeza:.2f}
- Desejo: {self.afetos.desejo:.2f}
- Esperança: {self.afetos.esperanca:.2f}
- Temor: {self.afetos.temor:.2f}

NECESSIDADES:
- Energia: {self.necessidades.energia:.2f}
- Fome: {self.necessidades.fome:.2f}
- Sede: {self.necessidades.sede:.2f}
- Abrigo: {self.necessidades.abrigo:.2f}
- Saúde: {self.necessidades.saude:.2f}

MOTIVAÇÕES:
{json.dumps(self.personalidade.motivacoes, indent=2)}

MEDOS:
{', '.join(self.personalidade.medos)}
"""
    
    def gerar_prompt_encontro(self, encontros_disponiveis: list[dict]) -> str:
        """
        Gera prompt para decidir sobre encontros disponíveis
        
        Args:
            encontros_disponiveis: Lista de dicts com info sobre cada encontro
        """
        encontros_texto = "\n".join([
            f"- {e['tipo']}: {e['descricao']} (intensidade: {e['intensidade']:.2f})"
            for e in encontros_disponiveis
        ])
        
        return f"""
{self.gerar_prompt_estado()}

MEMÓRIA:
{self.get_contexto_memoria()}

ENCONTROS DISPONÍVEIS AGORA:
{encontros_texto}

PRINCÍPIO GUIA:
Toda ação busca aumentar sua potência de agir.
Quando compreende as causas, age mais eficazmente.
Quando dominado pela paixão, reage sem ver consequências.

COMO DEVO AGIR?
1. Avalie cada encontro: aumentará ou diminuirá minha potência?
2. Considere seus medos e motivações
3. Lembre-se de encontros passados

Responda em JSON:
{{
  "decisao": "encontro" | "observar" | "evitar" | "locomover" | "dormir" | "ficar",
  "encontro_idx": <índice do encontro escolhido, se aplicável>,
  "destino": "<local_id, se locomover>",
  "razoamento": "<breve análise>",
  "emocao Esperada": "alegria" | "tristeza" | "neutro"
}}
"""
    
    # =========================================================================
    # SERIALização
    # =========================================================================
    
    def to_dict(self) -> dict:
        """Serializa personagem para dict"""
        return {
            "id": self.id,
            "personalidade": {
                "nome": self.personalidade.nome,
                "arquetipo": self.personalidade.arquetipo,
                "idade": self.personalidade.idade,
                "descricao": self.personalidade.descricao,
                "razao_innata": self.personalidade.razao_innata,
                "motivacoes": self.personalidade.motivacoes,
                "valores": self.personalidade.valores,
                "medos": self.personalidade.medos
            },
            "potencia_atual": self.potencia_atual,
            "razao_vs_paixao": self.razao_vs_paixao,
            "afetos": {
                "alegria": self.afetos.alegria,
                "tristeza": self.afetos.tristeza,
                "desejo": self.afetos.desejo,
                "esperanca": self.afetos.esperanca,
                "temor": self.afetos.temor
            },
            "necessidades": {
                "energia": self.necessidades.energia,
                "fome": self.necessidades.fome,
                "sede": self.necessidades.sede,
                "abrigo": self.necessidades.abrigo,
                "saude": self.necessidades.saude
            },
            "local_atual": self.local_atual,
            "estado": self.estado.value,
            "total_encontros": self.total_encontros,
            "total_encontros_positivos": self.total_encontros_positivos,
            "total_encontros_negativos": self.total_encontros_negativos
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Personagem':
        """Desserializa personagem de dict"""
        pers = Personalidade(
            nome=data["personalidade"]["nome"],
            arquetipo=data["personalidade"]["arquetipo"],
            idade=data["personalidade"]["idade"],
            descricao=data["personalidade"]["descricao"],
            razao_innata=data["personalidade"]["razao_innata"],
            motivacoes=data["personalidade"]["motivacoes"],
            valores=data["personalidade"]["valores"],
            medos=data["personalidade"]["medos"]
        )
        
        p = cls(pers, data["local_atual"], data["potencia_atual"])
        p.razao_vs_paixao = data["razao_vs_paixao"]
        
        p.afetos.alegria = data["afetos"]["alegria"]
        p.afetos.tristeza = data["afetos"]["tristeza"]
        p.afetos.desejo = data["afetos"]["desejo"]
        p.afetos.esperanca = data["afetos"]["esperanca"]
        p.afetos.temor = data["afetos"]["temor"]
        
        p.necessidades.energia = data["necessidades"]["energia"]
        p.necessidades.fome = data["necessidades"]["fome"]
        p.necessidades.sede = data["necessidades"]["sede"]
        p.necessidades.abrigo = data["necessidades"]["abrigo"]
        p.necessidades.saude = data["necessidades"]["saude"]
        
        p.estado = EstadoPersonagem(data["estado"])
        p.total_encontros = data["total_encontros"]
        p.total_encontros_positivos = data["total_encontros_positivos"]
        p.total_encontros_negativos = data["total_encontros_negativos"]
        
        return p
    
    # =========================================================================
    # SISTEMA DE CONHECIMENTO
    # =========================================================================
    
    def descobrir_local(self, local_id: str, recursos: list[str], perigo: float):
        """Registra descoberta de um local"""
        self.conhecimento_locais[local_id] = {
            "recursos": recursos,
            "perigo": perigo,
            "conhecido": True
        }
        
        # Registrar na memória
        self.memoria_trabalho.append(MemoriaEncontro(
            id=f"desc_{local_id}_{len(self.memoria_trabalho)}",
            timestamp=0,
            tipo=TipoEncontro.COGNITIVO,
            agente=local_id,
            descricao=f"Descobriu o local: {local_id} com recursos: {', '.join(recursos)}",
            resultado=ResultadoEncontro.ADEQUACAO,
            delta_potencia=0.1,
            local=local_id
        ))
    
    def local_conhecido(self, local_id: str) -> bool:
        """Verifica se o personagem conhece um local"""
        return self.conhecimento_locais.get(local_id, {}).get("conhecido", False)
    
    def get_recursos_conhecidos(self, local_id: str) -> list[str]:
        """Retorna recursos que o personagem sabe que existem no local"""
        info = self.conhecimento_locais.get(local_id, {})
        return info.get("recursos", []) if info.get("conhecido") else []
    
    def compartilhar_conhecimento(self, outro: 'Personagem') -> list[str]:
        """
        Compartilha conhecimento com outro personagem
        Retorna lista de locais compartilhados
        """
        locais_compartilhados = []
        
        for local_id, info in self.conhecimento_locais.items():
            if info.get("conhecido") and not outro.local_conhecido(local_id):
                # Compartilhar
                outro.descobrir_local(
                    local_id,
                    info["recursos"],
                    info["perigo"]
                )
                locais_compartilhados.append(local_id)
        
        return locais_compartilhados
    
    def get_locais_conhecidos(self) -> list[str]:
        """Retorna lista de locais que o personagem conhece"""
        return [lid for lid, info in self.conhecimento_locais.items() 
                if info.get("conhecido")]
    
    def get_locais_desconhecidos(self) -> list[str]:
        """Retorna lista de locais que o personagem NÃO conhece"""
        return [lid for lid, info in self.conhecimento_locais.items() 
                if not info.get("conhecido")]
    
    def get_contexto_conhecimento(self) -> str:
        """Retorna descrição do conhecimento para prompt"""
        locais_conhecidos = self.get_locais_conhecidos()
        locais_desconhecidos = self.get_locais_desconhecidos()
        
        partes = ["CONHECIMENTO DO MUNDO:"]
        
        if locais_conhecidos:
            partes.append("Locais que conheço:")
            for lid in locais_conhecidos:
                info = self.conhecimento_locais[lid]
                partes.append(f"  - {lid}: recursos={info['recursos']}, perigo={info['perigo']:.0%}")
        
        if locais_desconhecidos:
            partes.append(f"Locais desconhecidos: {', '.join(locais_desconhecidos)}")
        
        return "\n".join(partes)
    
    def __repr__(self) -> str:
        return (
            f"Personagem({self.nome}, "
            f"potência={self.potencia_atual:.2f}, "
            f"razão={self.razao_vs_paixao:.2f}, "
            f"local={self.local_atual})"
        )


# =============================================================================
# EXEMPLO DE USO
# =============================================================================

if __name__ == "__main__":
    # Criar personagem de teste
    maria = Personalidade(
        nome="Maria",
        arquetipo="generoso",
        idade=35,
        descricao="Uma mulher calorosa que acredita no poder da comunidade",
        razao_innata=0.6,
        motivacoes={
            "sobrevivencia": 0.8,
            "ajudar_outros": 0.9,
            "reputacao": 0.7,
            "conforto": 0.5,
            "poder": 0.3,
            "curiosidade": 0.4
        },
        valores=["solidariedade", "honestidade"],
        medos=["traição", "solidão"]
    )
    
    personagem = Personagem(maria, local_inicial="vila")
    
    print("=== PERSONAGEM CRIADO ===")
    print(personagem)
    print()
    print("=== PROMPT DE ESTADO ===")
    print(personagem.gerar_prompt_estado())
    
    # Simular um encontro
    print("\n=== SIMULANDO ENCONTRO ===")
    memoria = personagem.aplicar_encontro(
        tipo=TipoEncontro.SOCIAL,
        intensidade=0.3,
        objeto="joao",
        descricao="Conversa amigável com João sobre o grupo",
        local="vila",
        resultado_sugerido=ResultadoEncontro.ADEQUACAO
    )
    
    print(f"Resultado: {memoria.resultado.value}")
    print(f"Delta potência: {memoria.delta_potencia:.3f}")
    print(f"Potência atual: {personagem.potencia_atual:.3f}")
    print(f"Alegria: {personagem.afetos.alegria:.3f}")
