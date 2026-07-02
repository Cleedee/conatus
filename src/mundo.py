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
from mapa import Mapa, Local, criar_mapa_padrao
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
            
            # Reset semanal
            if self.dia > 7:
                self.dia = 1
                self.semana += 1
        
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

class GeradorEventos:
    """
    Gera eventos aleatórios no mundo
    """
    
    def __init__(self, seed: int = None):
        if seed is not None:
            random.seed(seed)
    
    def verificar_novo_evento(self, estado: EstadoMundo) -> Optional[EventoMundo]:
        """
        Verifica se deve gerar novo evento
        """
        # Chance base de evento: 5% por tick
        if random.random() > 0.05:
            return None
        
        # Escolher tipo de evento
        tipo = random.choices(
            list(TipoEventoMundo),
            weights=[20, 15, 5, 15, 10, 3, 2]  # pesos
        )[0]
        
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
            "resumo_geral": ""
        }
        
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
        
        # 4. RESOLVER INTERAÇÕES PENDENTES
        self._resolver_interacoes()
        
        # 5. gerar resumo
        resumo["resumo_geral"] = self._gerar_resumo_tick()
        
        # 6. DISPLAY
        self.callback_display(resumo)
        
        return resumo
    
    def _tick_mundo(self):
        """Atualiza estado do mundo"""
        self.estado.avancar_tick()
        self.mapa.tick()
    
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
        
        # Verificar se pode agir
        if not personagem.pode_interagir:
            return resultado
        
        # Se está em movimento, avançar
        if personagem.estado == EstadoPersonagem.LOCOMOVENDO:
            self._processar_movimento(personagem)
            return resultado
        
        # Se está dormindo
        if personagem.dormindo:
            self._processar_sono(personagem)
            return resultado
        
        # Atualizar necessidades
        personagem.tick_necessidades()
        personagem.tick_afetos()
        
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
                    resultado_sugerido=ResultadoEncontro.DISSOLUCAO
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
        
        # Usar LLM se disponível
        if self.agente_llm and self.agente_llm.verificar_pronto():
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
                self._iniciar_movimento(personagem, destino)
                resultado["movimentos"].append({
                    "personagem": personagem.nome,
                    "origem": personagem.local_atual,
                    "destino": destino
                })
            
            # Verificar se é CRAFTING
            elif encontro_escolhido.objeto.startswith("craft_"):
                receita_id = encontro_escolhido.objeto.replace("craft_", "")
                resultado_craft = self._processar_crafting(personagem, receita_id)
                resultado["crafting"].append(resultado_craft)
            
            else:
                # Processar encontro normal
                resultado_encontro = self.motor_encontros.processar_encontro(
                    personagem,
                    encontro_escolhido
                )
                resultado["encontros"].append({
                    "personagem": personagem.nome,
                    "tipo": encontro_escolhido.tipo.value,
                    "resultado": resultado_encontro.resultado.value,
                    "delta": resultado_encontro.delta_potencia
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
        
        # FASE 2: Personalidade guia ações quando saciado
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
            if movimentos and random.random() < 0.6:
                return random.choice(movimentos)
            for e in encontros:
                if any(p in e.tag.lower() or p in e.descricao.lower() for p in prioritarios):
                    return e
        
        # Prudente: busca segurança, planejamento, recursos
        elif arquetipo == "prudente":
            prioritarios = ["seguranca", "recurso", "planejamento"]
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
            prioritarios = ["poder", "recurso", "controle", "mineral"]
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
        
        # FASE 3: CRAFTING sempre é opção quando disponível
        craftings = [e for e in encontros if hasattr(e, 'tag') and e.tag == "crafting"]
        if craftings:
            # Priorizar crafting se necessidades estão OK
            if (personagem.necessidades.fome > 0.3 and 
                personagem.necessidades.sede > 0.3 and
                random.random() < 0.6):  # 60% chance
                return random.choice(craftings)
        
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
    
    def _iniciar_movimento(self, personagem: Personagem, destino_id: str):
        """Inicia movimento de personagem para destino"""
        local_origem = self.mapa.get_local(personagem.local_atual)
        
        if local_origem and destino_id in local_origem.conexoes:
            tempo = local_origem.conexoes[destino_id]
            
            personagem.estado = EstadoPersonagem.LOCOMOVENDO
            personagem.destino = destino_id
            personagem.ticks_restantes = tempo
            
            # Atualizar ocupação
            local_origem.ocupacao_atual = max(0, local_origem.ocupacao_atual - 1)
    
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
        
        # Registrar evento
        self.estado.registrar_evento(
            f"{personagem.nome} {resultado.mensagem}",
            {
                "personagem": personagem.id,
                "receita": receita.nome,
                "sucesso": resultado.resultado.value
            }
        )
        
        return {
            "personagem": personagem.nome,
            "receita": receita.nome,
            "sucesso": resultado.resultado.value == "sucesso",
            "mensagem": resultado.mensagem,
            "itens_criados": resultado.itens_criados,
            "xp_ganho": resultado.xp_ganho
        }
    
    def _listar_outros_no_local(self, personagem: Personagem) -> str:
        """Lista outros personagens no mesmo local"""
        outros = [
            p.nome for p in self.personagens
            if p.local_atual == personagem.local_atual and p.id != personagem.id
        ]
        if not outros:
            return "Ninguém mais"
        elif len(outros) == 1:
            return outros[0]
        else:
            return ", ".join(outros[:-1]) + " e " + outros[-1]
    
    def _resolver_interacoes(self):
        """Resolve interações entre personagens no mesmo local"""
        # Agrupar por local
        locais_com_personagens = {}
        for p in self.personagens:
            if p.pode_interagir:
                if p.local_atual not in locais_com_personagens:
                    locais_com_personagens[p.local_atual] = []
                locais_com_personagens[p.local_atual].append(p)
        
        # Verificar encontros sociais
        for local_id, personagens in locais_com_personagens.items():
            if len(personagens) >= 2:
                # Chance de encontro social
                if random.random() < 0.3:  # 30% por tick
                    p1, p2 = random.sample(personagens, 2)
                    self.motor_encontros.processar_encontro_social(p1, p2)
                    
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
        
        if resumo["encontros"]:
            print("\n📚 Encontros:")
            for e in resumo["encontros"]:
                emoji = "✅" if e.get("resultado") == "adequacao" else "❌" if e.get("resultado") == "dissolucao" else "➖"
                print(f"   {emoji} {e['personagem']}: {e.get('tipo', 'encontro')} ({e.get('delta', 0):+.2f})")
        
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
    # Criar e rodar simulação
    sim = criar_simulacao_padrao()
    
    # Rodar 20 ticks
    sim.rodar(ticks=20)
