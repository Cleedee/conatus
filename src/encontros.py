"""
Módulo de Encontros — Motor de Simulação Espinozista

Gerencia todos os encontros possíveis na simulação:
- Encontros com recursos/objetos
- Encontros sociais (entre personagens)
- Encontros ambientais (clima, eventos)
- Encontros observacionais (ver outros interagirem)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable
import random
from datetime import datetime

from personagem import (
    Personagem,
    TipoEncontro,
    ResultadoEncontro,
    EstadoPersonagem
)


# =============================================================================
# ENUMS E TIPOS
# =============================================================================

class OrigemEncontro(Enum):
    """De onde vem o encontro"""
    RECURSO = "recurso"          # interação com objeto/ambiente
    SOCIAL = "social"            # outro personagem inicia
    AMBIENTAL = "ambiental"      # evento do mundo
    OBSERVACIONAL = "observacional"  # personagem observa


class DisponibilidadeEncontro(Enum):
    """Quão disponível está o encontro"""
    SEMPRE = "sempre"           # sempre disponível
    SITUACIONAL = "situacional" # depende de estado
    RARO = "raro"               # chance baixa
    UNICO = "unico"             # só uma vez


# =============================================================================
# ESTRUTURAS DE ENCONTRO
# =============================================================================

@dataclass
class EncontroDisponivel:
    """
    Representa um encontro potencial que um personagem pode ter
    """
    id: str
    origem: OrigemEncontro
    tipo: TipoEncontro
    
    # O que/ quem é o encontro
    objeto: str                    # ID do objeto/personagem
    descricao: str                 # Descrição legível
    
    # Parâmetros
    intensidade: float             # 0.0 a 1.0
    disponibilidade: DisponibilidadeEncontro
    
    # Condições
    requer_local: Optional[str] = None
    requer_hora: Optional[tuple[int, int]] = None  # (min, max)
    requer_estado: Optional[EstadoPersonagem] = None
    requer_necessidade: Optional[tuple[str, float]] = None  # (necessidade, max_value)
    requer_ferramenta: Optional[str] = None
    
    # Consequências pré-definidas (podem ser modificadas)
    resultado_sugerido: Optional[ResultadoEncontro] = None
    
    # Para encontros sociais
    personagem_origem: Optional[str] = None  # quem initiate
    
    # Metadata
    peso: float = 1.0              # probabilidade relativa
    tag: str = ""                  # para filtragem


@dataclass
class ResultadoEncontroProcessado:
    """
    Resultado após processar um encontro
    """
    encontro: EncontroDisponivel
    resultado: ResultadoEncontro
    delta_potencia: float
    sucesso: bool
    
    # Efeitos colaterais
    mudanca_local: Optional[str] = None
    perda_recurso: Optional[str] = None
    ganho_recurso: Optional[str] = None
    mudanca_estado: Optional[EstadoPersonagem] = None
    
    # Consumo de recurso local (nome da quantidade no mapa)
    recurso_consumido: Optional[str] = None
    recurso_quantidade: float = 0.0
    
    # Depósito (colocar recurso de volta no local)
    recurso_depositado: Optional[str] = None
    recurso_depositado_qtd: float = 0.0
    
    # Dano à saúde (causado por perigo, ferimentos, etc.)
    dano_saude: float = 0.0
    
    # Para logging
    detalhes: str = ""
    

@dataclass
class EventoMundo:
    """
    Evento que afeta o mundo (gera encontros ambientais)
    """
    id: str
    nome: str
    descricao: str
    intensidade: float
    
    # Efeitos nos locais
    locais_afetados: list[str]
    duracao: int                    # ticks
    tick_atual: int = 0
    
    # Gera quais tipos de encontro
    tipos_encontro: list[TipoEncontro] = field(default_factory=lambda: [
        TipoEncontro.AMBIENTAL
    ])
    
    def avancar_tick(self):
        self.tick_atual += 1
    
    @property
    def ativo(self) -> bool:
        return self.tick_atual < self.duracao


# =============================================================================
# GERADOR DE ENCONTROS
# =============================================================================

class GeradorEncontros:
    """
    Gera encontros disponíveis baseado no estado do mundo
    """
    
    def __init__(self):
        # Templates de encontros por tipo de local
        self.templates_local: dict[str, list[dict]] = {
            "vila": [
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "comida_comun",
                    "descricao": "Pegar comida do depósito comum",
                    "intensidade": 0.2,
                    "tag": "sobrevivencia"
                },
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "poço",
                    "descricao": "Buscar água no poço",
                    "intensidade": 0.15,
                    "tag": "sobrevivencia"
                },
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "madeira",
                    "descricao": "Cortar madeira no bosque próximo",
                    "intensidade": 0.2,
                    "requer_necessidade": ("energia", 0.4),
                    "requer_ferramenta": "machado",
                    "tag": "recurso"
                },
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "oficina",
                    "descricao": "Usar ferramentas na oficina",
                    "intensidade": 0.25,
                    "requer_necessidade": ("energia", 0.5),
                    "tag": "producao"
                },
                {
                    "tipo": TipoEncontro.COGNITIVO,
                    "objeto": "reflexao",
                    "descricao": "Sentar e refletir sobre a vida",
                    "intensidade": 0.1,
                    "tag": "crescimento"
                }
            ],
            "floresta": [
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "madeira",
                    "descricao": "Cortar madeira para construção",
                    "intensidade": 0.3,
                    "requer_necessidade": ("energia", 0.4),
                    "requer_ferramenta": "machado",
                    "tag": "recurso"
                },
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "caça",
                    "descricao": "Caçar animais pequenos",
                    "intensidade": 0.35,
                    "requer_necessidade": ("energia", 0.5),
                    "tag": "alimento"
                },
                {
                    "tipo": TipoEncontro.AMBIENTAL,
                    "objeto": "natureza",
                    "descricao": "Caminhar entre as árvores",
                    "intensidade": 0.1,
                    "resultado_sugerido": ResultadoEncontro.ADEQUACAO,
                    "tag": "bem_estar"
                },
                {
                    "tipo": TipoEncontro.AMBIENTAL,
                    "objeto": "perigo_floresta",
                    "descricao": "Encontrar trilha perigosa",
                    "intensidade": 0.2,
                    "resultado_sugerido": ResultadoEncontro.DISSOLUCAO,
                    "tag": "risco"
                }
            ],
            "rio": [
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "peixe",
                    "descricao": "Pescar no rio",
                    "intensidade": 0.25,
                    "requer_necessidade": ("energia", 0.4),
                    "requer_ferramenta": "vara_pesca",
                    "tag": "alimento"
                },
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "agua_fresca",
                    "descricao": "Beber água fresca do rio",
                    "intensidade": 0.2,
                    "tag": "sobrevivencia"
                },
                {
                    "tipo": TipoEncontro.AMBIENTAL,
                    "objeto": "correnteza",
                    "descricao": "Nadar na correnteza",
                    "intensidade": 0.15,
                    "requer_necessidade": ("energia", 0.6),
                    "tag": "aventura"
                }
            ],
            "montanha": [
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "pedra",
                    "descricao": "Coletar pedras resistentes",
                    "intensidade": 0.3,
                    "requer_necessidade": ("energia", 0.5),
                    "requer_ferramenta": "picareta",
                    "tag": "recurso"
                },
                {
                    "tipo": TipoEncontro.COGNITIVO,
                    "objeto": "vista_panoramica",
                    "descricao": "Observar a paisagem do topo",
                    "intensidade": 0.2,
                    "tag": "sabedoria"
                },
                {
                    "tipo": TipoEncontro.AMBIENTAL,
                    "objeto": "altitude",
                    "descricao": "Lidar com ar rarefeito",
                    "intensidade": 0.15,
                    "resultado_sugerido": ResultadoEncontro.DISSOLUCAO,
                    "tag": "desafio"
                }
            ],
            "caverna": [
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "mineral",
                    "descricao": "Minerar minerais preciosos",
                    "intensidade": 0.35,
                    "requer_necessidade": ("energia", 0.6),
                    "requer_ferramenta": "picareta",
                    "tag": "recurso"
                },
                {
                    "tipo": TipoEncontro.AMBIENTAL,
                    "objeto": "escuridao",
                    "descricao": "Explorar os túneis escuros",
                    "intensidade": 0.2,
                    "tag": "aventura"
                },
                {
                    "tipo": TipoEncontro.AMBIENTAL,
                    "objeto": "frio_umido",
                    "descricao": "Lidar com frio e umidade",
                    "intensidade": 0.15,
                    "resultado_sugerido": ResultadoEncontro.DISSOLUCAO,
                    "tag": "desconforto"
                }
            ],
            "planicie": [
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "colheita",
                    "descricao": "Colher plantações",
                    "intensidade": 0.25,
                    "tag": "alimento"
                },
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "ervas_medicinais",
                    "descricao": "Buscar ervas medicinais",
                    "intensidade": 0.2,
                    "tag": "saude"
                },
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "grama",
                    "descricao": "Colher grama para artesanato",
                    "intensidade": 0.15,
                    "tag": "recurso"
                },
                {
                    "tipo": TipoEncontro.AMBIENTAL,
                    "objeto": "sol_forte",
                    "descricao": "Expor-se ao sol forte",
                    "intensidade": 0.1,
                    "requer_hora": (6, 20),
                    "tag": "clima"
                }
            ],
            "praia": [
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "marisco",
                    "descricao": "Coletar mariscos na costa",
                    "intensidade": 0.2,
                    "tag": "alimento"
                },
                {
                    "tipo": TipoEncontro.AMBIENTAL,
                    "objeto": "ondas",
                    "descricao": "Nadar nas ondas",
                    "intensidade": 0.15,
                    "requer_necessidade": ("energia", 0.5),
                    "tag": "lazer"
                },
                {
                    "tipo": TipoEncontro.AMBIENTAL,
                    "objeto": "mare",
                    "descricao": "Cuidado com a maré alta",
                    "intensidade": 0.2,
                    "resultado_sugerido": ResultadoEncontro.DISSOLUCAO,
                    "tag": "risco"
                }
            ],
            "lago": [
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "peixe",
                    "descricao": "Pescar no lago sereno",
                    "intensidade": 0.2,
                    "requer_necessidade": ("energia", 0.3),
                    "requer_ferramenta": "vara_pesca",
                    "tag": "alimento"
                },
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "agua_fresca",
                    "descricao": "Beber água do lago",
                    "intensidade": 0.15,
                    "tag": "sobrevivencia"
                },
                {
                    "tipo": TipoEncontro.AMBIENTAL,
                    "objeto": "natureza",
                    "descricao": "Meditar à beira do lago",
                    "intensidade": 0.15,
                    "resultado_sugerido": ResultadoEncontro.ADEQUACAO,
                    "tag": "bem_estar"
                }
            ],
            "pantano": [
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "cogumelos",
                    "descricao": "Coletar cogumelos raros",
                    "intensidade": 0.2,
                    "tag": "alimento"
                },
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "ervas_medicinais",
                    "descricao": "Buscar ervas no pântano",
                    "intensidade": 0.25,
                    "tag": "saude"
                },
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "madeira",
                    "descricao": "Cortar madeira podre",
                    "intensidade": 0.2,
                    "requer_necessidade": ("energia", 0.4),
                    "requer_ferramenta": "machado",
                    "tag": "recurso"
                },
                {
                    "tipo": TipoEncontro.AMBIENTAL,
                    "objeto": "perigo_floresta",
                    "descricao": "Evitar criaturas do pântano",
                    "intensidade": 0.3,
                    "resultado_sugerido": ResultadoEncontro.DISSOLUCAO,
                    "tag": "risco"
                }
            ],
            "ruinas": [
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "pedra",
                    "descricao": "Coletar pedras das ruínas",
                    "intensidade": 0.2,
                    "requer_necessidade": ("energia", 0.4),
                    "requer_ferramenta": "picareta",
                    "tag": "recurso"
                },
                {
                    "tipo": TipoEncontro.RECURSO,
                    "objeto": "mineral",
                    "descricao": "Extrair minerais dos escombros",
                    "intensidade": 0.3,
                    "requer_necessidade": ("energia", 0.5),
                    "requer_ferramenta": "picareta",
                    "tag": "recurso"
                },
                {
                    "tipo": TipoEncontro.COGNITIVO,
                    "objeto": "vista_panoramica",
                    "descricao": "Explorar as ruínas antigas",
                    "intensidade": 0.2,
                    "tag": "sabedoria"
                }
            ]
        }
    
    def gerar_encontros_locais(
        self,
        local: str,
        hora: int,
        personagem: Personagem,
        eventos: list[EventoMundo]
    ) -> list[EncontroDisponivel]:
        """
        Gera encontros disponíveis para um personagem num local.
        Inclui alternativas quando há escassez.
        """
        encontros = []
        
        # Mapeamento de necessidades para recursos e locais alternativos
        recursos_necessidade = {
            "comida": {
                "templates": ["comida_comun", "colheita", "caça", "peixe", "marisco"],
                "alternativas": {
                    "floresta": "Caçar animais na floresta",
                    "planicie": "Colher na planície",
                    "rio": "Pescar no rio",
                    "praia": "Coletar mariscos"
                }
            },
            "água": {
                "templates": ["poço", "água_fresca"],
                "alternativas": {
                    "rio": "Beber água fresca do rio",
                    "floresta": "Buscar água em nascentes"
                }
            }
        }
        
        # Encontros base do local
        templates = self.templates_local.get(local, [])
        
        # Rastrear quais tipos de recurso estão disponíveis
        recursos_disponiveis = set()
        
        for i, template in enumerate(templates):
            # Verificar condições
            if not self._verificar_condicoes(template, personagem, hora):
                continue
            
            encontro = EncontroDisponivel(
                id=f"{local}_{template['objeto']}_{i}",
                origem=OrigemEncontro.RECURSO,
                tipo=template["tipo"],
                objeto=template["objeto"],
                descricao=template["descricao"],
                intensidade=template["intensidade"],
                disponibilidade=DisponibilidadeEncontro.SEMPRE,
                requer_local=local,
                resultado_sugerido=template.get("resultado_sugerido"),
                tag=template.get("tag", ""),
                requer_ferramenta=template.get("requer_ferramenta")
            )
            
            encontros.append(encontro)
            
            # Rastrear tipo de recurso
            if "comida" in template.get("objeto", "") or "colheita" in template.get("objeto", ""):
                recursos_disponiveis.add("comida")
            if "água" in template.get("objeto", "") or "poço" in template.get("objeto", ""):
                recursos_disponiveis.add("água")
        
        # Verificar necessidades do personagem e sugerir alternativas
        necessidades_baixas = []
        if personagem.necessidades.fome < 0.4:
            necessidades_baixas.append("comida")
        if personagem.necessidades.sede < 0.4:
            necessidades_baixas.append("água")
        
        # Para cada necessidade baixa, verificar se pode ser atendida localmente
        for necessidade in necessidades_baixas:
            # Verificar se há encontro local que atende essa necessidade
            pode_atender_local = False
            for e in encontros:
                if necessidade == "comida" and e.tag == "sobrevivencia":
                    if any(x in e.objeto for x in ["comida", "colheita", "caça", "peixe"]):
                        pode_atender_local = True
                elif necessidade == "água" and e.tag == "sobrevivencia":
                    if any(x in e.objeto for x in ["água", "poço", "rio"]):
                        pode_atender_local = True
            
            # Se não pode atender localmente, sugerir alternativas
            if not pode_atender_local:
                info = recursos_necessidade.get(necessidade, {})
                alternativas = info.get("alternativas", {})
                
                for local_alt, descricao in alternativas.items():
                    if local_alt != local:
                        encontro = EncontroDisponivel(
                            id=f"ir_buscar_{necessidade}_{local_alt}",
                            origem=OrigemEncontro.RECURSO,
                            tipo=TipoEncontro.FISICO,
                            objeto=f"mover_{local_alt}",
                            descricao=f"{descricao} (falta {necessidade} aqui)",
                            intensidade=0.5,  # urgente
                            disponibilidade=DisponibilidadeEncontro.SEMPRE,
                            tag=f"necessidade_{necessidade}"
                        )
                        encontros.append(encontro)
        
        # SEMPRE oferecer alternativas quando personagem tem necessidade
        # (independente de haver recurso local)
        for necessidade in necessidades_baixas:
            info = recursos_necessidade.get(necessidade, {})
            alternativas = info.get("alternativas", {})
            
            for local_alt, descricao in alternativas.items():
                if local_alt != local:
                    # Verificar se já adicionou
                    ja_existe = any(e.id == f"ir_buscar_{necessidade}_{local_alt}" for e in encontros)
                    if not ja_existe:
                        encontro = EncontroDisponivel(
                            id=f"ir_buscar_{necessidade}_{local_alt}",
                            origem=OrigemEncontro.RECURSO,
                            tipo=TipoEncontro.FISICO,
                            objeto=f"mover_{local_alt}",
                            descricao=f"{descricao} (opção alternativa)",
                            intensidade=0.3,
                            disponibilidade=DisponibilidadeEncontro.SEMPRE,
                            tag=f"alternativa_{necessidade}"
                        )
                        encontros.append(encontro)
        
        # Encontros de eventos ativos
        for evento in eventos:
            if local in evento.locais_afetados and evento.ativo:
                for tipo in evento.tipos_encontro:
                    encontro = EncontroDisponivel(
                        id=f"evento_{evento.id}_{tipo.value}",
                        origem=OrigemEncontro.AMBIENTAL,
                        tipo=tipo,
                        objeto=evento.id,
                        descricao=f"{evento.nome}: {evento.descricao}",
                        intensidade=evento.intensidade,
                        disponibilidade=DisponibilidadeEncontro.SITUACIONAL,
                        tag="evento"
                    )
                    encontros.append(encontro)
        
        return encontros
    
    def gerar_encontros_sociais(
        self,
        personagem: Personagem,
        outros: list[Personagem]
    ) -> list[EncontroDisponivel]:
        """
        Gera encontros sociais disponíveis (outros personagens no mesmo local)
        """
        encontros = []
        
        for outro in outros:
            if outro.id == personagem.id:
                continue
            
            if outro.local_atual != personagem.local_atual:
                continue
            
            if not outro.pode_interagir:
                continue
            
            # Calcular intensidade baseada na relação
            relacao = personagem.get_ou_criar_relacao(outro.id)
            intensidade_base = 0.3
            
            # Relação positiva = mais provável interagir
            if relacao.afeto > 0.3:
                intensidade_base += 0.1
            elif relacao.afeto < -0.3:
                intensidade_base -= 0.1
            
            # Encontro social básico
            encontro = EncontroDisponivel(
                id=f"social_{personagem.id}_{outro.id}",
                origem=OrigemEncontro.SOCIAL,
                tipo=TipoEncontro.SOCIAL,
                objeto=outro.id,
                descricao=f"Falar com {outro.nome}",
                intensidade=intensidade_base,
                disponibilidade=DisponibilidadeEncontro.SEMPRE,
                personagem_origem=outro.id,
                tag="conversa"
            )
            encontros.append(encontro)
            
            # Encontros específicos baseados no estado
            if personagem.esta_vulneravel and relacao.afeto > 0:
                encontro_ajuda = EncontroDisponivel(
                    id=f"ajuda_{personagem.id}_{outro.id}",
                    origem=OrigemEncontro.SOCIAL,
                    tipo=TipoEncontro.SOCIAL,
                    objeto=outro.id,
                    descricao=f"Pedir ajuda para {outro.nome}",
                    intensidade=0.4,
                    disponibilidade=DisponibilidadeEncontro.SITUACIONAL,
                    personagem_origem=outro.id,
                    tag="ajuda"
                )
                encontros.append(encontro_ajuda)
            
            # Encontro de observação (personagem vê outro agindo)
            if random.random() < 0.3:  # 30% de chance
                encontro_observacao = EncontroDisponivel(
                    id=f"obs_{personagem.id}_{outro.id}",
                    origem=OrigemEncontro.OBSERVACIONAL,
                    tipo=TipoEncontro.OBSERVACIONAL,
                    objeto=outro.id,
                    descricao=f"Observar {outro.nome} de longe",
                    intensidade=0.15,
                    disponibilidade=DisponibilidadeEncontro.RARO,
                    tag="observacao"
                )
                encontros.append(encontro_observacao)
        
        return encontros
    
    def _verificar_condicoes(
        self,
        template: dict,
        personagem: Personagem,
        hora: int
    ) -> bool:
        """Verifica se o encontro cumpre condições"""
        
        # Verificar hora
        if "requer_hora" in template:
            min_hora, max_hora = template["requer_hora"]
            if not (min_hora <= hora <= max_hora):
                return False
        
        # Verificar necessidade (valor mínimo necessário)
        if "requer_necessidade" in template:
            nec_nome, nec_min = template["requer_necessidade"]
            nec_atual = getattr(personagem.necessidades, nec_nome, None)
            if nec_atual is not None and nec_atual < nec_min:
                return False
        
        # Verificar estado
        if "requer_estado" in template:
            if personagem.estado != template["requer_estado"]:
                return False
        
        return True


# =============================================================================
# PROCESSADOR DE ENCONTROS
# =============================================================================

class ProcessadorEncontros:
    """
    Processa encontros e aplica seus efeitos
    """
    
    def __init__(self):
        # Mapeamento de encontros para efeitos
        self.efeitos: dict[str, Callable] = {
            "comida_comun": self._efeito_comida,
            "poço": self._efeito_agua,
            "madeira": self._efeito_madeira,
            "caça": self._efeito_caca,
            "peixe": self._efeito_peixe,
            "oficina": self._efeito_oficina,
            "pedra": self._efeito_minerar,
            "mineral": self._efeito_minerar,
        }
    
    def processar(
        self,
        personagem: Personagem,
        encontro: EncontroDisponivel
    ) -> ResultadoEncontroProcessado:
        """
        Processa um encontro e retorna o resultado
        """
        # Verificar se há efeito específico
        efeito_fn = self.efeitos.get(encontro.objeto)
        
        if efeito_fn:
            return efeito_fn(personagem, encontro)
        
        # Processamento genérico
        return self._processar_generico(personagem, encontro)
    
    RECURSOS_COLETAVEIS: dict[str, tuple[str, int]] = {
        "pedra": ("pedra", 2),
        "mineral": ("mineral", 1),
        "colheita": ("colheita", 3),
        "ervas_medicinais": ("ervas", 2),
        "marisco": ("comida", 2),
        "agua_fresca": ("água", 2),
        "cogumelos": ("cogumelos", 2),
        "sal": ("sal", 1),
        "madeira_marinha": ("madeira", 1),
        "pedras_lisas": ("pedra", 1),
        "grama": ("grama", 2),
    }
    
    # Mapeamento objeto_encontro → nome_recurso_local (para consumir do mapa)
    OBJETO_PARA_RECURSO: dict[str, str] = {
        "comida_comun": "comida",
        "poço": "água",
        "madeira": "madeira",
        "caça": "caça",
        "peixe": "peixe",
        "pedra": "pedra",
        "mineral": "mineral",
        "colheita": "colheita",
        "ervas_medicinais": "ervas_medicinais",
        "marisco": "marisco",
        "agua_fresca": "água",
        "cogumelos": "cogumelos",
        "sal": "sal",
        "madeira_marinha": "madeira_marinha",
        "pedras_lisas": "pedras_lisas",
        "grama": "grama",
    }

    def _processar_generico(
        self,
        personagem: Personagem,
        encontro: EncontroDisponivel
    ) -> ResultadoEncontroProcessado:
        """Processamento genérico para encontros sem efeito especial"""
        
        # Verificar se tem ferramenta necessária
        tem_ferramenta = True
        ferramenta_requerida = getattr(encontro, 'requer_ferramenta', None)
        if ferramenta_requerida and not personagem.tem_item(ferramenta_requerida):
            tem_ferramenta = False
        
        # Usar resultado sugerido ou calcular
        resultado = encontro.resultado_sugerido
        
        if resultado is None:
            # Determinar baseado na intensidade e estado
            if encontro.intensidade > 0.3:
                resultado = ResultadoEncontro.ADEQUACAO
            elif encontro.intensidade < 0.1:
                resultado = ResultadoEncontro.DISSOLUCAO
            else:
                resultado = ResultadoEncontro.NEUTRO
        
        # Aplicar penalidade se não tem ferramenta
        intensidade_modificada = encontro.intensidade
        detalhe_extra = ""
        if not tem_ferramenta and ferramenta_requerida:
            intensidade_modificada *= 0.5  # Metade da eficiência
            detalhe_extra = f" (sem {ferramenta_requerida})"
        
        # Dano à saúde se for encontro perigoso
        dano_saude = 0.0
        if resultado == ResultadoEncontro.DISSOLUCAO and (
            encontro.tag == "risco" or "perigo" in encontro.objeto
        ):
            dano_saude = encontro.intensidade * 0.15
        
        # Adicionar recurso ao inventário se for coleta
        ganho = None
        recurso_consumido = None
        recurso_qtd = 0.0
        
        if encontro.objeto in self.RECURSOS_COLETAVEIS:
            mat_nome, mat_qtd = self.RECURSOS_COLETAVEIS[encontro.objeto]
            personagem.inventario.adicionar_material(mat_nome, mat_qtd, qualidade=1.0)
            ganho = mat_nome
            
            # Marcar consumo de recurso local
            rec_nome = self.OBJETO_PARA_RECURSO.get(encontro.objeto)
            if rec_nome:
                recurso_consumido = rec_nome
                recurso_qtd = mat_qtd * 0.1  # 0.1 por unidade coletada
        
        # Calcular delta
        delta, _ = personagem.calcular_delta_encontro(
            tipo=encontro.tipo,
            intensidade=intensidade_modificada,
            objeto=encontro.objeto,
            resultado_sugerido=resultado
        )
        
        return ResultadoEncontroProcessado(
            encontro=encontro,
            resultado=resultado,
            delta_potencia=delta,
            sucesso=resultado != ResultadoEncontro.DISSOLUCAO,
            ganho_recurso=ganho,
            recurso_consumido=recurso_consumido,
            recurso_quantidade=recurso_qtd,
            dano_saude=dano_saude,
            detalhes=f"{encontro.descricao}{detalhe_extra}"
        )
    
    def _efeito_comida(
        self,
        personagem: Personagem,
        encontro: EncontroDisponivel
    ) -> ResultadoEncontroProcessado:
        """Efeito de pegar/comer comida"""
        antes_fome = personagem.necessidades.fome
        
        # Pegar comida do depósito comum (consome recurso local)
        personagem.inventario.adicionar_material("comida", 1, qualidade=1.0)
        
        # Restaurar fome
        restauracao = min(0.3, 1.0 - personagem.necessidades.fome)
        personagem.necessidades.fome += restauracao
        
        # Se estava com muita fome, grande alegria
        if antes_fome < 0.3:
            resultado = ResultadoEncontro.ADEQUACAO
            delta = 0.4
        else:
            resultado = ResultadoEncontro.ADEQUACAO
            delta = 0.15
        
        return ResultadoEncontroProcessado(
            encontro=encontro,
            resultado=resultado,
            delta_potencia=delta,
            sucesso=True,
            ganho_recurso="comida",
            recurso_consumido="comida",
            recurso_quantidade=0.15,
            detalhes=f"Pegou comida do depósito e comeu"
        )
    
    def _efeito_agua(
        self,
        personagem: Personagem,
        encontro: EncontroDisponivel
    ) -> ResultadoEncontroProcessado:
        """Efeito de buscar/beber água"""
        antes_sede = personagem.necessidades.sede
        
        # Pegar água
        personagem.inventario.adicionar_material("água", 1, qualidade=1.0)
        
        restauracao = min(0.35, 1.0 - personagem.necessidades.sede)
        personagem.necessidades.sede += restauracao
        
        if antes_sede < 0.3:
            resultado = ResultadoEncontro.ADEQUACAO
            delta = 0.45
        else:
            resultado = ResultadoEncontro.ADEQUACAO
            delta = 0.12
        
        return ResultadoEncontroProcessado(
            encontro=encontro,
            resultado=resultado,
            delta_potencia=delta,
            sucesso=True,
            ganho_recurso="água",
            recurso_consumido="água",
            recurso_quantidade=0.1,
            detalhes=f"Pegou água e bebeu"
        )
    
    def _checar_ferramenta(self, encontro: EncontroDisponivel, personagem: Personagem) -> tuple[bool, str]:
        """Verifica se personagem tem ferramenta necessária para o encontro"""
        ferramenta = encontro.requer_ferramenta
        if not ferramenta:
            return True, ""
        if personagem.tem_item(ferramenta):
            return True, f" usando {ferramenta}"
        return False, f" (sem {ferramenta})"

    def _efeito_madeira(
        self,
        personagem: Personagem,
        encontro: EncontroDisponivel
    ) -> ResultadoEncontroProcessado:
        """Efeito de cortar madeira"""
        tem_ferr, ferr_texto = self._checar_ferramenta(encontro, personagem)
        personagem.necessidades.energia -= 0.15
        
        # Chance de sucesso baseada em energia e ferramenta
        if personagem.necessidades.energia > 0.4 and tem_ferr:
            sucesso = True
            resultado = ResultadoEncontro.ADEQUACAO
            delta = 0.2
            ganho = "madeira"
            qtd = 2 if tem_ferr else 1
            personagem.inventario.adicionar_material("madeira", qtd, qualidade=1.0)
            detalhes = f"Cortou madeira{ferr_texto} (+{qtd} madeira)"
        elif personagem.necessidades.energia > 0.4:
            sucesso = True
            resultado = ResultadoEncontro.NEUTRO
            delta = 0.05
            ganho = "madeira"
            personagem.inventario.adicionar_material("madeira", 1, qualidade=1.0)
            detalhes = f"Cortou madeira{ferr_texto} (+1 madeira)"
        else:
            sucesso = False
            resultado = ResultadoEncontro.DISSOLUCAO
            delta = -0.15
            ganho = None
            detalhes = "Cansado demais para cortar madeira"
        
        recurso_consumido = "madeira" if sucesso else None
        recurso_qtd = 0.2 if sucesso else 0.0
        
        return ResultadoEncontroProcessado(
            encontro=encontro,
            resultado=resultado,
            delta_potencia=delta,
            sucesso=sucesso,
            ganho_recurso=ganho,
            recurso_consumido=recurso_consumido,
            recurso_quantidade=recurso_qtd,
            detalhes=detalhes
        )
    
    def _efeito_caca(
        self,
        personagem: Personagem,
        encontro: EncontroDisponivel
    ) -> ResultadoEncontroProcessado:
        """Efeito de caçar"""
        personagem.necessidades.energia -= 0.2
        
        # Caça é arriscada
        sucesso = random.random() < 0.6  # 60% de chance
        
        if sucesso:
            resultado = ResultadoEncontro.ADEQUACAO
            delta = 0.35
            ganho = "comida"
            personagem.inventario.adicionar_material("comida", 3, qualidade=1.0)
            detalhes = "Caça bem-sucedida! (+3 comida)"
        else:
            resultado = ResultadoEncontro.DISSOLUCAO
            delta = -0.1
            ganho = None
            detalhes = "A caça escapou"
        
        recurso_consumido = "caça" if sucesso else None
        recurso_qtd = 0.3 if sucesso else 0.0
        
        return ResultadoEncontroProcessado(
            encontro=encontro,
            resultado=resultado,
            delta_potencia=delta,
            sucesso=sucesso,
            ganho_recurso=ganho,
            recurso_consumido=recurso_consumido,
            recurso_quantidade=recurso_qtd,
            detalhes=detalhes
        )
    
    def _efeito_peixe(
        self,
        personagem: Personagem,
        encontro: EncontroDisponivel
    ) -> ResultadoEncontroProcessado:
        """Efeito de pescar"""
        tem_ferr, ferr_texto = self._checar_ferramenta(encontro, personagem)
        personagem.necessidades.energia -= 0.1
        
        chance = 0.8 if tem_ferr else 0.4
        sucesso = random.random() < chance
        
        if sucesso:
            resultado = ResultadoEncontro.ADEQUACAO
            delta = 0.25
            ganho = "comida"
            qtd = 3 if tem_ferr else 1
            personagem.inventario.adicionar_material("comida", qtd, qualidade=1.0)
            detalhes = f"Pescou{ferr_texto} (+{qtd} comida)"
        else:
            resultado = ResultadoEncontro.NEUTRO
            delta = -0.05
            ganho = None
            detalhes = "Nada mordeu a isca"
        
        recurso_consumido = "peixe" if sucesso else None
        recurso_qtd = 0.2 if sucesso else 0.0
        
        return ResultadoEncontroProcessado(
            encontro=encontro,
            resultado=resultado,
            delta_potencia=delta,
            sucesso=sucesso,
            ganho_recurso=ganho,
            recurso_consumido=recurso_consumido,
            recurso_quantidade=recurso_qtd,
            detalhes=detalhes
        )
    
    def _efeito_oficina(
        self,
        personagem: Personagem,
        encontro: EncontroDisponivel
    ) -> ResultadoEncontroProcessado:
        """Efeito de usar oficina"""
        personagem.necessidades.energia -= 0.1
        
        # Produzir algo útil baseado nas habilidades
        producoes_possiveis = []
        if personagem.get_nivel_habilidade("ferreiro") >= 0.2:
            producoes_possiveis.append(("metal", "refinou minério em metal"))
        if personagem.get_nivel_habilidade("artesao") >= 0.1:
            producoes_possiveis.append(("cordas", "teceu cordas resistentes"))
        if personagem.get_nivel_habilidade("construtor") >= 0.1:
            producoes_possiveis.append(("pranchas", "desbastou pranchas de madeira"))
        
        if producoes_possiveis:
            item, desc = random.choice(producoes_possiveis)
            qtd = random.randint(1, 3)
            if item in ("cordas",):
                personagem.inventario.adicionar_item(item, qtd)
            else:
                personagem.inventario.adicionar_material(item, qtd)
            detalhes = f"Trabalhou na oficina e {desc} (+{qtd} {item})"
            ganho = item
        else:
            detalhes = "Trabalhou na oficina mas não tem habilidade para produzir nada"
            ganho = None
        
        resultado = ResultadoEncontro.ADEQUACAO
        delta = 0.2
        
        return ResultadoEncontroProcessado(
            encontro=encontro,
            resultado=resultado,
            delta_potencia=delta,
            sucesso=True,
            ganho_recurso=ganho,
            detalhes=detalhes
        )
    
    def _efeito_minerar(
        self,
        personagem: Personagem,
        encontro: EncontroDisponivel
    ) -> ResultadoEncontroProcessado:
        """Efeito de mineração (pedra/mineral)"""
        tem_ferr, ferr_texto = self._checar_ferramenta(encontro, personagem)
        personagem.necessidades.energia -= 0.2
        
        if tem_ferr:
            sucesso = True
            if encontro.objeto in self.RECURSOS_COLETAVEIS:
                mat_nome, mat_qtd = self.RECURSOS_COLETAVEIS[encontro.objeto]
                qtd_real = mat_qtd + random.randint(0, 1)  # bônus com ferramenta
                personagem.inventario.adicionar_material(mat_nome, qtd_real, qualidade=1.0)
                detalhes = f"Minerou{ferr_texto} (+{qtd_real} {mat_nome})"
                ganho = mat_nome
            else:
                ganho = None
                detalhes = f"Minerou{ferr_texto}"
            resultado = ResultadoEncontro.ADEQUACAO
            delta = 0.25
        else:
            sucesso = False
            ganho = None
            detalhes = f"Não consegue minerar{ferr_texto}"
            resultado = ResultadoEncontro.DISSOLUCAO
            delta = -0.1
        
        rec_nome = self.OBJETO_PARA_RECURSO.get(encontro.objeto)
        recurso_consumido = rec_nome if sucesso else None
        recurso_qtd = 0.3 if sucesso else 0.0
        
        return ResultadoEncontroProcessado(
            encontro=encontro,
            resultado=resultado,
            delta_potencia=delta,
            sucesso=sucesso,
            ganho_recurso=ganho,
            recurso_consumido=recurso_consumido,
            recurso_quantidade=recurso_qtd,
            detalhes=detalhes
        )


# =============================================================================
# MOTOR PRINCIPAL DE ENCONTROS
# =============================================================================

class MotorEncontros:
    """
    Motor principal que orquestra todos os encontros
    """
    
    def __init__(self):
        self.gerador = GeradorEncontros()
        self.processador = ProcessadorEncontros()
        
        # Histórico de encontros
        self.historico: list[ResultadoEncontroProcessado] = []
    
    def obter_encontros_para_personagem(
        self,
        personagem: Personagem,
        todos_personagens: list[Personagem],
        hora: int,
        eventos: list[EventoMundo]
    ) -> list[EncontroDisponivel]:
        """
        Retorna todos os encontros disponíveis para um personagem
        """
        encontros = []
        
        # Encontros locais
        encontros_locais = self.gerador.gerar_encontros_locais(
            local=personagem.local_atual,
            hora=hora,
            personagem=personagem,
            eventos=eventos
        )
        encontros.extend(encontros_locais)
        
        # Encontros sociais
        encontros_sociais = self.gerador.gerar_encontros_sociais(
            personagem=personagem,
            outros=todos_personagens
        )
        encontros.extend(encontros_sociais)
        
        return encontros
    
    def processar_encontro(
        self,
        personagem: Personagem,
        encontro: EncontroDisponivel
    ) -> ResultadoEncontroProcessado:
        """
        Processa um encontro e aplica seus efeitos
        """
        # Processar
        resultado = self.processador.processar(personagem, encontro)
        
        # Aplicar no personagem
        memoria = personagem.aplicar_encontro(
            tipo=encontro.tipo,
            intensidade=encontro.intensidade,
            objeto=encontro.objeto,
            descricao=encontro.descricao,
            local=personagem.local_atual,
            resultado_sugerido=resultado.resultado
        )
        
        # Processar efeitos colaterais
        if resultado.mudanca_local:
            personagem.local_atual = resultado.mudanca_local
        
        if resultado.mudanca_estado:
            personagem.estado = resultado.mudanca_estado
        
        # Registrar no histórico
        self.historico.append(resultado)
        
        return resultado
    
    def processar_encontro_social(
        self,
        personagem1: Personagem,
        personagem2: Personagem,
        tipo_encontro: str = "conversa"
    ) -> tuple[ResultadoEncontroProcessado, ResultadoEncontroProcessado]:
        """
        Processa encontro social entre dois personagens
        
        Retorna resultados para ambos
        """
        # Criar encontro
        encontro = EncontroDisponivel(
            id=f"social_{personagem1.id}_{personagem2.id}",
            origem=OrigemEncontro.SOCIAL,
            tipo=TipoEncontro.SOCIAL,
            objeto=personagem2.id,
            descricao=f"Encontro com {personagem2.nome}",
            intensidade=0.3,
            disponibilidade=DisponibilidadeEncontro.SEMPRE,
            tag=tipo_encontro
        )
        
        # Processar para ambos
        resultado1 = self.processar_encontro(personagem1, encontro)
        
        encontro2 = EncontroDisponivel(
            id=f"social_{personagem2.id}_{personagem1.id}",
            origem=OrigemEncontro.SOCIAL,
            tipo=TipoEncontro.SOCIAL,
            objeto=personagem1.id,
            descricao=f"Encontro com {personagem1.nome}",
            intensidade=encontro.intensidade,
            disponibilidade=DisponibilidadeEncontro.SEMPRE,
            tag=tipo_encontro
        )
        resultado2 = self.processar_encontro(personagem2, encontro2)
        
        # Atualizar relações
        positivo1 = resultado1.resultado == ResultadoEncontro.ADEQUACAO
        positivo2 = resultado2.resultado == ResultadoEncontro.ADEQUACAO
        
        personagem1.registrar_encontro_relacional(
            personagem2.id, "personagem", positivo1,
            encontro.descricao, personagem2.nome
        )
        personagem2.registrar_encontro_relacional(
            personagem1.id, "personagem", positivo2,
            encontro2.descricao, personagem1.nome
        )
        
        return resultado1, resultado2
    
    def processar_encontro_observacional(
        self,
        observador: Personagem,
        encontro_observado: EncontroDisponivel
    ) -> ResultadoEncontroProcessado:
        """
        Processa encontro que o personagem apenas observa
        """
        # Encontros observacionais são mais fracos
        encontro_observacao = EncontroDisponivel(
            id=f"obs_{observador.id}_{encontro_observado.id}",
            origem=OrigemEncontro.OBSERVACIONAL,
            tipo=TipoEncontro.OBSERVACIONAL,
            objeto=encontro_observado.objeto,
            descricao=f"Observar: {encontro_observado.descricao}",
            intensidade=encontro_observado.intensidade * 0.5,  # metade da intensidade
            disponibilidade=DisponibilidadeEncontro.RARO,
            tag="observacao"
        )
        
        return self.processar_encontro(observador, encontro_observacao)
    
    def resumir_historico(self, ultimos_n: int = 10) -> str:
        """Retorna resumo dos últimos encontros"""
        if not self.historico:
            return "Nenhum encontro registrado."
        
        recentes = self.historico[-ultimos_n:]
        
        linhas = []
        for r in recentes:
            emoji = "✅" if r.resultado == ResultadoEncontro.ADEQUACAO else "❌" if r.resultado == ResultadoEncontro.DISSOLUCAO else "➖"
            linhas.append(f"{emoji} {r.encontro.descricao} ({r.delta_potencia:+.2f})")
        
        return "\n".join(linhas)


# =============================================================================
# EXEMPLO DE USO
# =============================================================================

if __name__ == "__main__":
    from personagem import Personalidade
    
    # Criar motor
    motor = MotorEncontros()
    
    # Criar personagens
    maria = Personalidade(
        nome="Maria",
        arquetipo="generoso",
        idade=35,
        descricao="Mulher calorosa",
        razao_innata=0.6
    )
    p_maria = Personagem(maria, local_inicial="vila")
    
    joao = Personalidade(
        nome="João",
        arquetipo="prudente",
        idade=40,
        descricao="Homem cauteloso",
        razao_innata=0.7
    )
    p_joao = Personagem(joao, local_inicial="vila")
    
    print("=== ENCONTROS DISPONÍVEIS PARA MARIA ===")
    encontros = motor.obter_encontros_para_personagem(
        p_maria,
        [p_maria, p_joao],
        hora=10,
        eventos=[]
    )
    
    for e in encontros:
        print(f"  [{e.tipo.value}] {e.descricao} (intensidade: {e.intensidade:.2f})")
    
    print(f"\nTotal: {len(encontros)} encontros disponíveis")
    
    # Processar um encontro
    if encontros:
        print("\n=== PROCESSANDO PRIMEIRO ENCONTRO ===")
        resultado = motor.processar_encontro(p_maria, encontros[0])
        print(f"Resultado: {resultado.resultado.value}")
        print(f"Delta: {resultado.delta_potencia:+.3f}")
        print(f"Detalhes: {resultado.detalhes}")
        print(f"\nMaria agora: potência={p_maria.potencia_atual:.3f}")
    
    # Processar encontro social
    print("\n=== ENCONTRO SOCIAL ===")
    r1, r2 = motor.processar_encontro_social(p_maria, p_joao)
    print(f"Maria: {r1.resultado.value} ({r1.delta_potencia:+.3f})")
    print(f"João: {r2.resultado.value} ({r2.delta_potencia:+.3f})")
    print(f"\nRelação Maria→João: afeto={p_maria.get_ou_criar_relacao('joão').afeto:.2f}")
    print(f"Relação João→Maria: afeto={p_joao.get_ou_criar_relacao('maria').afeto:.2f}")
