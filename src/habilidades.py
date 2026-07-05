"""
Módulo de Habilidades e Crafting

Sistema completo de:
- Habilidades por personagem
- Receitas de crafting
- Cadeia de produção
- Aprendizado e ensino
- Especialização
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import random


# =============================================================================
# ENUMS
# =============================================================================

# Tabela de perecibilidade: quantos ticks cada material dura (-1 = não perece)
TEMPOS_VALIDADE: dict[str, int] = {
    "comida": 24,            # 1 dia (raw, estraga rápido)
    "colheita": 36,          # 1.5 dias
    "carne_assada": 96,      # 4 dias
    "sopa": 72,              # 3 dias
    "pao": 120,              # 5 dias
    "refeicao": 48,          # 2 dias
    "carne_defumada": 500,   # ~20 dias
    "molho": 96,             # 4 dias
    "po_cura": 200,          # ~8 dias
    "remedio": 200,          # ~8 dias
    "bandagem": 200,         # ~8 dias
    "peixe": 18,             # <1 dia (fresco)
    "caça": 18,              # <1 dia (fresco)
    "marisco": 12,           # meio dia
}


class NivelHabilidade(Enum):
    """Níveis descritivos de habilidade"""
    IGNORANTE = "ignorante"      # 0.0 - 0.2
    INICIANTE = "iniciante"      # 0.2 - 0.4
    CAPAZ = "capaz"              # 0.4 - 0.6
    HABILIDOSO = "habilidoso"    # 0.6 - 0.8
    MESTRE = "mestre"            # 0.8 - 1.0


class TipoReceita(Enum):
    """Tipos de receitas"""
    CRAFTING = "crafting"        # Criar item novo
    PROCESSAMENTO = "processamento"  # Transformar matéria-prima
    COZINHA = "cozinha"          # Preparar comida
    MEDICINA = "medicina"        # Criar remédios
    CONSTRUCAO = "construcao"    # Construir estruturas


class ResultadoCrafting(Enum):
    """Resultado do crafting"""
    SUCESSO = "sucesso"
    FALHA_PARCIAL = "falha_parcial"  # Perde material mas não tudo
    FALHA_TOTAL = "falha_total"      # Perde tudo
    FALHA_SEGURA = "falha_segura"    # Não perde nada, só não consegue


# =============================================================================
# ESTRUTURAS DE DADOS
# =============================================================================

@dataclass
class Habilidade:
    """Habilidade de um personagem"""
    nome: str
    nivel: float = 0.0          # 0.0 a 1.0
    experiencia: int = 0        # XP acumulado
    xp_proximo_nivel: int = 100 # XP necessário para próximo nível
    
    @property
    def nivel_descricao(self) -> str:
        """Retorna nível descritivo"""
        if self.nivel < 0.2:
            return NivelHabilidade.IGNORANTE.value
        elif self.nivel < 0.4:
            return NivelHabilidade.INICIANTE.value
        elif self.nivel < 0.6:
            return NivelHabilidade.CAPAZ.value
        elif self.nivel < 0.8:
            return NivelHabilidade.HABILIDOSO.value
        else:
            return NivelHabilidade.MESTRE.value
    
    @property
    def pode_ensinar(self) -> bool:
        """Se pode ensinar outros — reduzido para 0.2 para ensino mais cedo"""
        return self.nivel >= 0.2
    
    @property
    def pode_aprender_com(self) -> bool:
        """Se pode aprender observando"""
        return self.nivel < 0.8
    
    def ganhar_xp(self, quantidade: int) -> bool:
        """
        Ganha experiência
        
        Returns:
            True se subiu de nível
        """
        self.experiencia += quantidade
        subiu = False
        
        while self.experiencia >= self.xp_proximo_nivel:
            self.experiencia -= self.xp_proximo_nivel
            self.nivel = min(1.0, self.nivel + 0.05)
            self.xp_proximo_nivel = int(self.xp_proximo_nivel * 1.3)
            subiu = True
        
        return subiu
    
    def chance_sucesso(self, dificuldade: float = 0.5) -> float:
        """
        Calcula chance de sucesso baseado na habilidade
        """
        # Habilidade do personagem vs dificuldade da tarefa
        return max(0.0, min(1.0, self.nivel - dificuldade + 0.5))


@dataclass
class Material:
    """Material/recurso"""
    nome: str
    quantidade: int = 0
    qualidade: float = 1.0      # 0.5 a 1.5 (afeta resultado)
    validade: int = -1          # ticks restantes (-1 = não perecível)
    
    @property
    def perecivel(self) -> bool:
        return self.validade >= 0
    
    @property
    def nivel_descricao(self) -> str:
        if self.qualidade < 0.7:
            return "baixa"
        elif self.qualidade < 1.0:
            return "média"
        elif self.qualidade < 1.3:
            return "boa"
        else:
            return "excelente"


@dataclass
class Receita:
    """Receita de crafting"""
    id: str
    nome: str
    descricao: str
    tipo: TipoReceita
    
    # Materiais necessários {nome_material: quantidade}
    materiais: dict[str, int]
    
    # Habilidade necessária e nível mínimo
    habilidade_requerida: Optional[str] = None
    nivel_minimo: float = 0.0
    
    # Resultado
    resultado_nome: str = ""
    resultado_quantidade: int = 1
    resultado_descricao: str = ""
    
    # XP ganho ao completar
    xp_ganho: int = 25
    
    # Dificuldade da receita (afeta chance de falha)
    dificuldade: float = 0.3
    
    # Tempo em ticks
    tempo_crafting: int = 1
    
    # Pré-requisitos (outras receitas que precisa saber)
    prerequisitos: list[str] = field(default_factory=list)


@dataclass
class ResultadoCraftingFinal:
    """Resultado de uma tentativa de crafting"""
    receita: Receita
    resultado: ResultadoCrafting
    itens_criados: list[tuple[str, int]]  # (nome, quantidade)
    materiais_perdidos: dict[str, int]
    xp_ganho: int
    mensagem: str


# =============================================================================
# BANCO DE RECEITAS
# =============================================================================

class BancoReceitas:
    """Todas as receitas disponíveis no mundo"""
    
    def __init__(self):
        self.receitas: dict[str, Receita] = {}
        self._criar_receitas_padrao()
    
    def _criar_receitas_padrao(self):
        """Cria receitas iniciais do jogo"""
        
        # === PROCESSAMENTO BÁSICO ===
        
        self.adicionar(Receita(
            id="talar_madeira",
            nome="Talar Madeira",
            descricao="Transformar tronco em pranchas úteis",
            tipo=TipoReceita.PROCESSAMENTO,
            materiais={"madeira": 2},
            habilidade_requerida="madeireiro",
            nivel_minimo=0.0,
            resultado_nome="pranchas",
            resultado_quantidade=4,
            resultado_descricao="Pranchas de madeira processada",
            xp_ganho=15,
            dificuldade=0.2
        ))
        
        self.adicionar(Receita(
            id="fazer_cordas",
            nome="Fazer Cordas",
            descricao="Tecer fibras em cordas resistentes",
            tipo=TipoReceita.PROCESSAMENTO,
            materiais={"ervas": 3},
            habilidade_requerida="artesao",
            nivel_minimo=0.0,
            resultado_nome="cordas",
            resultado_quantidade=2,
            resultado_descricao="Cordas feitas de fibras naturais",
            xp_ganho=15,
            dificuldade=0.2
        ))
        
        self.adicionar(Receita(
            id="fundir_metal",
            nome="Fundir Metal",
            descricao="Transformar minério em metal trabalhável",
            tipo=TipoReceita.PROCESSAMENTO,
            materiais={"mineral": 3},
            habilidade_requerida="ferreiro",
            nivel_minimo=0.2,
            resultado_nome="metal",
            resultado_quantidade=1,
            resultado_descricao="Metal fundido e moldável",
            xp_ganho=30,
            dificuldade=0.4
        ))
        
        # === FERRAMENTAS ===
        
        self.adicionar(Receita(
            id="fazer_machado",
            nome="Fazer Machado",
            descricao="Criar machado para cortar madeira",
            tipo=TipoReceita.CRAFTING,
            materiais={"pranchas": 2, "pedra": 1, "cordas": 1},
            habilidade_requerida="ferreiro",
            nivel_minimo=0.3,
            resultado_nome="machado",
            resultado_quantidade=1,
            resultado_descricao="Machado robusto para cortar árvores",
            xp_ganho=40,
            dificuldade=0.4
        ))
        
        self.adicionar(Receita(
            id="fazer_picareta",
            nome="Fazer Picareta",
            descricao="Criar picareta para minerar",
            tipo=TipoReceita.CRAFTING,
            materiais={"pranchas": 2, "metal": 1, "cordas": 1},
            habilidade_requerida="ferreiro",
            nivel_minimo=0.4,
            resultado_nome="picareta",
            resultado_quantidade=1,
            resultado_descricao="Picareta resistente para mineração",
            xp_ganho=50,
            dificuldade=0.5
        ))
        
        self.adicionar(Receita(
            id="fazer_vara_pesca",
            nome="Fazer Vara de Pesca",
            descricao="Criar vara simples para pescar",
            tipo=TipoReceita.CRAFTING,
            materiais={"pranchas": 1, "cordas": 1},
            habilidade_requerida="artesao",
            nivel_minimo=0.1,
            resultado_nome="vara_pesca",
            resultado_quantidade=1,
            resultado_descricao="Vara de pesca simples",
            xp_ganho=20,
            dificuldade=0.2
        ))
        
        # === CONSTRUÇÃO ===
        
        self.adicionar(Receita(
            id="construir_fogueira",
            nome="Construir Fogueira",
            descricao="Montar fogueira para aquecer e cozinhar",
            tipo=TipoReceita.CONSTRUCAO,
            materiais={"pedra": 3, "madeira": 2},
            habilidade_requerida="construtor",
            nivel_minimo=0.0,
            resultado_nome="fogueira",
            resultado_quantidade=1,
            resultado_descricao="Fogueira funcional",
            xp_ganho=20,
            dificuldade=0.2
        ))
        
        self.adicionar(Receita(
            id="construir_abrigo",
            nome="Construir Abrigo",
            descricao="Construir abrigo simples contra intempéries",
            tipo=TipoReceita.CONSTRUCAO,
            materiais={"pranchas": 6, "cordas": 2},
            habilidade_requerida="construtor",
            nivel_minimo=0.3,
            resultado_nome="abrigo",
            resultado_quantidade=1,
            resultado_descricao="Abrigo simples mas funcional",
            xp_ganho=50,
            dificuldade=0.4
        ))
        
        self.adicionar(Receita(
            id="construir_cabana",
            nome="Construir Cabana",
            descricao="Construir cabana de madeira",
            tipo=TipoReceita.CONSTRUCAO,
            materiais={"pranchas": 15, "cordas": 5, "pedra": 5},
            habilidade_requerida="construtor",
            nivel_minimo=0.5,
            resultado_nome="cabana",
            resultado_quantidade=1,
            resultado_descricao="Cabana confortável e resistente",
            xp_ganho=100,
            dificuldade=0.6
        ))
        
        self.adicionar(Receita(
            id="construir_armazem",
            nome="Construir Armazém",
            descricao="Construir estrutura para guardar alimentos",
            tipo=TipoReceita.CONSTRUCAO,
            materiais={"pranchas": 20, "cordas": 3, "pedra": 10},
            habilidade_requerida="construtor",
            nivel_minimo=0.6,
            resultado_nome="armazem",
            resultado_quantidade=1,
            resultado_descricao="Armazém para preservar alimentos",
            xp_ganho=120,
            dificuldade=0.7
        ))
        
        # === COZINHA ===
        
        self.adicionar(Receita(
            id="assar_carne",
            nome="Assar Carne",
            descricao="Cozinhar carne na fogueira",
            tipo=TipoReceita.COZINHA,
            materiais={"comida": 1},
            habilidade_requerida="cozinheiro",
            nivel_minimo=0.0,
            resultado_nome="carne_assada",
            resultado_quantidade=1,
            resultado_descricao="Carne assada saborosa e nutriente",
            xp_ganho=10,
            dificuldade=0.1
        ))
        
        self.adicionar(Receita(
            id="preparar_sopa",
            nome="Preparar Sopa",
            descricao="Fazer sopa nutritiva com vários ingredientes",
            tipo=TipoReceita.COZINHA,
            materiais={"comida": 2, "água": 1, "ervas": 1},
            habilidade_requerida="cozinheiro",
            nivel_minimo=0.2,
            resultado_nome="sopa",
            resultado_quantidade=3,
            resultado_descricao="Sopa quente e nutritiva (restaura muita energia)",
            xp_ganho=25,
            dificuldade=0.3
        ))
        
        self.adicionar(Receita(
            id="fazer_pao",
            nome="Fazer Pão",
            descricao="Assar pão com farinha e água",
            tipo=TipoReceita.COZINHA,
            materiais={"colheita": 3, "água": 1},
            habilidade_requerida="cozinheiro",
            nivel_minimo=0.3,
            resultado_nome="pao",
            resultado_quantidade=4,
            resultado_descricao="Pão fresco e quente",
            xp_ganho=30,
            dificuldade=0.4
        ))

        # === AGRICULTURA ===

        self.adicionar(Receita(
            id="plantar",
            nome="Plantar e Cultivar",
            descricao="Plantar sementes, regar e colher",
            tipo=TipoReceita.PROCESSAMENTO,
            materiais={"colheita": 1, "água": 2},
            habilidade_requerida="agricultor",
            nivel_minimo=0.1,
            resultado_nome="colheita",
            resultado_quantidade=4,
            resultado_descricao="Colheita fresca da roça",
            xp_ganho=25,
            dificuldade=0.2,
            tempo_crafting=3
        ))

        self.adicionar(Receita(
            id="adubar_solo",
            nome="Adubar e Preparar Solo",
            descricao="Preparar terra para plantio com adubo natural",
            tipo=TipoReceita.PROCESSAMENTO,
            materiais={"colheita": 2, "água": 1, "grama": 2},
            habilidade_requerida="agricultor",
            nivel_minimo=0.3,
            resultado_nome="colheita",
            resultado_quantidade=6,
            resultado_descricao="Colheita abundante com solo preparado",
            xp_ganho=40,
            dificuldade=0.4,
            tempo_crafting=5
        ))

        self.adicionar(Receita(
            id="fazer_refeicao",
            nome="Fazer Refeição Completa",
            descricao="Preparar refeição balanceada",
            tipo=TipoReceita.COZINHA,
            materiais={"carne_assada": 1, "sopa": 1, "pao": 2},
            habilidade_requerida="cozinheiro",
            nivel_minimo=0.5,
            resultado_nome="refeicao",
            resultado_quantidade=1,
            resultado_descricao="Refeição completa e deliciosa",
            xp_ganho=50,
            dificuldade=0.5
        ))
        
        # === MEDICINA ===
        
        self.adicionar(Receita(
            id="fazer_bandagem",
            nome="Fazer Bandagem",
            descricao="Higienizar e preparar bandagem",
            tipo=TipoReceita.MEDICINA,
            materiais={"ervas": 2},
            habilidade_requerida="medico",
            nivel_minimo=0.0,
            resultado_nome="bandagem",
            resultado_quantidade=2,
            resultado_descricao="Bandagem limpa para ferimentos",
            xp_ganho=15,
            dificuldade=0.2
        ))
        
        self.adicionar(Receita(
            id="preparar_po_cura",
            nome="Preparar Pó de Cura",
            descricao="Misturar ervas para criar pó cicatrizante",
            tipo=TipoReceita.MEDICINA,
            materiais={"ervas": 4, "cristais": 1},
            habilidade_requerida="medico",
            nivel_minimo=0.3,
            resultado_nome="po_cura",
            resultado_quantidade=2,
            resultado_descricao="Pó que acelera cicatrização",
            xp_ganho=40,
            dificuldade=0.5
        ))
        
        self.adicionar(Receita(
            id="preparar_remedio",
            nome="Preparar Remédio",
            descricao="Criar remédio para doenças",
            tipo=TipoReceita.MEDICINA,
            materiais={"ervas": 5, "cristais": 2, "água": 2},
            habilidade_requerida="medico",
            nivel_minimo=0.5,
            resultado_nome="remedio",
            resultado_quantidade=1,
            resultado_descricao="Remédio eficaz contra doenças",
            xp_ganho=60,
            dificuldade=0.6
        ))
        
        # === ALIMENTOS ESPECIAIS ===
        
        self.adicionar(Receita(
            id="defumar_carne",
            nome="Defumar Carne",
            descricao="Preservar carne defumando",
            tipo=TipoReceita.COZINHA,
            materiais={"carne_assada": 3, "madeira": 2},
            habilidade_requerida="cozinheiro",
            nivel_minimo=0.4,
            resultado_nome="carne_defumada",
            resultado_quantidade=3,
            resultado_descricao="Carne que dura dias sem estragar",
            xp_ganho=35,
            dificuldade=0.4
        ))
        
        self.adicionar(Receita(
            id="fazer_molho",
            nome="Fazer Molho",
            descricao="Preparar molho saboroso com ervas",
            tipo=TipoReceita.COZINHA,
            materiais={"ervas": 2, "água": 1},
            habilidade_requerida="cozinheiro",
            nivel_minimo=0.3,
            resultado_nome="molho",
            resultado_quantidade=3,
            resultado_descricao="Molho que melhora qualquer refeição",
            xp_ganho=25,
            dificuldade=0.3
        ))
    
    def adicionar(self, receita: Receita):
        """Adiciona receita ao banco"""
        self.receitas[receita.id] = receita
    
    def get_receita(self, id: str) -> Optional[Receita]:
        """Retorna receita pelo ID"""
        return self.receitas.get(id)
    
    def receitas_por_tipo(self, tipo: TipoReceita) -> list[Receita]:
        """Retorna receitas de um tipo específico"""
        return [r for r in self.receitas.values() if r.tipo == tipo]
    
    def receitas_para_habilidade(self, habilidade: str) -> list[Receita]:
        """Retorna receitas que usam determinada habilidade"""
        return [r for r in self.receitas.values() 
                if r.habilidade_requerida == habilidade]
    
    def pode_craftar(
        self,
        receita: Receita,
        materiais: dict[str, int],
        habilidades: dict[str, float]
    ) -> tuple[bool, str]:
        """
        Verifica se pode realizar o crafting
        
        Returns:
            (pode_craftar, motivo_se_nao)
        """
        # Verificar materiais
        for mat, qtd_necessaria in receita.materiais.items():
            qtd_disponivel = materiais.get(mat, 0)
            if qtd_disponivel < qtd_necessaria:
                return False, f"Falta {mat}: tem {qtd_disponivel}, precisa {qtd_necessaria}"
        
        # Verificar habilidade
        if receita.habilidade_requerida:
            nivel = habilidades.get(receita.habilidade_requerida, 0.0)
            if nivel < receita.nivel_minimo:
                return False, f"Habilidade '{receita.habilidade_requerida}' muito baixa ({nivel:.0%})"
        
        return True, ""
    
    def listar_receitas_possiveis(
        self,
        materiais: dict[str, int],
        habilidades: dict[str, float]
    ) -> list[Receita]:
        """Lista receitas que o personagem pode fazer (skill OK)"""
        possiveis = []
        for receita in self.receitas.values():
            pode, _ = self.pode_craftar(receita, materiais, habilidades)
            if pode:
                possiveis.append(receita)
        return possiveis
    
    def listar_receitas_por_materiais(
        self,
        materiais: dict[str, int],
    ) -> list[Receita]:
        """
        Lista receitas onde os materiais estão disponíveis (ignora skill).
        Usado para oferecer tentativas experimentais.
        """
        resultados = []
        for receita in self.receitas.values():
            materiais_ok = all(
                materiais.get(mat, 0) >= qtd
                for mat, qtd in receita.materiais.items()
            )
            if materiais_ok:
                resultados.append(receita)
        return resultados


# =============================================================================
# MOTOR DE CRAFTING
# =============================================================================

class MotorCrafting:
    """
    Processa tentativas de crafting
    """
    
    def __init__(self):
        self.banco = BancoReceitas()
    
    def tentar_crafting(
        self,
        receita: Receita,
        materiais: dict[str, int],
        nivel_habilidade: float,
        bonus_qualidade: float = 1.0
    ) -> ResultadoCraftingFinal:
        """
        Tenta realizar o crafting
        """
        # Calcular chance de sucesso
        chance_sucesso = self._calcular_chance_sucesso(
            receita, nivel_habilidade, materiais
        )
        
        # Rolar resultado
        resultado_rolagem = random.random()
        
        # Determinar resultado
        if resultado_rolagem < chance_sucesso:
            # SUCESSO
            resultado = ResultadoCrafting.SUCESSO
            itens = [(receita.resultado_nome, receita.resultado_quantidade)]
            xp = receita.xp_ganho * 2  # XP dobrado para aprendizado mais rápido
            mensagem = f"✅ {receita.nome} concluído com sucesso!"
            
        elif resultado_rolagem < chance_sucesso + 0.2:
            # FALHA PARCIAL (perde metade dos materiais)
            resultado = ResultadoCrafting.FALHA_PARCIAL
            itens = []
            xp = receita.xp_ganho  # metade do XP base (base*2/2 = base)
            mensagem = f"⚠️ {receita.nome} falhou parcialmente. Alguns materiais foram perdidos."
            
        elif resultado_rolagem < chance_sucesso + 0.35:
            # FALHA TOTAL (perde tudo)
            resultado = ResultadoCrafting.FALHA_TOTAL
            itens = []
            xp = receita.xp_ganho // 2
            mensagem = f"❌ {receita.nome} falhou completamente! Todos os materiais foram perdidos."
            
        else:
            # FALHA SEGURA (não perde nada)
            resultado = ResultadoCrafting.FALHA_SEGURA
            itens = []
            xp = receita.xp_ganho // 5
            mensagem = f"🔄 Não conseguiu fazer {receita.nome}. Materiais preservados."
        
        # Calcular materiais perdidos
        materiais_perdidos = {}
        if resultado in [ResultadoCrafting.FALHA_PARCIAL, ResultadoCrafting.FALHA_TOTAL]:
            for mat, qtd in receita.materiais.items():
                if resultado == ResultadoCrafting.FALHA_PARCIAL:
                    materiais_perdidos[mat] = qtd // 2
                else:
                    materiais_perdidos[mat] = qtd
        
        return ResultadoCraftingFinal(
            receita=receita,
            resultado=resultado,
            itens_criados=itens,
            materiais_perdidos=materiais_perdidos,
            xp_ganho=xp,
            mensagem=mensagem
        )
    
    def _calcular_chance_sucesso(
        self,
        receita: Receita,
        nivel_habilidade: float,
        materiais: dict[str, int]
    ) -> float:
        """Calcula chance de sucesso"""
        # Base: habilidade - dificuldade
        base = nivel_habilidade - receita.dificuldade + 0.5
        
        # Bonus por ter boa quantidade de material (excesso)
        bonus_material = 0.0
        for mat, qtd in receita.materiais.items():
            disponivel = materiais.get(mat, 0)
            if disponivel > qtd * 1.5:
                bonus_material += 0.05
        
        # Penalty se está no mínimo exato
        penalty = 0.0
        for mat, qtd in receita.materiais.items():
            disponivel = materiais.get(mat, 0)
            if disponivel == qtd:
                penalty += 0.05
        
        chance = base + bonus_material - penalty
        return max(0.05, min(0.95, chance))  # Entre 5% e 95%
    
    def calcular_ganho_xp(
        self,
        receita: Receita,
        resultado: ResultadoCrafting,
        nivel_atual: float
    ) -> int:
        """Calcula XP ganho baseado no resultado"""
        xp_base = receita.xp_ganho
        
        multiplicadores = {
            ResultadoCrafting.SUCESSO: 1.0,
            ResultadoCrafting.FALHA_PARCIAL: 0.5,
            ResultadoCrafting.FALHA_TOTAL: 0.25,
            ResultadoCrafting.FALHA_SEGURA: 0.1
        }
        
        mult = multiplicadores.get(resultado, 0.5)
        
        # Mais XP quando habilidade é baixa (aprendizado rápido)
        bonus_aprendizado = 1.0 + (1.0 - nivel_atual) * 0.5
        
        return int(xp_base * mult * bonus_aprendizado)


# =============================================================================
# SISTEMA DE ENSINO
# =============================================================================

class MotorEnsino:
    """
    Gerencia ensino e aprendizado entre personagens
    """
    
    def __init__(self):
        self.banco = BancoReceitas()
    
    def calcular_ganho_observar(
        self,
        observador_nivel: float,
        mestre_nivel: float
    ) -> tuple[int, float]:
        """
        Calcula ganho ao observar alguém trabalhar
        
        Returns:
            (xp_ganho, novo_nivel_apos_xp)
        """
        # Quanto mais distante o nível, mais aprende
        gap = mestre_nivel - observador_nivel
        
        if gap <= 0:
            return 0, observador_nivel  # Não aprende
        
        # XP baseado na diferença de níveis
        xp = int(gap * 30)
        
        # Diminuir se mestre não é tão bom
        if mestre_nivel < 0.5:
            xp = int(xp * 0.5)
        
        return xp, observador_nivel
    
    def calcular_ganho_ensino(
        self,
        nivel_aluno: float,
        nivel_professor: float,
        tempo_ensino: int = 1  # por aula
    ) -> int:
        """
        Calcula XP ganho ao ser ensinado diretamente
        
        Returns:
            XP ganho pelo aluno
        """
        # Professor precisa ser melhor
        if nivel_professor <= nivel_aluno:
            return 0
        
        # Base: diferença de níveis (máximo 0.5)
        gap = min(0.5, nivel_professor - nivel_aluno)
        
        # XP por aula (mais XP quando mais gap)
        xp = int(gap * 40) + 10  # Mínimo 10 XP por aula
        
        # Bonus se professor é mestre
        if nivel_professor >= 0.8:
            xp = int(xp * 1.5)
        
        # Mais fácil aprender quando iniciante
        if nivel_aluno < 0.3:
            xp = int(xp * 1.3)
        
        return xp
    
    def pode_ensinar(
        self,
        professor_habilidade: Habilidade,
        habilidade_alvo: str
    ) -> tuple[bool, str]:
        """
        Verifica se pode ensinar determinada habilidade
        """
        if professor_habilidade.nome != habilidade_alvo:
            return False, "Não possui essa habilidade"
        
        if not professor_habilidade.pode_ensinar:
            return False, f"Nível muito baixo ({professor_habilidade.nivel:.0%})"
        
        return True, ""
    
    def listar_pode_ensinar(
        self,
        habilidades_professor: dict[str, Habilidade]
    ) -> list[str]:
        """Lista habilidades que pode ensinar"""
        return [
            nome for nome, hab in habilidades_professor.items()
            if hab.pode_ensinar
        ]
    
    def listar_pode_aprender(
        self,
        habilidades_aluno: dict[str, Habilidade],
        habilidades_professor: dict[str, Habilidade]
    ) -> list[str]:
        """
        Lista habilidades que o aluno pode aprender com o professor
        """
        pode_aprender = []
        
        for nome, hab_aluno in habilidades_aluno.items():
            if hab_aluno.pode_aprender_com and nome in habilidades_professor:
                hab_prof = habilidades_professor[nome]
                if hab_prof.nivel > hab_aluno.nivel:
                    pode_aprender.append(nome)
        
        return pode_aprender


# =============================================================================
# CLASSE PRINCIPAL: INVENTÁRIO
# =============================================================================

@dataclass
class Inventario:
    """
    Inventário de materiais e itens de um personagem
    """
    materiais: dict[str, Material] = field(default_factory=dict)
    itens_craftados: dict[str, int] = field(default_factory=dict)
    
    def adicionar_material(self, nome: str, quantidade: int, qualidade: float = 1.0):
        """Adiciona material ao inventário"""
        validade = TEMPOS_VALIDADE.get(nome, -1)
        
        if nome in self.materiais:
            existente = self.materiais[nome]
            total = existente.quantidade + quantidade
            
            # Média ponderada de qualidade
            existente.qualidade = (
                (existente.qualidade * existente.quantidade +
                 qualidade * quantidade) / total
            )
            
            # Média ponderada de validade (só se ambos forem perecíveis)
            if existente.validade >= 0 and validade >= 0:
                existente.validade = (
                    (existente.validade * existente.quantidade +
                     validade * quantidade) / total
                )
            elif validade >= 0:
                existente.validade = validade
            
            existente.quantidade = total
        else:
            self.materiais[nome] = Material(nome, quantidade, qualidade, validade)
    
    def remover_material(self, nome: str, quantidade: int) -> bool:
        """Remove material. Retorna False se não tem suficiente"""
        if nome not in self.materiais:
            return False
        
        if self.materiais[nome].quantidade < quantidade:
            return False
        
        self.materiais[nome].quantidade -= quantidade
        
        if self.materiais[nome].quantidade <= 0:
            del self.materiais[nome]
        
        return True
    
    def tem_material(self, nome: str, quantidade: int) -> bool:
        """Verifica se tem material suficiente"""
        return self.materiais.get(nome, Material(nome, 0)).quantidade >= quantidade
    
    def get_quantidade(self, nome: str) -> int:
        """Retorna quantidade de um material"""
        return self.materiais.get(nome, Material(nome, 0)).quantidade
    
    def adicionar_item(self, nome: str, quantidade: int = 1):
        """Adiciona item craftado"""
        self.itens_craftados[nome] = self.itens_craftados.get(nome, 0) + quantidade
    
    def get_quantidade_itens(self, nome: str) -> int:
        """Retorna quantidade de um item"""
        return self.itens_craftados.get(nome, 0)
    
    def get_materiais_dict(self) -> dict[str, int]:
        """Retorna materiais como dict simples"""
        return {nome: mat.quantidade for nome, mat in self.materiais.items()}
    
    def tick_validade(self) -> list[str]:
        """
        Processa perecibilidade: decrementa validade e remove estragados.
        Retorna lista de materiais que estragaram.
        """
        estragados = []
        remover = []
        
        for nome, mat in self.materiais.items():
            if mat.validade < 0:
                continue  # não perecível
            
            mat.validade -= 1
            
            if mat.validade <= 0:
                estragados.append(nome)
                remover.append(nome)
        
        for nome in remover:
            del self.materiais[nome]
        
        return estragados
    
    def esta_seco(self, nome: str) -> bool:
        """
        Verifica se um material perecível ainda está fresco (validade > 25% do total).
        Materiais não perecíveis sempre retornam True.
        """
        if nome not in self.materiais:
            return False
        mat = self.materiais[nome]
        if mat.validade < 0:
            return True
        total = TEMPOS_VALIDADE.get(nome, 24)
        return mat.validade > total * 0.25
    
    def descricao(self) -> str:
        """Descrição do inventário"""
        linhas = []
        
        if self.materiais:
            linhas.append("📦 Materiais:")
            for nome, mat in sorted(self.materiais.items()):
                perece = ""
                if mat.validade >= 0:
                    total = TEMPOS_VALIDADE.get(nome, 24)
                    if mat.validade < total * 0.25:
                        perece = " ⚠️ estragando"
                    elif mat.validade < total * 0.5:
                        perece = " ⏳ fresco"
                    else:
                        perece = " ✅ fresco"
                linhas.append(f"  - {nome}: {mat.quantidade} ({mat.nivel_descricao}){perece}")
        
        if self.itens_craftados:
            linhas.append("🔧 Itens:")
            for nome, qtd in sorted(self.itens_craftados.items()):
                linhas.append(f"  - {nome}: {qtd}")
        
        if not linhas:
            return "Inventário vazio"
        
        return "\n".join(linhas)


# =============================================================================
# EXEMPLO DE USO
# =============================================================================

if __name__ == "__main__":
    print("=== Teste do Sistema de Habilidades ===\n")
    
    # Criar habilidades
    madeireiro = Habilidade("madeireiro", nivel=0.3)
    construtor = Habilidade("construtor", nivel=0.1)
    
    print(f"Madeireiro: {madeireiro.nivel_descricao} ({madeireiro.nivel:.0%})")
    print(f"Construtor: {construtor.nivel_descricao} ({construtor.nivel:.0%})")
    
    # Ganhar XP
    print("\n--- Ganho de XP ---")
    subiu = madeireiro.ganhar_xp(50)
    print(f"Madeireiro ganhou 50 XP → {madeireiro.nivel_descricao} ({madeireiro.nivel:.0%})")
    if subiu:
        print("  ↑ SUBIU DE NÍVEL!")
    
    # Testar crafting
    print("\n--- Crafting ---")
    motor = MotorCrafting()
    banco = BancoReceitas()
    
    # Verificar se pode fazer machado
    receita = banco.get_receita("fazer_machado")
    materiais = {"pranchas": 3, "pedra": 2, "cordas": 2}
    habilidades = {"ferreiro": 0.5, "construtor": 0.2}
    
    pode, motivo = banco.pode_craftar(receita, materiais, habilidades)
    print(f"Pode fazer machado? {pode}")
    if not pode:
        print(f"  Motivo: {motivo}")
    
    # Tentar craftar
    resultado = motor.tentar_crafting(receita, materiais, nivel_habilidade=0.5)
    print(f"\n{resultado.mensagem}")
    print(f"Itens criados: {resultado.itens_criados}")
    print(f"XP ganho: {resultado.xp_ganho}")
