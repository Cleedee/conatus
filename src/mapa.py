"""
Módulo de Mapa — Sistema de Espaço na Simulação Espinozista

Define locais, conexões, distâncias e propriedades do mundo.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import random


# =============================================================================
# ENUMS
# =============================================================================

class TipoLocal(Enum):
    """Tipos de local"""
    ASSENTAMENTO = "assentamento"
    RECURSO_NATURAL = "recurso_natural"
    PERIGOSO = "perigoso"
    NEUTRO = "neutro"


class CondicaoClima(Enum):
    """Condições climáticas"""
    NORMAL = "normal"
    CHUVA = "chuva"
    SECA = "seca"
    TEMPESTADE = "tempestade"
    NEVE = "neve"
    CALOR_EXTREMO = "calor_extremo"


# =============================================================================
# ESTRUTURAS
# =============================================================================

@dataclass
class RecursoLocal:
    """Recurso disponível num local"""
    nome: str
    quantidade_atual: float      # 0.0 a 1.0
    taxa_renovacao: float        # por tick
    maximo: float = 1.0
    renovavel: bool = True
    
    def renovar(self):
        """Renova o recurso (chamado a cada tick)"""
        if self.renovavel and self.quantidade_atual < self.maximo:
            self.quantidade_atual = min(
                self.maximo,
                self.quantidade_atual + self.taxa_renovacao
            )
    
    def consumir(self, quantidade: float) -> float:
        """
        Consome recurso
        
        Returns:
            Quantidade efetivamente consumida
        """
        consumido = min(quantidade, self.quantidade_atual)
        self.quantidade_atual -= consumido
        return consumido
    
    @property
    def disponivel(self) -> bool:
        return self.quantidade_atual > 0.1
    
    @property
    def nivel(self) -> str:
        """Nível descritivo do recurso"""
        if self.quantidade_atual > 0.8:
            return "abundante"
        elif self.quantidade_atual > 0.5:
            return "suficiente"
        elif self.quantidade_atual > 0.2:
            return "escasso"
        else:
            return "crítico"


@dataclass
class Local:
    """
    Representa um local no mundo da simulação
    """
    id: str
    nome: str
    descricao: str
    tipo: TipoLocal
    
    # Propriedades físicas
    capacidade: int = 10         # máximo de personagens
    perigo: float = 0.0         # 0.0 a 1.0
    conforto: float = 0.5       # 0.0 a 1.0
    
    # Recursos
    recursos: list[RecursoLocal] = field(default_factory=list)
    
    # Conexões (local_id -> distância em ticks)
    conexoes: dict[str, int] = field(default_factory=dict)
    
    # Propriedades especiais
    permite_acampamento: bool = True
    requer_ferramentas: bool = False
    visivel_de: list[str] = field(default_factory=list)  # locais de onde se vê
    
    # Estado dinâmico
    clima_local: CondicaoClima = CondicaoClima.NORMAL
    ocupacao_atual: int = 0
    
    def tick(self):
        """Atualiza estado do local a cada tick"""
        # Renovar recursos
        for recurso in self.recursos:
            recurso.renovar()
        
        # Chance de mudar clima
        if random.random() < 0.05:  # 5% por tick
            self._mudar_clima()
    
    def _mudar_clima(self):
        """Muda clima aleatoriamente"""
        opcoes = list(CondicaoClima)
        # Manter mais provável ser normal
        pesos = [50, 15, 15, 5, 10, 5]
        self.clima_local = random.choices(opcoes, weights=pesos)[0]
    
    @property
    def lotado(self) -> bool:
        return self.ocupacao_atual >= self.capacidade
    
    @property
    def nivel_perigo(self) -> str:
        """Nível descritivo de perigo"""
        if self.perigo > 0.7:
            return "muito perigoso"
        elif self.perigo > 0.4:
            return "perigoso"
        elif self.perigo > 0.2:
            return "cautela"
        else:
            return "seguro"
    
    def get_distancia(self, destino_id: str) -> Optional[int]:
        """Retorna distância em ticks para outro local"""
        return self.conexoes.get(destino_id)
    
    def tem_recurso(self, nome: str) -> bool:
        """Verifica se tem recurso disponível"""
        for r in self.recursos:
            if r.nome == nome and r.disponivel:
                return True
        return False
    
    def get_recurso(self, nome: str) -> Optional[RecursoLocal]:
        """Retorna recurso pelo nome"""
        for r in self.recursos:
            if r.nome == nome:
                return r
        return None
    
    def descricao_completa(self) -> str:
        """Retorna descrição detalhada do local"""
        linhas = [
            f"📍 {self.nome}",
            f"   {self.descricao}",
            f"   Tipo: {self.tipo.value}",
            f"   Perigo: {self.nivel_perigo}",
            f"   Conforto: {self.conforto:.0%}",
            f"   Clima: {self.clima_local.value}",
            f"   Ocupação: {self.ocupacao_atual}/{self.capacidade}"
        ]
        
        # Recursos
        if self.recursos:
            recursos_disponiveis = [r for r in self.recursos if r.disponivel]
            if recursos_disponiveis:
                linhas.append("   Recursos disponíveis:")
                for r in recursos_disponiveis:
                    linhas.append(f"     - {r.nome}: {r.nivel}")
        
        # Conexões
        if self.conexoes:
            linhas.append("   Conexões:")
            for destino, dist in self.conexoes.items():
                linhas.append(f"     → {destino}: {dist} ticks")
        
        return "\n".join(linhas)


# =============================================================================
# MAPA PRINCIPAL
# =============================================================================

class Mapa:
    """
    Mapa do mundo da simulação
    """
    
    def __init__(self):
        self.locais: dict[str, Local] = {}
        self.local_inicial: str = "vila"
    
    def adicionar_local(self, local: Local):
        """Adiciona um local ao mapa"""
        self.locais[local.id] = local
    
    def get_local(self, local_id: str) -> Optional[Local]:
        """Retorna um local pelo ID"""
        return self.locais.get(local_id)
    
    def get_distancia(self, origem_id: str, destino_id: str) -> Optional[int]:
        """
        Calcula distância entre dois locais
        
        Returns:
            Distância em ticks, ou None se não há caminho
        """
        if origem_id == destino_id:
            return 0
        
        local = self.get_local(origem_id)
        if local:
            return local.get_distancia(destino_id)
        
        return None
    
    def get_caminho(
        self,
        origem_id: str,
        destino_id: str,
        max_profundidade: int = 5
    ) -> Optional[list[str]]:
        """
        Busca caminho entre dois locais (BFS simples)
        
        Returns:
            Lista de locais no caminho, ou None
        """
        if origem_id == destino_id:
            return [origem_id]
        
        # BFS
        fila = [(origem_id, [origem_id])]
        visitados = {origem_id}
        
        while fila:
            atual, caminho = fila.pop(0)
            
            if len(caminho) > max_profundidade:
                continue
            
            local = self.get_local(atual)
            if not local:
                continue
            
            for vizinho_id in local.conexoes.keys():
                if vizinho_id == destino_id:
                    return caminho + [vizinho_id]
                
                if vizinho_id not in visitados:
                    visitados.add(vizinho_id)
                    fila.append((vizinho_id, caminho + [vizinho_id]))
        
        return None
    
    def get_tempo_caminho(
        self,
        origem_id: str,
        destino_id: str,
        modificador_velocidade: float = 1.0
    ) -> Optional[int]:
        """
        Calcula tempo total de viagem entre dois locais
        
        Args:
            modificador_velocidade: < 1 = mais rápido, > 1 = mais lento
        """
        caminho = self.get_caminho(origem_id, destino_id)
        if not caminho:
            return None
        
        tempo_total = 0
        for i in range(len(caminho) - 1):
            local = self.get_local(caminho[i])
            dist = local.get_distancia(caminho[i + 1])
            if dist:
                tempo_total += int(dist * modificador_velocidade)
        
        return tempo_total
    
    def locais_com_recurso(self, nome_recurso: str) -> list[Local]:
        """Retorna locais que têm determinado recurso"""
        resultado = []
        for local in self.locais.values():
            if local.tem_recurso(nome_recurso):
                resultado.append(local)
        return resultado
    
    def locais_seguros(self) -> list[Local]:
        """Retorna locais com perigo baixo"""
        return [l for l in self.locais.values() if l.perigo < 0.3]
    
    def tick(self):
        """Atualiza todos os locais"""
        for local in self.locais.values():
            local.tick()
    
    def descrever_mundo(self) -> str:
        """Retorna descrição completa do mundo"""
        linhas = ["🌍 MAPA DO MUNDO", "=" * 40]
        
        for local in self.locais.values():
            linhas.append("")
            linhas.append(local.descricao_completa())
        
        return "\n".join(linhas)


# =============================================================================
# MAPA PADRÃO
# =============================================================================

def criar_mapa_padrao() -> Mapa:
    """
    Cria o mapa padrão da simulação
    
    Topografia:
                    [Floresta] ── [Lago]
                         │
     [Montanha] ── [Vila] ── [Planície] ── [Ruínas]
                         │
                     [Rio] ── [Pântano]
                         │
                     [Praia]
                         │
                    [Caverna]
    """
    mapa = Mapa()
    
    # =========================================================================
    # VILA (centro)
    # =========================================================================
    vila = Local(
        id="vila",
        nome="Vila",
        descricao="Pequeno assentamento com abrigos e depósitos",
        tipo=TipoLocal.ASSENTAMENTO,
        capacidade=12,
        perigo=0.05,
        conforto=0.7,
        recursos=[
            RecursoLocal("comida", 0.8, 0.02),
            RecursoLocal("água", 0.9, 0.03),
            RecursoLocal("madeira", 0.5, 0.01),
            RecursoLocal("ferramentas", 0.6, 0.005)
        ],
        conexoes={
            "floresta": 3,
            "montanha": 4,
            "planicie": 2,
            "rio": 2
        }
    )
    
    # =========================================================================
    # FLORESTA
    # =========================================================================
    floresta = Local(
        id="floresta",
        nome="Floresta Densa",
        descricao="Árvores centenárias, recursos abundantes mas perigosa",
        tipo=TipoLocal.RECURSO_NATURAL,
        capacidade=6,
        perigo=0.4,
        conforto=0.3,
        recursos=[
            RecursoLocal("madeira", 0.9, 0.005),
            RecursoLocal("caça", 0.6, 0.01),
            RecursoLocal("ervas", 0.5, 0.008),
            RecursoLocal("cogumelos", 0.4, 0.015)
        ],
        conexoes={
            "vila": 3,
            "montanha": 5
        },
        permite_acampamento=False
    )
    
    # =========================================================================
    # MONTANHA
    # =========================================================================
    montanha = Local(
        id="montanha",
        nome="Montanha Rochosa",
        descricao="Pico elevado com vista panorâmica e minerais",
        tipo=TipoLocal.RECURSO_NATURAL,
        capacidade=4,
        perigo=0.5,
        conforto=0.2,
        recursos=[
            RecursoLocal("pedra", 0.8, 0.002),
            RecursoLocal("mineral", 0.4, 0.001),
            RecursoLocal("cristais", 0.2, 0.0005)
        ],
        conexoes={
            "vila": 4,
            "floresta": 5,
            "caverna": 3
        },
        requer_ferramentas=True
    )
    
    # =========================================================================
    # PLANÍCIE
    # =========================================================================
    planicie = Local(
        id="planicie",
        nome="Planície Fértil",
        descricao="Campos abertos ideais para agricultura",
        tipo=TipoLocal.NEUTRO,
        capacidade=8,
        perigo=0.1,
        conforto=0.5,
        recursos=[
            RecursoLocal("colheita", 0.7, 0.02),
            RecursoLocal("ervas_medicinais", 0.5, 0.01),
            RecursoLocal("grama", 0.9, 0.03)
        ],
        conexoes={
            "vila": 2,
            "rio": 3,
            "praia": 5
        }
    )
    
    # =========================================================================
    # RIO
    # =========================================================================
    rio = Local(
        id="rio",
        nome="Rio Caudaloso",
        descricao="Água corrente com peixes e riscos de enchente",
        tipo=TipoLocal.RECURSO_NATURAL,
        capacidade=6,
        perigo=0.3,
        conforto=0.4,
        recursos=[
            RecursoLocal("água_fresca", 0.95, 0.04),
            RecursoLocal("peixe", 0.6, 0.015),
            RecursoLocal("pedras_lisas", 0.5, 0.003)
        ],
        conexoes={
            "vila": 2,
            "planicie": 3,
            "praia": 3
        }
    )
    
    # =========================================================================
    # PRAIA
    # =========================================================================
    praia = Local(
        id="praia",
        nome="Praia do Litoral",
        descricao="Costa rochosa com mariscos e areia",
        tipo=TipoLocal.NEUTRO,
        capacidade=8,
        perigo=0.2,
        conforto=0.4,
        recursos=[
            RecursoLocal("marisco", 0.5, 0.01),
            RecursoLocal("sal", 0.3, 0.002),
            RecursoLocal("madeira_marinha", 0.4, 0.005)
        ],
        conexoes={
            "rio": 3,
            "planicie": 5
        }
    )
    
    # =========================================================================
    # CAVERNA
    # =========================================================================
    caverna = Local(
        id="caverna",
        nome="Caverna Escura",
        descricao="Túneis subterrâneos com minerais e perigos",
        tipo=TipoLocal.PERIGOSO,
        capacidade=4,
        perigo=0.6,
        conforto=0.1,
        recursos=[
            RecursoLocal("mineral", 0.7, 0.001),
            RecursoLocal("cristais", 0.3, 0.0003),
            RecursoLocal("fungos", 0.4, 0.008)
        ],
        conexoes={
            "montanha": 3
        },
        requer_ferramentas=True
    )
    
    # =========================================================================
    # LAGO
    # =========================================================================
    lago = Local(
        id="lago",
        nome="Lago Sereno",
        descricao="Águas calmas cercadas por vegetação",
        tipo=TipoLocal.RECURSO_NATURAL,
        capacidade=4,
        perigo=0.15,
        conforto=0.6,
        recursos=[
            RecursoLocal("peixe", 0.6, 0.02),
            RecursoLocal("água", 0.8, 0.03),
            RecursoLocal("ervas", 0.4, 0.01),
        ],
        conexoes={
            "floresta": 2,
            "montanha": 4,
        }
    )
    
    # =========================================================================
    # PÂNTANO
    # =========================================================================
    pantano = Local(
        id="pantano",
        nome="Pântano Sombrio",
        descricao="Terreno alagado com névoa e plantas raras",
        tipo=TipoLocal.PERIGOSO,
        capacidade=3,
        perigo=0.55,
        conforto=0.15,
        recursos=[
            RecursoLocal("ervas", 0.5, 0.02),
            RecursoLocal("cogumelos", 0.7, 0.01),
            RecursoLocal("madeira", 0.3, 0.005),
        ],
        conexoes={
            "floresta": 4,
            "rio": 2,
        }
    )
    
    # =========================================================================
    # RUÍNAS ANTIGAS
    # =========================================================================
    ruinas = Local(
        id="ruinas",
        nome="Ruínas Antigas",
        descricao="Vestígios de uma civilização com materiais valiosos",
        tipo=TipoLocal.NEUTRO,
        capacidade=3,
        perigo=0.35,
        conforto=0.2,
        recursos=[
            RecursoLocal("pedra", 0.5, 0.005),
            RecursoLocal("mineral", 0.5, 0.002),
            RecursoLocal("cristais", 0.4, 0.001),
        ],
        conexoes={
            "planicie": 4,
        }
    )
    
    # Adicionar locais ao mapa
    for local in [vila, floresta, montanha, planicie, rio, praia, caverna, lago, pantano, ruinas]:
        mapa.adicionar_local(local)
    
    mapa.local_inicial = "vila"
    
    return mapa


# =============================================================================
# EXEMPLO DE USO
# =============================================================================

if __name__ == "__main__":
    # Criar mapa
    mapa = criar_mapa_padrao()
    
    print(mapa.descrever_mundo())
    
    print("\n" + "=" * 40)
    print("🧪 TESTES DE CAMINHO")
    print("=" * 40)
    
    # Testar caminhos
    testes = [
        ("vila", "caverna"),
        ("floresta", "praia"),
        ("montanha", "planicie")
    ]
    
    for origem, destino in testes:
        caminho = mapa.get_caminho(origem, destino)
        tempo = mapa.get_tempo_caminho(origem, destino)
        print(f"\n{origem} → {destino}:")
        print(f"  Caminho: {' → '.join(caminho) if caminho else 'Sem caminho'}")
        print(f"  Tempo: {tempo} ticks" if tempo else "  Tempo: N/A")
    
    # Locais com recurso
    print("\n" + "=" * 40)
    print("🔍 LOCAIS COM 'comida'")
    print("=" * 40)
    
    locais_comida = mapa.locais_com_recurso("comida")
    for local in locais_comida:
        recurso = local.get_recurso("comida")
        print(f"  - {local.nome}: {recurso.nivel} ({recurso.quantidade_atual:.0%})")
    
    # Simular ticks
    print("\n" + "=" * 40)
    print("⏰ SIMULANDO 10 TICKS")
    print("=" * 40)
    
    for i in range(10):
        mapa.tick()
    
    # Mostrar estado após ticks
    print("\nRecursos após 10 ticks:")
    for local in mapa.locais.values():
        for r in local.recursos:
            print(f"  {local.nome}/{r.nome}: {r.quantidade_atual:.2%}")
