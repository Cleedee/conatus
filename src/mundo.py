"""
Módulo Mundo — Orquestrador da Simulação Espinozista

Integra todos os componentes:
- Mapa e locais
- Personagens
- Encontros
- Eventos do mundo
- Ciclos de simulação
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable
import random
from datetime import datetime
from collections import defaultdict

from personagem import (
    Personagem,
    TipoEncontro,
    ResultadoEncontro,
    EstadoPersonagem,
    Personalidade
)
from encontros import (
    MotorEncontros,
    EncontroDisponivel,
    EventoMundo,
    OrigemEncontro,
    ResultadoEncontroProcessado,
    DisponibilidadeEncontro
)
from mapa import Mapa, Local, criar_mapa_padrao, Estacao
from llm import AgenteLLM, criar_llm, ConfigLLM
from habilidades import MotorCrafting, BancoReceitas, TipoReceita
from mercado import Mercado, TipoTransacao


# =============================================================================
# ENUMS
# =============================================================================

class FaseSimulacao(Enum):
    """Fases do ciclo de simulação"""
    INICIO = "inicio"
    TICK_MUNDO = "tick_mundo"
    ANALISE_PERSONAGENS = "analise_personagens"
    PROCESSAMENTO_ENCONTROS = "processamento_encontros"
    RESOLUCAO = "resolucao"
    DISPLAY = "display"
    FIM = "fim"


class TipoEventoMundo(Enum):
    """Tipos de eventos que podem ocorrer no mundo"""
    CHUVA = "chuva"
    SECA = "seca"
    TEMPESTADE = "tempestade"
    COLHEITA = "colheita"
    DOENCA = "doenca"
    VISITANTE = "visitante"
    DESCOBERTA = "descoberta"


# =============================================================================
# ESTADO DO MUNDO
# =============================================================================

@dataclass
class EstadoMundo:
    """
    Estado global do mundo da simulação
    """
    # Tempo
    tick_atual: int = 0
    hora: int = 8               # hora do dia (0-23)
    dia: int = 1
    semana: int = 1

    # Estação (muda a cada 7 dias)
    estacao_atual: Estacao = Estacao.PRIMAVERA

    # Estatísticas
    total_encontros: int = 0
    total_encontros_positivos: int = 0
    total_encontros_negativos: int = 0

    # Eventos ativos
    eventos_ativos: list[EventoMundo] = field(default_factory=list)

    # Histórico
    historico: list[dict] = field(default_factory=list)
    
    @property
    def e_dia(self) -> bool:
        """É durante o dia?"""
        return 6 <= self.hora <= 20
    
    @property
    def nome_periodo(self) -> str:
        """Nome do período do dia"""
        if 6 <= self.hora < 12:
            return "manhã"
        elif 12 <= self.hora < 18:
            return "tarde"
        elif 18 <= self.hora <= 20:
            return "entardecer"
        else:
            return "noite"
    
    def avancar_tick(self):
        """Avança um tick"""
        self.tick_atual += 1
        self.hora += 1

        # Reset diário
        if self.hora >= 24:
            self.hora = 0
            self.dia += 1

            # Reset semanal e avançar estação
            if self.dia > 7:
                self.dia = 1
                self.semana += 1
                # Avançar estação: PRIMAVERA → VERAO → OUTONO → INVERNO → PRIMAVERA
                estacoes = list(Estacao)
                idx = estacoes.index(self.estacao_atual)
                self.estacao_atual = estacoes[(idx + 1) % len(estacoes)]

        # Processar eventos
        for evento in self.eventos_ativos:
            evento.avancar_tick()

        # Remover eventos expirados
        self.eventos_ativos = [e for e in self.eventos_ativos if e.ativo]
    
    def registrar_evento(self, descricao: str, detalhes: dict = None):
        """Registra evento no histórico"""
        self.historico.append({
            "tick": self.tick_atual,
            "hora": self.hora,
            "dia": self.dia,
            "descricao": descricao,
            "detalhes": detalhes or {}
        })
        
        # Manter apenas últimos 100
        if len(self.historico) > 100:
            self.historico.pop(0)


# =============================================================================
# GERADOR DE EVENTOS
# =============================================================================

# Pesos de eventos por estação: [CHUVA, SECA, TEMPESTADE, COLHEITA, DOENCA, VISITANTE, DESCOBERTA]
PESOS_EVENTOS_POR_ESTACAO: dict[Estacao, list[float]] = {
    Estacao.PRIMAVERA: [30, 5,  10, 15, 10, 3, 2],
    Estacao.VERAO:     [5,  30, 5,  20, 15, 3, 2],
    Estacao.OUTONO:    [15, 10, 15, 30, 5,  5, 5],
    Estacao.INVERNO:   [10, 15, 15, 5,  25, 3, 2],
}

class GeradorEventos:
    """
    Gera eventos aleatórios no mundo
    """
    
    def __init__(self, seed: int = None):
        if seed is not None:
            random.seed(seed)
    
    def verificar_novo_evento(self, estado: EstadoMundo) -> Optional[EventoMundo]:
        """
        Verifica se deve gerar novo evento (influenciado pela estação)
        """
        # Chance base de evento: 5% por tick
        if random.random() > 0.05:
            return None

        # Escolher tipo de evento com pesos da estação
        pesos = PESOS_EVENTOS_POR_ESTACAO.get(
            estado.estacao_atual,
            [20, 15, 5, 15, 10, 3, 2]
        )
        tipo = random.choices(list(TipoEventoMundo), weights=pesos)[0]

        return self._criar_evento(tipo, estado)
    
    def _criar_evento(
        self,
        tipo: TipoEventoMundo,
        estado: EstadoMundo
    ) -> EventoMundo:
        """Cria evento baseado no tipo"""
        
        if tipo == TipoEventoMundo.CHUVA:
            return EventoMundo(
                id=f"chuva_{estado.tick_atual}",
                nome="Chuva",
                descricao="Chuva cai sobre a região",
                intensidade=random.uniform(0.3, 0.7),
                locais_afetados=["vila", "planicie", "rio", "praia"],
                duracao=random.randint(3, 8),
                tipos_encontro=[TipoEncontro.AMBIENTAL]
            )
        
        elif tipo == TipoEventoMundo.SECA:
            return EventoMundo(
                id=f"seca_{estado.tick_atual}",
                nome="Seca",
                descricao="Período de seca reduz recursos hídricos",
                intensidade=random.uniform(0.4, 0.8),
                locais_afetados=["vila", "planicie", "rio"],
                duracao=random.randint(5, 12),
                tipos_encontro=[TipoEncontro.AMBIENTAL]
            )
        
        elif tipo == TipoEventoMundo.TEMPESTADE:
            return EventoMundo(
                id=f"tempestade_{estado.tick_atual}",
                nome="Tempestade",
                descricao="Tempestade forte com ventos e chuva",
                intensidade=random.uniform(0.6, 0.9),
                locais_afetados=["floresta", "planicie", "praia"],
                duracao=random.randint(2, 5),
                tipos_encontro=[TipoEncontro.AMBIENTAL]
            )
        
        elif tipo == TipoEventoMundo.COLHEITA:
            return EventoMundo(
                id=f"colheita_{estado.tick_atual}",
                nome="Colheita Pronta",
                descricao="Plantações atingiram maturidade",
                intensidade=random.uniform(0.3, 0.5),
                locais_afetados=["planicie"],
                duracao=random.randint(4, 7),
                tipos_encontro=[TipoEncontro.RECURSO]
            )
        
        elif tipo == TipoEventoMundo.DOENCA:
            # Doença afeta aleatoriamente um local
            local = random.choice(["vila", "floresta", "planicie"])
            return EventoMundo(
                id=f"doenca_{estado.tick_atual}",
                nome="Doença",
                descricao="Doença se espalha na região",
                intensidade=random.uniform(0.3, 0.6),
                locais_afetados=[local],
                duracao=random.randint(3, 6),
                tipos_encontro=[TipoEncontro.AMBIENTAL]
            )
        
        elif tipo == TipoEventoMundo.VISITANTE:
            return EventoMundo(
                id=f"visitante_{estado.tick_atual}",
                nome="Visitante",
                descricao="Viajante chega à região",
                intensidade=random.uniform(0.2, 0.4),
                locais_afetados=["vila"],
                duracao=random.randint(2, 4),
                tipos_encontro=[TipoEncontro.SOCIAL]
            )
        
        else:  # DESCOBERTA
            return EventoMundo(
                id=f"descoberta_{estado.tick_atual}",
                nome="Descoberta",
                descricao="Novo local ou recurso encontrado",
                intensidade=random.uniform(0.3, 0.5),
                locais_afetados=["montanha", "caverna", "floresta"],
                duracao=random.randint(3, 5),
                tipos_encontro=[TipoEncontro.COGNITIVO]
            )


# =============================================================================
# SIMULAÇÃO PRINCIPAL
# =============================================================================

class Simulacao:
    """
    Classe principal que orquestra toda a simulação
    """
    
    def __init__(
        self,
        mapa: Mapa = None,
        personagens: list[Personagem] = None,
        callback_display: Callable = None,
        usar_llm: bool = True,
        config_llm: ConfigLLM = None
    ):
        # Componentes
        self.mapa = mapa or criar_mapa_padrao()
        self.personagens = personagens or []
        self.motor_encontros = MotorEncontros()
        self.gerador_eventos = GeradorEventos()
        self.motor_crafting = MotorCrafting()
        self.mercado = Mercado()
        
        # LLM
        self.usar_llm = usar_llm
        if usar_llm:
            llm = criar_llm(config_llm)
            self.agente_llm = AgenteLLM(llm)
        else:
            self.agente_llm = None
        
        # Estado
        self.estado = EstadoMundo()
        
        # Callback para display
        self.callback_display = callback_display or self._display_padrao
    
    # =========================================================================
    # GESTÃO DE PERSONAGENS
    # =========================================================================
    
    def adicionar_personagem(self, personagem: Personagem):
        """Adiciona personagem à simulação"""
        self.personagens.append(personagem)
        
        # Atualizar ocupação do local
        local = self.mapa.get_local(personagem.local_atual)
        if local:
            local.ocupacao_atual += 1
            local.recalcular_nivel(self.personagens)
    
    def remover_personagem(self, personagem_id: str) -> Optional[Personagem]:
        """Remove personagem da simulação"""
        for i, p in enumerate(self.personagens):
            if p.id == personagem_id:
                # Atualizar ocupação
                local = self.mapa.get_local(p.local_atual)
                if local:
                    local.ocupacao_atual = max(0, local.ocupacao_atual - 1)
                
                return self.personagens.pop(i)
        return None
    
    def get_personagem(self, personagem_id: str) -> Optional[Personagem]:
        """Retorna personagem pelo ID"""
        for p in self.personagens:
            if p.id == personagem_id:
                return p
        return None
    
    def personagens_no_local(self, local_id: str) -> list[Personagem]:
        """Retorna personagens num local específico"""
        return [p for p in self.personagens if p.local_atual == local_id]
    
    # =========================================================================
    # CICLO DE SIMULAÇÃO
    # =========================================================================
    
    def tick(self) -> dict:
        """
        Executa um ciclo completo de simulação
        
        Returns:
            Resumo do que aconteceu no tick
        """
        resumo = {
            "tick": self.estado.tick_atual,
            "hora": self.estado.hora,
            "eventos": [],
            "encontros": [],
            "movimentos": [],
            "crafting": [],
            "resumo_geral": ""
        }

        # Reset contador LLM para este tick
        self._llm_chamadas_tick = 0
        # Só usa LLM a cada N ticks
        self._llm_gate = getattr(self, '_llm_gate', 0)
        self._usar_llm_agora = (
            self.agente_llm
            and self.agente_llm.verificar_pronto()
            and self.estado.tick_atual >= self._llm_gate
        )
        if self._usar_llm_agora:
            self._llm_gate = self.estado.tick_atual + 8  # próximo uso daqui 8 ticks

        # 1. AVANÇAR TEMPO E MUNDO
        self._tick_mundo()
        
        # 2. VERIFICAR NOVOS EVENTOS
        novo_evento = self.gerador_eventos.verificar_novo_evento(self.estado)
        if novo_evento:
            self.estado.eventos_ativos.append(novo_evento)
            self.estado.registrar_evento(
                f"Evento: {novo_evento.nome}",
                {"descricao": novo_evento.descricao}
            )
            resumo["eventos"].append(novo_evento.nome)
        
        # 3. PROCESSAR CADA PERSONAGEM
        for personagem in self.personagens:
            resultado_personagem = self._processar_personagem(personagem)
            resumo["encontros"].extend(resultado_personagem["encontros"])
            resumo["movimentos"].extend(resultado_personagem["movimentos"])
            resumo["crafting"].extend(resultado_personagem["crafting"])
        
        # 4. RESOLVER INTERAÇÕES PENDENTES
        self._resolver_interacoes()
        
        # 5. ATUALIZAR DESENVOLVIMENTO DOS LOCAIS
        for local in self.mapa.locais.values():
            nivel_antes = local.nivel_desenvolvimento
            local.recalcular_nivel(self.personagens)
            if local.nivel_desenvolvimento > nivel_antes:
                nomes = {0: "ermo", 1: "acampamento", 2: "povoado", 3: "vila"}
                self.estado.registrar_evento(
                    f"{local.nome} evoluiu para {nomes[local.nivel_desenvolvimento]}",
                    {"local": local.id, "nivel": local.nivel_desenvolvimento}
                )
        
        # 6. gerar resumo
        resumo["resumo_geral"] = self._gerar_resumo_tick()
        
        # 6. DISPLAY
        self.callback_display(resumo)
        
        return resumo
    
    def _tick_mundo(self):
        """Atualiza estado do mundo"""
        self.estado.avancar_tick()
        self.mapa.tick(self.estado.estacao_atual)
    
    def _processar_personagem(self, personagem: Personagem) -> dict:
        """
        Processa um personagem no tick atual
        """
        resultado = {
            "encontros": [],
            "movimentos": [],
            "decisoes": [],
            "crafting": []
        }
        
        # Se está em movimento, avançar (antes de pode_interagir)
        if personagem.estado == EstadoPersonagem.LOCOMOVENDO:
            self._processar_movimento(personagem)
            return resultado
        
        # Se está dormindo (antes de pode_interagir)
        if personagem.dormindo:
            self._processar_sono(personagem)
            return resultado
        
        # Verificar se pode agir (só para estados ATIVO/ESPERANDO)
        if not personagem.pode_interagir:
            return resultado
        
        # Aplicar clima local nas necessidades
        local = self.mapa.get_local(personagem.local_atual)
        if local:
            personagem.aplicar_clima_local(local.clima_local.value)
        
        # Atualizar necessidades
        personagem.tick_necessidades()
        personagem.tick_afetos()
        
        # Auto-usar medicina se ferido e tiver itens
        if personagem.necessidades.saude < 0.5:
            for med_nome in ("remedio", "po_cura", "bandagem"):
                if personagem.tem_item(med_nome):
                    msg = personagem.usar_item(med_nome)
                    self.estado.registrar_evento(
                        f"{personagem.nome} {msg}",
                        {"personagem": personagem.id, "item": med_nome}
                    )
                    break
        
        # Verificar se deve dormir
        if personagem.decidir_dormir():
            personagem.dormindo = True
            personagem.estado = EstadoPersonagem.DORMINDO
            self.estado.registrar_evento(
                f"{personagem.nome} foi dormir",
                {"personagem": personagem.id}
            )
            return resultado
        
        # Verificar se está em perigo
        local = self.mapa.get_local(personagem.local_atual)
        if local and local.perigo > 0.5 and random.random() < local.perigo * 0.3:
            # Encontro perigoso
            resultado_encontro = self.motor_encontros.processar_encontro(
                personagem,
                EncontroDisponivel(
                    id=f"perigo_{personagem.id}",
                    origem=OrigemEncontro.AMBIENTAL,
                    tipo=TipoEncontro.AMBIENTAL,
                    objeto="perigo_local",
                    descricao=f"Encontro perigoso em {local.nome}",
                    intensidade=local.perigo,
                    resultado_sugerido=ResultadoEncontro.DISSOLUCAO,
                    disponibilidade=DisponibilidadeEncontro.SITUACIONAL
                )
            )
            resultado["encontros"].append({
                "personagem": personagem.nome,
                "tipo": "perigo",
                "resultado": resultado_encontro.resultado.value
            })
        
        # Obter encontros disponíveis
        encontros = self.motor_encontros.obter_encontros_para_personagem(
            personagem,
            self.personagens,
            self.estado.hora,
            self.estado.eventos_ativos
        )
        
        # Adicionar opções de locomoção
        local = self.mapa.get_local(personagem.local_atual)
        if local:
            for destino_id, tempo in local.conexoes.items():
                destino_local = self.mapa.get_local(destino_id)
                if destino_local and not destino_local.lotado:
                    # Verificar se o personagem conhece o destino
                    conhecido = personagem.local_conhecido(destino_id)
                    
                    if conhecido:
                        # Local conhecido - mostrar informações
                        recursos = personagem.get_recursos_conhecidos(destino_id)
                        desc = f"Ir para {destino_local.nome} ({tempo} ticks)"
                        if recursos:
                            desc += f" - recursos: {', '.join(recursos[:2])}"
                    else:
                        # Local desconhecido - mostrar como exploração
                        desc = f"Explorar área desconhecida ({tempo} ticks)"
                    
                    encontros.append(EncontroDisponivel(
                        id=f"mover_{destino_id}",
                        origem=OrigemEncontro.RECURSO,
                        tipo=TipoEncontro.FISICO,
                        objeto=f"mover_{destino_id}",
                        descricao=desc,
                        intensidade=0.1,
                        disponibilidade=DisponibilidadeEncontro.SEMPRE,
                        tag="locomocao"
                    ))
        
        # Adicionar opções de CRAFTING
        materiais_dict = personagem.inventario.get_materiais_dict()
        habilidades_dict = {nome: hab.nivel for nome, hab in personagem.habilidades.items()}
        
        receitas_possiveis = self.motor_crafting.banco.listar_receitas_possiveis(
            materiais_dict, habilidades_dict
        )
        
        for receita in receitas_possiveis[:3]:  # Limitar a 3 opções
            # Construções só são oferecidas se há motivo para construir aqui
            if receita.tipo == TipoReceita.CONSTRUCAO:
                motivo = (
                    personagem.necessidades.abrigo < 0.5
                    or personagem.moradia_local == personagem.local_atual
                    or (local and bool(local.construcoes))
                )
                if not motivo:
                    continue
            
            encontros.append(EncontroDisponivel(
                id=f"craft_{receita.id}",
                origem=OrigemEncontro.RECURSO,
                tipo=TipoEncontro.COGNITIVO,
                objeto=f"craft_{receita.id}",
                descricao=f"🔧 {receita.nome} ({receita.tipo.value})",
                intensidade=0.3,
                disponibilidade=DisponibilidadeEncontro.SEMPRE,
                tag="crafting"
            ))
        
        # Adicionar opções de DEPÓSITO (se personagem tem itens para depositar)
        depositaveis = ["comida", "madeira", "colheita", "pedra", "ferramentas"]
        for dep_rec_nome in depositaveis:
            # Verificar se local aceita esse recurso
            if local:
                rec = local.get_recurso(dep_rec_nome)
                if not rec or not rec.disponivel:
                    continue
            # Verificar inventário
            tem_para_depositar = False
            if dep_rec_nome == "comida":
                for c in ("comida", "carne_assada", "sopa", "pao", "refeicao", "carne_defumada"):
                    if personagem.inventario.tem_material(c, 1):
                        tem_para_depositar = True
                        break
            elif personagem.inventario.tem_material(dep_rec_nome, 1):
                tem_para_depositar = True
            
            if tem_para_depositar:
                encontros.append(EncontroDisponivel(
                    id=f"depositar_{dep_rec_nome}",
                    origem=OrigemEncontro.RECURSO,
                    tipo=TipoEncontro.FISICO,
                    objeto=f"depositar_{dep_rec_nome}",
                    descricao=f"📥 Depositar {dep_rec_nome} no depósito comum",
                    intensidade=0.2,
                    disponibilidade=DisponibilidadeEncontro.SEMPRE,
                    tag="producao"
                ))
        
        # Garantir que sempre haja encontros
        if not encontros:
            encontros.append(EncontroDisponivel(
                id="esperar",
                origem=OrigemEncontro.AMBIENTAL,
                tipo=TipoEncontro.AMBIENTAL,
                objeto="esperar",
                descricao="Esperar e observar o ambiente",
                intensidade=0.05,
                disponibilidade=DisponibilidadeEncontro.SEMPRE,
                tag="esperar"
            ))
        
        # Decidir ação
        encontro_escolhido = None
        decisao_info = {}

        # Usar LLM se disponível (limitado a 1 chamada de decisão por tick)
        usar_llm = self._usar_llm_agora and getattr(self, '_llm_chamadas_tick', 0) < 1
        if usar_llm:
            self._llm_chamadas_tick = getattr(self, '_llm_chamadas_tick', 0) + 1
            contexto = {
                "local": personagem.local_atual,
                "hora": self.estado.hora,
                "outros": self._listar_outros_no_local(personagem)
            }
            decisao = self.agente_llm.decidir_acao(
                personagem, encontros, contexto
            )
            encontro_escolhido = decisao.get("encontro")
            decisao_info = decisao
        
        # Fallback: decisão simples se LLM falhou
        if encontro_escolhido is None:
            encontro_escolhido = self._decidir_acao_simples(personagem, encontros)
        
        # Último fallback: escolher aleatório
        if encontro_escolhido is None and encontros:
            encontro_escolhido = random.choice(encontros)
        
        # Registrar pensamento
        if decisao_info:
            resultado["decisoes"].append({
                "personagem": personagem.nome,
                "razao": decisao_info.get("razao", ""),
                "emocao": decisao_info.get("emocao", "neutro")
            })
        
        # Processar ação escolhida
        if encontro_escolhido:
            # Verificar se é locomoção
            if encontro_escolhido.objeto.startswith("mover_"):
                destino = encontro_escolhido.objeto.replace("mover_", "")
                if self._iniciar_movimento(personagem, destino):
                    resultado["movimentos"].append({
                        "personagem": personagem.nome,
                        "origem": personagem.local_atual,
                        "destino": destino
                    })
                else:
                    personagem.estado = EstadoPersonagem.ATIVO
            
            # Verificar se é CRAFTING
            elif encontro_escolhido.objeto.startswith("craft_"):
                receita_id = encontro_escolhido.objeto.replace("craft_", "")
                resultado_craft = self._processar_crafting(personagem, receita_id)
                resultado["crafting"].append(resultado_craft)
            
            # Verificar se é DEPÓSITO
            elif encontro_escolhido.objeto.startswith("depositar_"):
                rec_nome = encontro_escolhido.objeto.replace("depositar_", "")
                resultado_dep = self._processar_deposito(personagem, rec_nome)
                resultado["encontros"].append({
                    "personagem": personagem.nome,
                    "tipo": "social",
                    "resultado": resultado_dep["status"],
                    "delta": 0.1,
                    "descricao": resultado_dep["descricao"],
                    "detalhes": resultado_dep["detalhes"],
                    "objeto": encontro_escolhido.objeto
                })
            
            else:
                # Processar encontro normal
                resultado_encontro = self.motor_encontros.processar_encontro(
                    personagem,
                    encontro_escolhido
                )
                
                # Consumir recurso local do mapa, se aplicável
                if resultado_encontro.recurso_consumido:
                    rec_nome = resultado_encontro.recurso_consumido
                    rec_qtd = resultado_encontro.recurso_quantidade
                    local = self.mapa.get_local(personagem.local_atual)
                    if local:
                        recurso = local.get_recurso(rec_nome)
                        if recurso:
                            consumido = recurso.consumir(rec_qtd)
                            if consumido < rec_qtd * 0.5:
                                resultado_encontro.detalhes += f" (⚠️ {rec_nome} escasso)"
                        else:
                            resultado_encontro.detalhes += f" (ℹ️ sem {rec_nome} no local)"
                
                # Aplicar dano à saúde
                if resultado_encontro.dano_saude > 0:
                    personagem.necessidades.saude -= resultado_encontro.dano_saude
                    resultado_encontro.detalhes += f" (-{resultado_encontro.dano_saude:.0%} saúde)"
                
                # Processar depósito no recurso local
                if resultado_encontro.recurso_depositado:
                    rec_nome = resultado_encontro.recurso_depositado
                    rec_qtd = resultado_encontro.recurso_depositado_qtd
                    local = self.mapa.get_local(personagem.local_atual)
                    if local:
                        recurso = local.get_recurso(rec_nome)
                        if recurso:
                            recurso.quantidade_atual = min(
                                recurso.maximo,
                                recurso.quantidade_atual + rec_qtd
                            )
                
                resultado["encontros"].append({
                    "personagem": personagem.nome,
                    "tipo": encontro_escolhido.tipo.value,
                    "resultado": resultado_encontro.resultado.value,
                    "delta": resultado_encontro.delta_potencia,
                    "descricao": encontro_escolhido.descricao,
                    "detalhes": resultado_encontro.detalhes,
                    "objeto": encontro_escolhido.objeto
                })
        
        return resultado
    
    def _decidir_acao_simples(
        self,
        personagem: Personagem,
        encontros: list[EncontroDisponivel]
    ) -> Optional[EncontroDisponivel]:
        """
        Decisão baseada em necessidades E personalidade.
        
        Lógica:
        1. Se necessidades críticas, priorizar sobrevivência
        2. Caso contrário, agir conforme personalidade
        """
        # FASE 1: Necessidades críticas sempre têm prioridade
        if personagem.necessidades.fome < 0.4:
            for e in encontros:
                if "comida" in e.objeto or "comer" in e.descricao.lower():
                    return e
        
        if personagem.necessidades.sede < 0.4:
            for e in encontros:
                if "água" in e.objeto or "poço" in e.objeto or "beber" in e.descricao.lower():
                    return e
        
        # FASE 2: Coleta e crafting quando há materiais
        craftings = [e for e in encontros if e.tag == "crafting"]
        coletas = [e for e in encontros
                   if e.tag in ("recurso", "alimento", "sobrevivencia", "producao")
                   and e.origem != OrigemEncontro.SOCIAL
                   and "mover_" not in e.objeto]
        
        # Se tem receitas disponíveis, chance de craftar
        if craftings and random.random() < 0.35:
            return random.choice(craftings)
        
        # Se não tem materiais no inventário, priorizar coleta
        tem_materiais = any(qtd > 0 for qtd in personagem.inventario.get_materiais_dict().values())
        if not tem_materiais and coletas and random.random() < 0.4:
            return random.choice(coletas)
        
        # Se tem comida demais, chance de depositar no local
        depositos = [e for e in encontros if "depositar" in e.objeto]
        if depositos and random.random() < 0.15:
            return random.choice(depositos)
        
        # FASE 3: Personalidade guia ações
        arquetipo = personagem.personalidade.arquetipo
        
        # Filósofo: busca conhecimento, reflexão, conversas profundas
        if arquetipo == "filosofo":
            prioritarios = ["cognitivo", "reflexao", "conhecimento"]
            for e in encontros:
                if any(p in e.tag.lower() or p in e.descricao.lower() for p in prioritarios):
                    return e
            # Social intelectual
            sociais = [e for e in encontros if e.origem == OrigemEncontro.SOCIAL]
            if sociais:
                return random.choice(sociais)
        
        # Ativo: busca aventura, exploração, ação
        elif arquetipo == "ativo":
            prioritarios = ["aventura", "explorar", "locomocao", "risco"]
            # Preferir se mover para novos locais
            movimentos = [e for e in encontros if "mover_" in e.objeto]
            if movimentos and random.random() < 0.4:
                return random.choice(movimentos)
            for e in encontros:
                if any(p in e.tag.lower() or p in e.descricao.lower() for p in prioritarios):
                    return e
        
        # Prudente: busca segurança, planejamento, recursos
        elif arquetipo == "prudente":
            prioritarios = ["seguranca", "recurso", "planejamento", "crafting"]
            for e in encontros:
                if any(p in e.tag.lower() or p in e.descricao.lower() for p in prioritarios):
                    return e
            # Evitar perigos
            seguros = [e for e in encontros if e.origem != OrigemEncontro.AMBIENTAL or e.intensidade < 0.3]
            if seguros:
                return random.choice(seguros)
        
        # Generoso: busca ajudar outros, interação social
        elif arquetipo == "generoso":
            prioritarios = ["social", "ajuda", "ajudar"]
            sociais = [e for e in encontros if e.origem == OrigemEncontro.SOCIAL]
            if sociais:
                return random.choice(sociais)
            for e in encontros:
                if any(p in e.tag.lower() or p in e.descricao.lower() for p in prioritarios):
                    return e
        
        # Dominador: busca poder, controle, recursos valiosos
        elif arquetipo == "dominador":
            prioritarios = ["poder", "recurso", "controle", "mineral", "crafting"]
            for e in encontros:
                if any(p in e.tag.lower() or p in e.descricao.lower() for p in prioritarios):
                    return e
        
        # Medo: busca segurança, evita riscos
        elif arquetipo == "medo":
            # Preferir locais seguros
            locais_seguros = [e for e in encontros if e.origem == OrigemEncontro.RECURSO and e.intensidade < 0.3]
            if locais_seguros:
                return random.choice(locais_seguros)
            # Evitar perigos
            seguros = [e for e in encontros if "perigo" not in e.tag.lower() and e.intensidade < 0.4]
            if seguros:
                return random.choice(seguros)
        
        # Fallback baseado em necessidades restantes
        # Se energia baixa, descansar
        if personagem.necessidades.energia < 0.5:
            for e in encontros:
                if "descansar" in e.descricao.lower() or "esperar" in e.objeto:
                    return e
        
        # Qualquer social
        sociais = [e for e in encontros if e.origem == OrigemEncontro.SOCIAL]
        if sociais and random.random() < 0.4:
            return random.choice(sociais)
        
        # Fallback: qualquer um
        return random.choice(encontros) if encontros else None
    
    def _iniciar_movimento(self, personagem: Personagem, destino_id: str) -> bool:
        """Inicia movimento de personagem para destino. Retorna False se barrado."""
        local_destino = self.mapa.get_local(destino_id)
        local_origem = self.mapa.get_local(personagem.local_atual)
        
        # Verificar requer_ferramentas do destino
        if local_destino and local_destino.requer_ferramentas:
            tem_picareta = personagem.tem_item("picareta")
            tem_machado = personagem.tem_item("machado")
            if not (tem_picareta or tem_machado):
                self.estado.registrar_evento(
                    f"{personagem.nome} não consegue entrar em {local_destino.nome}: precisa de picareta ou machado",
                    {"personagem": personagem.id, "destino": destino_id}
                )
                return False
        
        if local_origem and destino_id in local_origem.conexoes:
            tempo = local_origem.conexoes[destino_id]
            
            personagem.estado = EstadoPersonagem.LOCOMOVENDO
            personagem.destino = destino_id
            personagem.ticks_restantes = tempo
            
            # Atualizar ocupação
            local_origem.ocupacao_atual = max(0, local_origem.ocupacao_atual - 1)
            return True
        return False
    
    def _processar_movimento(self, personagem: Personagem):
        """Processa movimento em andamento"""
        if hasattr(personagem, 'ticks_restantes') and personagem.ticks_restantes > 0:
            personagem.ticks_restantes -= 1
            
            if personagem.ticks_restantes <= 0:
                # Chegou ao destino
                destino = personagem.destino
                personagem.local_atual = destino
                personagem.estado = EstadoPersonagem.ATIVO
                
                # Atualizar ocupação
                local = self.mapa.get_local(destino)
                if local:
                    local.ocupacao_atual += 1
                    
                    # DESCORBRIR LOCAL!
                    recursos_nomes = [r.nome for r in local.recursos]
                    if not personagem.local_conhecido(destino):
                        personagem.descobrir_local(
                            destino,
                            recursos_nomes,
                            local.perigo
                        )
                        self.estado.registrar_evento(
                            f"{personagem.nome} descobriu {local.nome}! Recursos: {', '.join(recursos_nomes)}",
                            {"personagem": personagem.id, "descoberta": destino}
                        )
                
                self.estado.registrar_evento(
                    f"{personagem.nome} chegou a {local.nome if local else destino}",
                    {"personagem": personagem.id, "destino": destino}
                )
    
    def _processar_sono(self, personagem: Personagem):
        """Processa sono do personagem"""
        # Recuperar necessidades
        personagem.necessidades.energia += 0.08
        personagem.necessidades.saude += 0.02  # sono recupera saúde
        
        # Abrigo recupera melhor na própria moradia
        if personagem.tem_moradia and personagem.local_atual == personagem.moradia_local:
            personagem.necessidades.abrigo += 0.02
            personagem.necessidades.saude += 0.02  # dormir em casa recupera mais
        else:
            personagem.necessidades.abrigo += 0.005  # dormir ao relento
        
        personagem.necessidades.normalizar()
        
        # Acordar quando energia alta
        if personagem.necessidades.energia > 0.8:
            personagem.dormindo = False
            personagem.estado = EstadoPersonagem.ATIVO
            self.estado.registrar_evento(
                f"{personagem.nome} acordou",
                {"personagem": personagem.id}
            )
    
    def _processar_crafting(self, personagem: Personagem, receita_id: str) -> dict:
        """
        Processa uma tentativa de crafting
        """
        receita = self.motor_crafting.banco.get_receita(receita_id)
        if not receita:
            return {"erro": "Receita não encontrada"}
        
        # Verificar se pode craftar
        materiais_dict = personagem.inventario.get_materiais_dict()
        habilidades_dict = {nome: hab.nivel for nome, hab in personagem.habilidades.items()}
        
        pode, motivo = self.motor_crafting.banco.pode_craftar(
            receita, materiais_dict, habilidades_dict
        )
        
        if not pode:
            return {
                "personagem": personagem.nome,
                "receita": receita.nome,
                "sucesso": False,
                "motivo": motivo
            }
        
        # Remover materiais
        for mat, qtd in receita.materiais.items():
            personagem.inventario.remover_material(mat, qtd)
        
        # Tentar crafting
        nivel_habilidade = personagem.get_nivel_habilidade(receita.habilidade_requerida)
        resultado = self.motor_crafting.tentar_crafting(
            receita, materiais_dict, nivel_habilidade
        )
        
        # Aplicar resultado
        if resultado.itens_criados:
            for nome, qtd in resultado.itens_criados:
                personagem.inventario.adicionar_item(nome, qtd)
        
        # Ganhar XP
        if resultado.xp_ganho > 0:
            personagem.ganhar_xp(receita.habilidade_requerida, resultado.xp_ganho)
        
        # Se for construção, registrar no local
        local = self.mapa.get_local(personagem.local_atual)
        if local and receita.tipo == TipoReceita.CONSTRUCAO and resultado.itens_criados:
            for nome, qtd in resultado.itens_criados:
                for _ in range(qtd):
                    local.adicionar_construcao(nome)
            # Pode reivindicar moradia se construiu abrigo/cabana
            if resultado.resultado.value == "sucesso":
                for nome, qtd in resultado.itens_criados:
                    if nome in ("abrigo", "cabana"):
                        personagem.moradia_local = local.id
                        personagem.tem_moradia = True
                        break
        
        # Registrar evento
        self.estado.registrar_evento(
            f"{personagem.nome} {resultado.mensagem}",
            {
                "personagem": personagem.id,
                "receita": receita.nome,
                "sucesso": resultado.resultado.value
            }
        )
        
        # Registrar no histórico do personagem
        personagem.historico_crafting.append({
            "tick": self.estado.tick_atual,
            "receita": receita.nome,
            "sucesso": resultado.resultado.value == "sucesso",
            "itens": resultado.itens_criados,
            "xp": resultado.xp_ganho
        })
        if len(personagem.historico_crafting) > 20:
            personagem.historico_crafting.pop(0)
        
        # Observadores: outros no mesmo local percebem a skill sendo usada
        for outro in self.personagens:
            if outro.id == personagem.id:
                continue
            if outro.local_atual != personagem.local_atual:
                continue
            if not outro.pode_interagir:
                continue
            # Encontro observacional
            obs_encontro = EncontroDisponivel(
                id=f"obs_craft_{outro.id}_{receita.id}",
                origem=OrigemEncontro.OBSERVACIONAL,
                tipo=TipoEncontro.OBSERVACIONAL,
                objeto=f"craft_{receita.id}",
                descricao=f"{personagem.nome} está {receita.nome.lower()}",
                intensidade=0.15,
                disponibilidade=DisponibilidadeEncontro.RARO,
                tag="observacao_craft"
            )
            self.motor_encontros.processar_encontro_observacional(outro, obs_encontro)
            # Registrar skill observada
            if resultado.resultado.value == "sucesso":
                outro.observar_skill(
                    personagem.id, receita.habilidade_requerida, nivel_habilidade
                )
        
        return {
            "personagem": personagem.nome,
            "receita": receita.nome,
            "sucesso": resultado.resultado.value == "sucesso",
            "mensagem": resultado.mensagem,
            "itens_criados": resultado.itens_criados,
            "xp_ganho": resultado.xp_ganho
        }
    
    def _processar_deposito(self, personagem: Personagem, rec_nome: str) -> dict:
        """
        Personagem deposita comida/recurso no depósito comum do local.
        """
        local = self.mapa.get_local(personagem.local_atual)
        if not local:
            return {"status": "erro", "descricao": "Local inválido", "detalhes": ""}
        
        recurso = local.get_recurso(rec_nome)
        if not recurso:
            return {"status": "erro", "descricao": f"Sem depósito de {rec_nome} aqui", "detalhes": ""}
        
        # Pegar materiais do inventário que podem ser depositados
        depositaveis = {
            "comida": "comida",
            "carne_assada": "comida",
            "sopa": "comida",
            "pao": "comida",
            "refeicao": "comida",
            "carne_defumada": "comida",
            "colheita": "colheita",
            "madeira": "madeira",
            "pedra": "pedra",
            "cogumelos": "comida",
            "ferramentas": "ferramentas",
        }
        
        if rec_nome not in depositaveis:
            return {"status": "erro", "descricao": f"{rec_nome} não pode ser depositado", "detalhes": ""}
        
        # Encontrar material correspondente no inventário
        ferramentas_nomeadas = {"machado", "picareta", "vara_pesca", "fogueira"}
        mat_alvo = rec_nome
        if rec_nome == "comida":
            mat_alvo = "comida"
            if not personagem.inventario.tem_material(mat_alvo, 1):
                mat_alvo = "carne_assada"
            if not personagem.inventario.tem_material(mat_alvo, 1):
                mat_alvo = "sopa"
            if not personagem.inventario.tem_material(mat_alvo, 1):
                mat_alvo = "pao"
            if not personagem.inventario.tem_material(mat_alvo, 1):
                mat_alvo = "refeicao"
            if not personagem.inventario.tem_material(mat_alvo, 1):
                mat_alvo = "carne_defumada"
        
        if rec_nome == "ferramentas":
            qtd_depositada = 0
            # Tentar depositar item "ferramentas" genérico
            if personagem.tem_item("ferramentas"):
                qtd_depositada = min(3, personagem.inventario.get_quantidade_itens("ferramentas"))
                personagem.remover_item("ferramentas", qtd_depositada)
                mat_alvo = "ferramentas"
            # Se não tem, tentar depositar ferramenta nomeada
            if qtd_depositada == 0:
                for ferr_nome in ferramentas_nomeadas:
                    if personagem.tem_item(ferr_nome):
                        qtd_depositada = 1
                        personagem.remover_item(ferr_nome)
                        mat_alvo = ferr_nome
                        break
            if qtd_depositada == 0:
                return {"status": "erro", "descricao": "Não tem ferramentas para depositar", "detalhes": ""}
        elif not personagem.inventario.tem_material(mat_alvo, 1):
            return {"status": "erro", "descricao": f"Não tem {mat_alvo} para depositar", "detalhes": ""}
        else:
            qtd_depositada = min(3, personagem.inventario.get_quantidade(mat_alvo))
            personagem.inventario.remover_material(mat_alvo, qtd_depositada)
        
        # Recurso local ganha 0.1 por unidade depositada
        ganho_local = qtd_depositada * 0.1
        recurso.quantidade_atual = min(recurso.maximo, recurso.quantidade_atual + ganho_local)
        
        return {
            "status": "sucesso",
            "descricao": f"Depositou {qtd_depositada}x {mat_alvo} no {rec_nome} do {local.nome}",
            "detalhes": f"+{ganho_local:.1f} de {rec_nome} no local"
        }
    
    def _listar_outros_no_local(self, personagem: Personagem) -> str:
        """Lista outros personagens no mesmo local com skills visíveis"""
        outros = [
            p for p in self.personagens
            if p.local_atual == personagem.local_atual and p.id != personagem.id
        ]
        if not outros:
            return "sozinho"
        partes = []
        for p in outros:
            skills_v = personagem.skills_conhecidas_de(p.id)
            itens_v = p.itens_visiveis
            extra = []
            if skills_v:
                extra.append(skills_v)
            if itens_v:
                extra.append(", ".join(itens_v))
            suf = f" ({'; '.join(extra)})" if extra else ""
            partes.append(f"{p.nome}{suf}")
        if len(partes) == 1:
            return partes[0]
        return ", ".join(partes[:-1]) + " e " + partes[-1]
    
    def _resolver_interacoes(self):
        """Resolve interações entre personagens no mesmo local"""
        # Agrupar por local
        locais_com_personagens = {}
        for p in self.personagens:
            if p.pode_interagir:
                if p.local_atual not in locais_com_personagens:
                    locais_com_personagens[p.local_atual] = []
                locais_com_personagens[p.local_atual].append(p)

        llm_pronto = getattr(self, '_usar_llm_agora', False) and self.agente_llm.verificar_pronto()

        # Verificar encontros sociais
        for local_id, personagens in locais_com_personagens.items():
            if len(personagens) >= 2:
                # Chance de encontro social
                if random.random() < 0.3:  # 30% por tick
                    p1, p2 = random.sample(personagens, 2)
                    r1, r2 = self.motor_encontros.processar_encontro_social(p1, p2)

                    # DIÁLOGO VIA LLM (30% dos encontros sociais, 1 chamada)
                    dialogo = None
                    if llm_pronto and random.random() < 0.3 and getattr(self, '_llm_chamadas_tick', 0) < 1:
                        self._llm_chamadas_tick = getattr(self, '_llm_chamadas_tick', 0) + 1
                        try:
                            ctx = f"{p1.nome} e {p2.nome} se encontram em {local_id}."
                            resp1 = self.agente_llm.gerar_resposta_social(p1, p2, ctx)
                            resp2 = self.agente_llm.gerar_resposta_social(p2, p1, ctx)
                            dialogo = {
                                f"{p1.nome}": resp1.get("fala", "..."),
                                f"{p2.nome}": resp2.get("fala", "..."),
                                f"tom_{p1.nome}": resp1.get("tom", "neutro"),
                                f"tom_{p2.nome}": resp2.get("tom", "neutro"),
                            }
                            self.estado.registrar_evento(
                                f"💬 {p1.nome} e {p2.nome} conversaram",
                                {"dialogo": dialogo, "local": local_id}
                            )
                        except Exception:
                            pass  # LLM falhou, segue sem diálogo

                    # OBSERVAÇÃO VIA LLM
                    if llm_pronto and random.random() < 0.3 and getattr(self, '_llm_chamadas_tick', 0) < 1:
                        observadores = [
                            o for o in personagens
                            if o.id not in (p1.id, p2.id)
                        ]
                        if observadores and random.random() < 0.5:
                            try:
                                obs = random.choice(observadores)
                                cena = f"{p1.nome} e {p2.nome} estão interagindo em {local_id}."
                                obs_result = self.agente_llm.interpretar_observacao(obs, cena)
                                self.estado.registrar_evento(
                                    f"👁 {obs.nome} observa {p1.nome} e {p2.nome}",
                                    {
                                        "observador": obs.nome,
                                        "interpretacao": obs_result.get("interpretacao", ""),
                                        "reacao": obs_result.get("reacao_interna", ""),
                                        "mudou_opiniao": obs_result.get("mudanca_opiniao", False)
                                    }
                                )
                            except Exception:
                                pass

                    # COMPARTILHAR CONHECIMENTO!
                    locais_novos_p1 = p1.compartilhar_conhecimento(p2)
                    locais_novos_p2 = p2.compartilhar_conhecimento(p1)

                    total_novos = len(locais_novos_p1) + len(locais_novos_p2)
                    if total_novos > 0:
                        self.estado.registrar_evento(
                            f"{p1.nome} e {p2.nome} trocaram informações sobre {total_novos} local(is)",
                            {
                                "personagens": [p1.id, p2.id],
                                "locais_novos": locais_novos_p1 + locais_novos_p2
                            }
                        )

                    # ENSINO AUTOMÁTICO!
                    self._tentar_ensino(p1, p2)
                    self._tentar_ensino(p2, p1)

                    # TROCA AUTOMÁTICA!
                    self._tentar_troca(p1, p2)

                    if not dialogo:
                        self.estado.registrar_evento(
                            f"{p1.nome} e {p2.nome} interagiram",
                            {
                                "personagens": [p1.id, p2.id],
                                "local": local_id
                            }
                        )
    
    def _tentar_ensino(self, professor: Personagem, aluno: Personagem):
        """
        Tenta ensinar uma habilidade do professor para o aluno
        """
        from habilidades import MotorEnsino
        motor_ensino = MotorEnsino()
        
        # Encontrar habilidades que professor pode ensinar
        habilidades_prof = professor.habilidades_pode_ensinar()
        
        if not habilidades_prof:
            return
        
        # Escolher uma habilidade aleatória para ensinar
        habilidade_alvo = random.choice(habilidades_prof)
        
        # Verificar se aluno pode aprender
        pode_aprender = aluno.habilidades_pode_aprender(professor)
        
        if habilidade_alvo not in pode_aprender:
            # Aluno já sabe mais ou não tem a habilidade
            if habilidade_alvo in aluno.habilidades:
                if aluno.habilidades[habilidade_alvo].nivel >= professor.habilidades[habilidade_alvo].nivel:
                    return  # Aluno já sabe tanto quanto o professor
            else:
                # Aluno não tem a habilidade, pode aprender do zero
                pass
        
        # Calcular XP de ensino
        nivel_prof = professor.habilidades[habilidade_alvo].nivel
        nivel_aluno = aluno.habilidades.get(habilidade_alvo, None)
        nivel_aluno_val = nivel_aluno.nivel if nivel_aluno else 0.0
        
        xp = motor_ensino.calcular_ganho_ensino(nivel_aluno_val, nivel_prof)
        
        if xp <= 0:
            return
        
        # Aplicar XP
        subiu = aluno.ganhar_xp(habilidade_alvo, xp)
        
        # Registrar evento
        msg = f"{professor.nome} ensinou {habilidade_alvo} para {aluno.nome}"
        if subiu:
            msg += f" (subiu de nível!)"
        
        self.estado.registrar_evento(
            msg,
            {
                "tipo": "ensino",
                "professor": professor.id,
                "aluno": aluno.id,
                "habilidade": habilidade_alvo,
                "xp": xp
            }
        )
    
    def _tentar_troca(self, proponente: Personagem, receptor: Personagem):
        """
        Tenta realizar uma troca entre personagens
        """
        # Verificar se há necessidade
        precisa_de_algo = (
            proponente.necessidades.fome < 0.5 or
            proponente.necessidades.sede < 0.5
        )
        
        if not precisa_de_algo:
            return
        
        # Gerar propostas
        propostas = self.mercado.gerar_propostas_automaticas(
            proponente, [receptor]
        )
        
        if not propostas:
            return
        
        # Tentar executar primeira proposta
        proposta = propostas[0]
        
        # Receptor avalia
        aceita, motivo = self.mercado.avaliar_proposta(proposta, receptor)
        
        if aceita:
            resultado = self.mercado.executar_troca(proposta, proponente, receptor)
            
            if resultado["sucesso"]:
                self.estado.registrar_evento(
                    f"{proponente.nome} trocou com {receptor.nome}: " +
                    f"{[f'{qtd} {nome}' for nome, qtd in proposta.ofertando]} por " +
                    f"{[f'{qtd} {nome}' for nome, qtd in proposta.pedindo]}",
                    {
                        "tipo": "troca",
                        "proponente": proponente.id,
                        "receptor": receptor.id
                    }
                )
    
    def _gerar_resumo_tick(self) -> str:
        """Gera resumo textual do tick"""
        linhas = []
        
        linhas.append(f"⏰ Tick {self.estado.tick_atual} | Dia {self.estado.dia} | {self.estado.nome_periodo} ({self.estado.hora}:00)")
        
        # Personagens
        if self.personagens:
            linhas.append(f"👥 {len(self.personagens)} personagens:")
            for p in self.personagens:
                estado = "💤" if p.dormindo else "🚶" if p.estado == EstadoPersonagem.LOCOMOVENDO else "🧑"
                linhas.append(f"   {estado} {p.nome} em {p.local_atual} (potência: {p.potencia_atual:.0%})")
        
        # Eventos
        if self.estado.eventos_ativos:
            linhas.append(f"🎯 Eventos ativos:")
            for e in self.estado.eventos_ativos:
                linhas.append(f"   - {e.nome}: {e.descricao} ({e.duracao - e.tick_atual} ticks restantes)")
        
        return "\n".join(linhas)
    
    # =========================================================================
    # DISPLAY
    # =========================================================================
    
    def _display_padrao(self, resumo: dict):
        """Display padrão no terminal"""
        print("\n" + "=" * 60)
        print(resumo["resumo_geral"])

        # Mostrar diálogos e observações do histórico recente
        for h in self.estado.historico[-5:]:
            detalhes = h.get("detalhes", {})
            if "dialogo" in detalhes:
                d = detalhes["dialogo"]
                for nome, fala in d.items():
                    if nome.startswith("tom_"):
                        continue
                    print(f"   💬 {nome}: \"{fala}\"")
            if "interpretacao" in detalhes:
                print(f"   👁 {detalhes.get('observador', '?')}: \"{detalhes['interpretacao']}\"")

        if resumo["encontros"]:
            print("\n📚 Encontros:")
            for e in resumo["encontros"]:
                emoji = "✅" if e.get("resultado") == "adequacao" else "❌" if e.get("resultado") == "dissolucao" else "➖"
                desc = e.get("detalhes") or e.get("descricao", "")
                print(f"   {emoji} {e['personagem']}: {desc} ({e.get('delta', 0):+.2f})")

        if resumo["movimentos"]:
            print("\n🚶 Movimentos:")
            for m in resumo["movimentos"]:
                print(f"   {m['personagem']}: {m['origem']} → {m['destino']}")

        if resumo.get("crafting"):
            print("\n🔧 Crafting:")
            for c in resumo["crafting"]:
                emoji = "✅" if c.get("sucesso") else "❌"
                print(f"   {emoji} {c.get('personagem', '?')}: {c.get('mensagem', '')}")

        print("=" * 60)
    
    # =========================================================================
    # CONTROLES
    # =========================================================================
    
    def rodar(self, ticks: int = None):
        """
        Roda a simulação
        
        Args:
            ticks: Número de ticks para rodar (None = infinito)
        """
        print("\n🚀 INICIANDO SIMULAÇÃO")
        print("=" * 60)
        print(self.mapa.descrever_mundo())
        print("\n👥 PERSONAGENS:")
        for p in self.personagens:
            print(f"   - {p.nome} ({p.personalidade.arquetipo}) em {p.local_atual}")
        print("=" * 60)
        
        tick_count = 0
        try:
            while ticks is None or tick_count < ticks:
                self.tick()
                tick_count += 1
                
                # Pausa a cada 10 ticks
                if tick_count % 10 == 0:
                    input("\n[Enter para continuar...]")
        
        except KeyboardInterrupt:
            print("\n\n⏹️  Simulação interrompida")
        
        self._mostrar_estatisticas_finais()
    
    def rodar_interativo(self, ticks_iniciais: int = 0):
        """
        Roda a simulação em modo interativo.
        
        Comandos disponíveis:
          olhar <local>          — detalhes de um local
          quem                   — lista todos personagens e onde estão
          quem <local>           — personagens num local específico
          personagem <nome>      — ficha completa do personagem
          inventario <nome>      — inventário do personagem
          habilidades <nome>     — habilidades do personagem
          relacoes <nome>        — relações do personagem
          conhecimento <nome>    — locais que o personagem conhece
          continuar [n]          — roda n ticks (padrão 1)
          mapa                   — mostra o mapa completo
          tempo                  — hora/dia atual
          ajuda                  — lista de comandos
          sair                   — encerra a simulação
        
        Pressione Tab para autocompletar nomes de locais/personagens.
        """
        import cmd
        
        # Rodar ticks iniciais
        for _ in range(ticks_iniciais):
            if not self._tick_silencioso():
                break
        
        intro = (
            "\n🎮 MODO INTERATIVO"
            "\n   Digite 'ajuda' para comandos ou 'continuar' para avançar."
            "\n   Dica: use Tab para autocompletar nomes.\n"
        )
        
        class REPLSimulacao(cmd.Cmd):
            prompt = "⏳> "
            
            def __init__(self, sim):
                super().__init__()
                self.sim = sim
                self._auto_continuar = False
            
            # ---- utilitários ----
            
            def _nomes_locais(self) -> list[str]:
                return list(self.sim.mapa.locais.keys())
            
            def _nomes_personagens(self) -> list[str]:
                return [p.nome.lower() for p in self.sim.personagens]
            
            def _buscar_personagem(self, nome: str) -> Optional[Personagem]:
                nome = nome.strip().lower()
                for p in self.sim.personagens:
                    if p.nome.lower() == nome:
                        return p
                    if p.id == nome:
                        return p
                return None
            
            def _tick_com_display(self, qtd: int = 1):
                for _ in range(qtd):
                    self.sim.tick()
                    print()
            
            def _formatar_necessidades(self, p: Personagem) -> str:
                n = p.necessidades
                return (f"Energia={n.energia:.0%} Fome={n.fome:.0%} "
                        f"Sede={n.sede:.0%} Abrigo={n.abrigo:.0%} Saúde={n.saude:.0%}")
            
            def _formatar_afetos(self, p: Personagem) -> str:
                a = p.afetos
                return (f"Alegria={a.alegria:.2f} Tristeza={a.tristeza:.2f} "
                        f"Desejo={a.desejo:.2f} Esperança={a.esperanca:.2f} Temor={a.temor:.2f}")
            
            def _barra_vida(self, valor: float, largura: int = 20) -> str:
                preenchido = int(valor * largura)
                return "█" * preenchido + "░" * (largura - preenchido)
            
            # ---- completador ----
            
            def completenames(self, text, *ignored):
                """Tab completion for commands."""
                d = self.completedefault(text, *ignored)
                for cmd_name in self.get_names():
                    if cmd_name.startswith("do_"):
                        name = cmd_name[3:]
                        if name.startswith(text):
                            d.append(name)
                return d
            
            def completedefault(self, text, line, begidx, endidx):
                args = line.split()
                if len(args) <= 1:
                    return []
                cmd = args[0]
                if cmd in ("olhar",):
                    return [n for n in self._nomes_locais() if n.startswith(text)]
                if cmd in ("personagem", "inventario", "habilidades", "relacoes", "conhecimento"):
                    return [n for n in self._nomes_personagens() if n.startswith(text)]
                if cmd == "quem":
                    return [n for n in self._nomes_locais() if n.startswith(text)]
                return []
            
            # ---- comandos ----
            
            def do_olhar(self, arg):
                """olhar <local> — detalhes de um local (recursos, clima, personagens presentes)"""
                if not arg:
                    print("   Use: olhar <local>")
                    return
                local_id = arg.strip().lower()
                local = self.sim.mapa.get_local(local_id)
                if not local:
                    print(f"   Local '{local_id}' não encontrado. Locais: {', '.join(self._nomes_locais())}")
                    return
                
                print()
                print(local.descricao_completa())
                
                # Personagens aqui
                aqui = self.sim.personagens_no_local(local_id)
                if aqui:
                    print(f"\n   👥 Aqui estão:")
                    for p in aqui:
                        estado = "💤" if p.dormindo else "🚶" if p.estado == EstadoPersonagem.LOCOMOVENDO else "🧑"
                        print(f"      {estado} {p.nome} ({p.personalidade.arquetipo}) — potência: {p.potencia_atual:.0%}")
            
            def do_quem(self, arg):
                """quem [local] — lista personagens. Se local for dado, filtra por local."""
                if arg:
                    local_id = arg.strip().lower()
                    local = self.sim.mapa.get_local(local_id)
                    if not local:
                        print(f"   Local '{local_id}' não encontrado.")
                        return
                    personagens = self.sim.personagens_no_local(local_id)
                    if not personagens:
                        print(f"   Ninguém em {local.nome}.")
                        return
                    print(f"\n   👥 Em {local.nome}:")
                    for p in personagens:
                        estado = "💤" if p.dormindo else "🚶" if p.estado == EstadoPersonagem.LOCOMOVENDO else "🧑"
                        print(f"      {estado} {p.nome} ({p.personalidade.arquetipo}) — {self._formatar_necessidades(p)}")
                else:
                    print(f"\n   👥 Personagens ({len(self.sim.personagens)}):")
                    # Agrupar por local
                    from collections import defaultdict
                    por_local = defaultdict(list)
                    for p in self.sim.personagens:
                        por_local[p.local_atual].append(p)
                    
                    for local_id, ps in sorted(por_local.items()):
                        local = self.sim.mapa.get_local(local_id)
                        nome_local = local.nome if local else local_id
                        print(f"\n      📍 {nome_local}:")
                        for p in ps:
                            estado = "💤" if p.dormindo else "🚶" if p.estado == EstadoPersonagem.LOCOMOVENDO else "🧑"
                            print(f"         {estado} {p.nome} ({p.personalidade.arquetipo}) — potência: {p.potencia_atual:.0%}")
            
            def do_personagem(self, arg):
                """personagem <nome> — ficha completa do personagem"""
                if not arg:
                    print("   Use: personagem <nome>")
                    return
                p = self._buscar_personagem(arg)
                if not p:
                    print(f"   Personagem '{arg}' não encontrado.")
                    return
                
                tools_str = ", ".join(p.ferramentas_equipadas) if p.ferramentas_equipadas else "nenhuma"
                moradia_str = f"🏠 {p.moradia_local}" if p.tem_moradia else "🚫 sem moradia"
                print(f"""
   ┌─ {p.nome} ──────────────────────────────────
   │ Arquétipo: {p.personalidade.arquetipo}
   │ Idade: {p.personalidade.idade}
   │ Descrição: {p.personalidade.descricao}
   │
   │ 🌟 Potência: {p.potencia_atual:.0%}  {self._barra_vida(p.potencia_atual)}
   │ 🧠 Razão: {p.razao_vs_paixao:.0%}
   │ 📍 Local: {p.local_atual}
   │ {moradia_str}
   │ 🛠️  Ferramentas: {tools_str}
   │ 🏷️  Estado: {p.estado.value}
   │
   │ 📊 Necessidades:
   │    Energia: {p.necessidades.energia:.0%} {self._barra_vida(p.necessidades.energia)}
   │    Fome:   {p.necessidades.fome:.0%} {self._barra_vida(p.necessidades.fome)}
   │    Sede:   {p.necessidades.sede:.0%} {self._barra_vida(p.necessidades.sede)}
   │    Abrigo: {p.necessidades.abrigo:.0%} {self._barra_vida(p.necessidades.abrigo)}
   │    Saúde:  {p.necessidades.saude:.0%} {self._barra_vida(p.necessidades.saude)}
   │
   │ 💖 Afetos: {self._formatar_afetos(p)}
   │
   │ 📚 Encontros: {p.total_encontros} ({p.total_encontros_positivos}+, {p.total_encontros_negativos}-)
   └─────────────────────────────────────────────""")
            
            def do_inventario(self, arg):
                """inventario <nome> — mostra o inventário do personagem"""
                if not arg:
                    print("   Use: inventario <nome>")
                    return
                p = self._buscar_personagem(arg)
                if not p:
                    print(f"   Personagem '{arg}' não encontrado.")
                    return
                
                desc = p.inventario.descricao()
                print(f"\n   📦 Inventário de {p.nome}:")
                for linha in desc.split("\n"):
                    print(f"     {linha}")
            
            def do_habilidades(self, arg):
                """habilidades <nome> — mostra habilidades do personagem"""
                if not arg:
                    print("   Use: habilidades <nome>")
                    return
                p = self._buscar_personagem(arg)
                if not p:
                    print(f"   Personagem '{arg}' não encontrado.")
                    return
                
                if not p.habilidades:
                    print(f"\n   {p.nome} não tem habilidades.")
                    return
                
                print(f"\n   ⚡ Habilidades de {p.nome}:")
                # Ordenar por nível (maior primeiro)
                for nome, hab in sorted(p.habilidades.items(), key=lambda x: -x[1].nivel):
                    barra = self._barra_vida(hab.nivel, 15)
                    print(f"      {barra} {nome}: {hab.nivel_descricao} ({hab.nivel:.0%})  XP: {hab.experiencia}/{hab.xp_proximo_nivel}")
            
            def do_relacoes(self, arg):
                """relacoes <nome> — mostra relações do personagem"""
                if not arg:
                    print("   Use: relacoes <nome>")
                    return
                p = self._buscar_personagem(arg)
                if not p:
                    print(f"   Personagem '{arg}' não encontrado.")
                    return
                
                if not p.relacoes:
                    print(f"\n   {p.nome} não tem relações registradas.")
                    return
                
                emoji_tipo = {"personagem": "🧑", "local": "📍", "item": "📦", "atividade": "⚡", "clima": "🌤️"}
                print(f"\n   🤝 Relações de {p.nome}:")
                for rid, r in sorted(p.relacoes.items(), key=lambda x: -x[1].afeto):
                    emoji = "❤️" if r.afeto > 0.1 else "💔" if r.afeto < -0.1 else "➖"
                    tipo_emoji = emoji_tipo.get(r.tipo, "❓")
                    print(f"      {emoji} {tipo_emoji} {r.entidade_nome}: {r.sentimento}  afeto={r.afeto:+.2f}")
            
            def do_crafting(self, arg):
                """crafting <nome> — histórico de crafting do personagem"""
                if not arg:
                    print("   Use: crafting <nome>")
                    return
                p = self._buscar_personagem(arg)
                if not p:
                    print(f"   Personagem '{arg}' não encontrado.")
                    return

                if not p.historico_crafting:
                    print(f"\n   {p.nome} nunca craftou nada.")
                    return

                print(f"\n   🔨 Histórico de Crafting de {p.nome}:")
                for h in reversed(p.historico_crafting[-10:]):
                    status = "✅" if h["sucesso"] else "❌"
                    itens = ", ".join(h["itens"]) if h["itens"] else "-"
                    print(f"      {status} Tick {h['tick']} | {h['receita']} → {itens} | XP +{h['xp']}")

            def do_conhecimento(self, arg):
                """conhecimento <nome> — mostra locais conhecidos pelo personagem"""
                if not arg:
                    print("   Use: conhecimento <nome>")
                    return
                p = self._buscar_personagem(arg)
                if not p:
                    print(f"   Personagem '{arg}' não encontrado.")
                    return
                
                print(f"\n   🗺️  Conhecimento de {p.nome}:")
                print(f"      {p.get_contexto_conhecimento()}")
            
            def do_continuar(self, arg):
                """continuar [n] — roda n ticks (padrão 1)"""
                try:
                    n = int(arg) if arg else 1
                except ValueError:
                    n = 1
                if n < 1:
                    n = 1
                self._tick_com_display(n)
            
            def do_auto(self, arg):
                """auto [n] — roda n ticks rapidamente (sem display detalhado entre eles)"""
                try:
                    n = int(arg) if arg else 5
                except ValueError:
                    n = 5
                print(f"   Rodando {n} ticks...")
                for _ in range(n):
                    self.sim.tick()
                print(f"   Tick {self.sim.estado.tick_atual} | Dia {self.sim.estado.dia} {self.sim.estado.nome_periodo} ({self.sim.estado.hora}:00)")
            
            def do_mapa(self, arg):
                """mapa — mostra o mapa completo com todos os locais"""
                print()
                print(self.sim.mapa.descrever_mundo())
            
            def do_tempo(self, arg):
                """tempo — mostra hora/dia atual"""
                e = self.sim.estado
                print(f"\n   ⏰ Tick {e.tick_atual} | Dia {e.dia} | Semana {e.semana} | {e.nome_periodo} ({e.hora}:00)")
                if e.eventos_ativos:
                    print(f"\n   🎯 Eventos ativos:")
                    for ev in e.eventos_ativos:
                        print(f"      - {ev.nome}: {ev.descricao} ({ev.duracao - ev.tick_atual} ticks restantes)")
            
            def do_ajuda(self, arg):
                """ajuda — mostra lista de comandos"""
                print("""
   🎮 COMANDOS:
     olhar <local>          — detalhes de um local
     quem [local]           — lista personagens (no mundo ou num local)
     personagem <nome>      — ficha completa do personagem
     inventario <nome>      — inventário do personagem
     habilidades <nome>     — habilidades do personagem
     relacoes <nome>        — relações do personagem
      crafting <nome>        — histórico de crafting do personagem
      conhecimento <nome>    — locais que o personagem conhece
      continuar [n]          — roda n ticks com display (padrão 1)
      auto [n]               — roda n ticks sem display (padrão 5)
      mapa                   — mostra o mapa completo
      tempo                  — hora/dia e eventos ativos
      ajuda                  — esta mensagem
      sair                   — encerra a simulação
   
   Dica: use Tab para autocompletar nomes de locais e personagens.
                """)
            
            def do_sair(self, arg):
                """sair — encerra a simulação"""
                print("\n   ⏹️  Encerrando simulação...")
                return True
            
            def do_EOF(self, arg):
                return True
            
            # atalhos
            do_q = do_quem
            do_s = do_sair
            do_c = do_continuar
            do_h = do_ajuda
            do_craft = do_crafting
            do_help = do_ajuda
            do_interrogacao = do_ajuda
            
            def default(self, line):
                if line.strip() == '?':
                    return self.do_ajuda('')
                print(f"   Comando desconhecido: {line.strip()}  (digite 'ajuda')")
        
        repl = REPLSimulacao(self)
        try:
            repl.cmdloop(intro)
        except KeyboardInterrupt:
            print()
        self._mostrar_estatisticas_finais()
    
    def _tick_silencioso(self) -> bool:
        """Roda um tick sem display. Retorna False se interrompido."""
        old = self.callback_display
        self.callback_display = lambda x: None
        try:
            self.tick()
            return True
        finally:
            self.callback_display = old
    
    def _mostrar_estatisticas_finais(self):
        """Mostra estatísticas ao final"""
        print("\n" + "=" * 60)
        print("📊 ESTATÍSTICAS FINAIS")
        print("=" * 60)
        
        print(f"\n⏰ Tempo total:")
        print(f"   Ticks: {self.estado.tick_atual}")
        print(f"   Dias: {self.estado.dia}")
        print(f"   Semanas: {self.estado.semana}")
        
        if self.personagens:
            print(f"\n👥 Personagens:")
            for p in self.personagens:
                print(f"\n   {p.nome} ({p.personalidade.arquetipo}):")
                print(f"      Potência: {p.potencia_atual:.0%}")
                print(f"      Razão: {p.razao_vs_paixao:.0%}")
                print(f"      Local: {p.local_atual}")
                print(f"      Encontros: {p.total_encontros} ({p.total_encontros_positivos}+, {p.total_encontros_negativos}-)")
                
                # Top relações
                if p.relacoes:
                    print(f"      Relações:")
                    for rid, r in list(sorted(p.relacoes.items(), key=lambda x: x[1].afeto, reverse=True))[:3]:
                        if r.afeto > 0:
                            print(f"        ❤️ {rid}: {r.afeto:.2f}")
                        elif r.afeto < 0:
                            print(f"        💔 {rid}: {r.afeto:.2f}")
        
        print("\n" + "=" * 60)


# =============================================================================
# CRIAÇÃO RÁPIDA DE SIMULAÇÃO
# =============================================================================

def criar_simulacao_padrao() -> Simulacao:
    """Cria simulação com personagens padrão"""
    mapa = criar_mapa_padrao()
    
    # Criar personagens
    personagens = []
    
    # Maria - Generosa
    maria = Personalidade(
        nome="Maria",
        arquetipo="generoso",
        idade=35,
        descricao="Mulher calorosa que acredita no poder da comunidade",
        razao_innata=0.6,
        motivacoes={
            "sobrevivencia": 0.8,
            "ajudar_outros": 0.9,
            "reputacao": 0.7
        }
    )
    personagens.append(Personagem(maria, local_inicial="vila"))
    
    # João - Prudente
    joao = Personalidade(
        nome="João",
        arquetipo="prudente",
        idade=40,
        descricao="Homem cauteloso que analisa antes de agir",
        razao_innata=0.7,
        motivacoes={
            "sobrevivencia": 0.9,
            "seguranca": 0.8,
            "reputacao": 0.5
        }
    )
    personagens.append(Personagem(joao, local_inicial="vila"))
    
    # Ana - Ativa
    ana = Personalidade(
        nome="Ana",
        arquetipo="ativo",
        idade=28,
        descricao="Jovem energica que age por impulso",
        razao_innata=0.4,
        motivacoes={
            "aventura": 0.8,
            "conquista": 0.7,
            "liberdade": 0.9
        }
    )
    personagens.append(Personagem(ana, local_inicial="planicie"))
    
    # Pedro - Filósofo
    pedro = Personalidade(
        nome="Pedro",
        arquetipo="filosofo",
        idade=55,
        descricao="Velho sábio que busca compreender o mundo",
        razao_innata=0.9,
        motivacoes={
            "conhecimento": 0.9,
            "verdade": 0.8,
            "ensinar": 0.6
        }
    )
    personagens.append(Personagem(pedro, local_inicial="montanha"))
    
    # Lúcia - Medo
    lucia = Personalidade(
        nome="Lúcia",
        arquetipo="medo",
        idade=32,
        descricao="Mulher cautelosa movida pelo temor",
        razao_innata=0.5,
        motivacoes={
            "seguranca": 0.9,
            "protecao": 0.8,
            "estabilidade": 0.7
        }
    )
    personagens.append(Personagem(lucia, local_inicial="vila"))
    
    return Simulacao(mapa=mapa, personagens=personagens)


# =============================================================================
# EXEMPLO DE USO
# =============================================================================

if __name__ == "__main__":
    import sys
    
    sim = criar_simulacao_padrao()
    
    if "--interativo" in sys.argv or "-i" in sys.argv:
        # Extrair ticks iniciais opcionais (ex: -i 5)
        ticks = 0
        for i, arg in enumerate(sys.argv):
            if arg in ("--interativo", "-i") and i + 1 < len(sys.argv):
                try:
                    ticks = int(sys.argv[i + 1])
                except ValueError:
                    pass
        sim.rodar_interativo(ticks_iniciais=ticks)
    else:
        sim.rodar(ticks=20)
