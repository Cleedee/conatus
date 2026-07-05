"""
Módulo Mundo — Orquestrador da Simulação Conatus

Integra todos os componentes:
- Mapa e locais
- Personagens
- Encontros
- Eventos do mundo
- Ciclos de simulação
"""

from __future__ import annotations
import concurrent.futures
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable
import random
import json
import os
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
from interface import rodar_interativo, tick_silencioso, mostrar_estatisticas_finais


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
        config_llm: ConfigLLM = None,
        verbose: int = 0,
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
        
        # LLM assíncrono — fila de futuros: tick -> (personagem_id, Future)
        self._llm_fila: dict[int, tuple[str, "concurrent.futures.Future"]] = {}
        self._prox_personagem_idx = 0
        
        # Verbosity
        self.verbose = verbose

        # Estado
        self.estado = EstadoMundo()
        
        # Alternância de personagem LLM
        self._alternancia_intervalo: int = 0  # 0 = revezamento desligado
        self._alternancia_prox_tick: int = 0
        self._indice_llm_atual: int = 0

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
        
        # 3. CONSULTAR LLM (síncrono — bloqueia até resposta)
        decisoes_llm = {}
        decisao_llm = self._consultar_llm_sincrono()
        if decisao_llm:
            pid = decisao_llm.get("_personagem_id")
            if pid:
                decisoes_llm[pid] = decisao_llm
                razao = decisao_llm.get('razao','')
                escolha = decisao_llm.get('escolha','?')
                print(f"   ✅ {pid} → opção {escolha}: \"{razao[:100]}\"")
        
        # 4. PROCESSAR CADA PERSONAGEM
        for personagem in self.personagens:
            predef = decisoes_llm.get(personagem.id) if personagem.controlado_por_llm else None
            resultado_personagem = self._processar_personagem(
                personagem,
                encontro_escolhido=predef.get("encontro") if predef else None,
                decisao_info=predef or {},
            )
            resumo["encontros"].extend(resultado_personagem["encontros"])
            resumo["movimentos"].extend(resultado_personagem["movimentos"])
            resumo["crafting"].extend(resultado_personagem["crafting"])
        
        # 6. RESOLVER INTERAÇÕES PENDENTES
        self._resolver_interacoes()
        
        # 7. ATUALIZAR DESENVOLVIMENTO DOS LOCAIS
        for local in self.mapa.locais.values():
            nivel_antes = local.nivel_desenvolvimento
            local.recalcular_nivel(self.personagens)
            if local.nivel_desenvolvimento > nivel_antes:
                nomes = {0: "ermo", 1: "acampamento", 2: "povoado", 3: "vila"}
                self.estado.registrar_evento(
                    f"{local.nome} evoluiu para {nomes[local.nivel_desenvolvimento]}",
                    {"local": local.id, "nivel": local.nivel_desenvolvimento}
                )
        
        # 8. gerar resumo
        resumo["resumo_geral"] = self._gerar_resumo_tick()
        
        # 9. DISPLAY
        self.callback_display(resumo)
        
        return resumo
    
    def _tick_mundo(self):
        """Atualiza estado do mundo"""
        self.estado.avancar_tick()
        self.mapa.tick(self.estado.estacao_atual)
    
    def _obter_encontros(self, personagem: Personagem) -> list[EncontroDisponivel]:
        """Centraliza a coleta de encontros disponíveis para um personagem"""
        encontros = self.motor_encontros.obter_encontros_para_personagem(
            personagem,
            self.personagens,
            self.estado.hora,
            self.estado.eventos_ativos
        )
        
        local = self.mapa.get_local(personagem.local_atual)
        
        # Adicionar opções de locomoção
        if local:
            for destino_id, tempo in local.conexoes.items():
                destino_local = self.mapa.get_local(destino_id)
                if destino_local and not destino_local.lotado:
                    conhecido = personagem.local_conhecido(destino_id)
                    if conhecido:
                        recursos = personagem.get_recursos_conhecidos(destino_id)
                        desc = f"Ir para {destino_local.nome} ({tempo} ticks)"
                        if recursos:
                            desc += f" - recursos: {', '.join(recursos[:2])}"
                    else:
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
        
        # Receitas com skill suficiente
        receitas_possiveis = self.motor_crafting.banco.listar_receitas_possiveis(
            materiais_dict, habilidades_dict
        )
        
        ids_possiveis = set()
        # Primeiro: TODAS as receitas que o personagem TEM skill (até 5)
        for receita in receitas_possiveis[:5]:
            if receita.tipo == TipoReceita.CONSTRUCAO:
                motivo = (
                    personagem.necessidades.abrigo < 0.5
                    or personagem.moradia_local == personagem.local_atual
                    or (local and bool(local.construcoes))
                )
                if not motivo:
                    continue
            
            ids_possiveis.add(receita.id)
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
        
        # Segundo: Receitas EXPERIMENTAIS (materiais OK, skill INSUFICIENTE)
        # SÃO as que estão em listar_receitas_por_materiais MAS NÃO em listar_receitas_possiveis
        todas_por_materiais = self.motor_crafting.banco.listar_receitas_por_materiais(
            materiais_dict
        )
        ids_possiveis_set = {r.id for r in receitas_possiveis}
        experimentais_count = 0
        for receita in todas_por_materiais:
            if receita.id in ids_possiveis_set:
                continue  # já sabe fazer
            if experimentais_count >= 3:
                break  # máximo 3 experimentais para não poluir
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
                descricao=f"🔧 {receita.nome} ⚠️ (tentativa — skill insuficiente)",
                intensidade=0.15,  # menos atrativo
                disponibilidade=DisponibilidadeEncontro.SEMPRE,
                tag="crafting_experimental"
            ))
            experimentais_count += 1
        
        # Adicionar opções de DEPÓSITO
        depositaveis = ["comida", "madeira", "colheita", "pedra", "ferramentas"]
        for dep_rec_nome in depositaveis:
            if local:
                rec = local.get_recurso(dep_rec_nome)
                if not rec or not rec.disponivel:
                    continue
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
        
        # Adicionar opção de DORMIR se estiver cansado ou com medo
        if personagem.necessidades.energia < 0.5 or personagem.afetos.temor > 0.5:
            motivos = []
            if personagem.necessidades.energia < 0.2:
                motivos.append("energia quase zerada")
            elif personagem.necessidades.energia < 0.3:
                motivos.append("energia criticamente baixa")
            elif personagem.necessidades.energia < 0.5:
                motivos.append("cansaço moderado")
            if personagem.afetos.temor > 0.7:
                motivos.append("muito temor")
            elif personagem.afetos.temor > 0.5:
                motivos.append("certo temor")

            descricao = "Dormir para recuperar energias"
            if motivos:
                descricao += f" ({', '.join(motivos)})"

            encontros.append(EncontroDisponivel(
                id=f"dormir_{personagem.id}",
                origem=OrigemEncontro.AMBIENTAL,
                tipo=TipoEncontro.COGNITIVO,
                objeto="dormir",
                descricao=descricao,
                intensidade=0.4,
                disponibilidade=DisponibilidadeEncontro.SITUACIONAL,
                tag="sono"
            ))

        # ========= MODIFICAÇÕES NOTURNAS (luminosidade, frio) =========
        e_noite = not (6 <= self.estado.hora <= 20)
        if e_noite:
            # 1. Reduzir intensidade de encontros externos (luminosidade)
            # Aplica a TODAS as tags, exceto as que são especificamente noturnas (dormir, abrigar-se)
            for e in encontros:
                if e.tag not in ("sono", "abrigo"):
                    e.intensidade *= 0.5  # escuro atrapalha
                    e.descricao += " (prejudicado pela escuridão)"

            # 2. Adicionar/priorizar opção de DORMIR
            tem_sono = any(e.tag == "sono" for e in encontros)
            if not tem_sono:
                encontros.append(EncontroDisponivel(
                    id=f"dormir_{personagem.id}",
                    origem=OrigemEncontro.AMBIENTAL,
                    tipo=TipoEncontro.COGNITIVO,
                    objeto="dormir",
                    descricao="Dormir para passar a noite",
                    intensidade=0.6,
                    disponibilidade=DisponibilidadeEncontro.SITUACIONAL,
                    tag="sono"
                ))

            # 3. Adicionar opção de PROCURAR ABRIGO (se estiver em ermo sem proteção)
            if local:
                tem_abrigo = (local.id == personagem.moradia_local and personagem.tem_moradia) or \
                             local.construcoes.get("abrigo", 0) > 0 or \
                             local.construcoes.get("cabana", 0) > 0
                if not tem_abrigo:
                    # Local seguro mais próximo (vila)
                    if "vila" in local.conexoes and local.id != "vila":
                        encontros.append(EncontroDisponivel(
                            id=f"abrigar_vila_{personagem.id}",
                            origem=OrigemEncontro.AMBIENTAL,
                            tipo=TipoEncontro.FISICO,
                            objeto="mover_vila",
                            descricao="Procurar abrigo na Vila para passar a noite",
                            intensidade=0.7,
                            disponibilidade=DisponibilidadeEncontro.SITUACIONAL,
                            tag="abrigo"
                        ))
                    # Construir abrigo se tiver materiais (ou mostrar quanto falta)
                    qtd_madeira = personagem.inventario.get_quantidade("madeira")
                    if qtd_madeira >= 3:
                        encontros.append(EncontroDisponivel(
                            id=f"construir_abrigo_{personagem.id}",
                            origem=OrigemEncontro.RECURSO,
                            tipo=TipoEncontro.COGNITIVO,
                            objeto="craft_abrigo",
                            descricao="Construir um abrigo aqui com madeira",
                            intensidade=0.5,
                            disponibilidade=DisponibilidadeEncontro.SITUACIONAL,
                            tag="crafting"
                        ))
                    else:
                        faltam = 3 - qtd_madeira
                        encontros.append(EncontroDisponivel(
                            id=f"precisa_abrigo_{personagem.id}",
                            origem=OrigemEncontro.AMBIENTAL,
                            tipo=TipoEncontro.COGNITIVO,
                            objeto="precisa_abrigo",
                            descricao=f"Falta{'m' if faltam > 1 else ''} {faltam} madeira{'s' if faltam > 1 else ''} para construir um abrigo improvisado",
                            intensidade=0.05,
                            disponibilidade=DisponibilidadeEncontro.SITUACIONAL,
                            tag="planejamento"
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
        
        return encontros

    def _colher_decisoes_llm(self) -> dict[str, dict]:
        """Verifica futuros LLM pendentes e retorna decisões prontas"""
        resultado = {}
        ticks_prontos = []
        
        for tick_origem, (pid, futuro) in self._llm_fila.items():
            if futuro.done():
                try:
                    decisao = futuro.result()
                    resultado[pid] = decisao
                    razao = decisao.get('razao','')
                    self.estado.registrar_evento(
                        f"LLM→{pid} (tick {tick_origem}): {razao[:60]}",
                        {"decisao": decisao}
                    )
                    escolha = decisao.get('escolha','?')
                    emocao = decisao.get('emocao','')
                    print(f"   ✅ {pid} → opção {escolha}: \"{razao[:100]}\"")
                    if self.verbose >= 1 and emocao:
                        print(f"   😶 Emoção: {emocao}")
                except Exception as e:
                    self.estado.registrar_evento(
                        f"LLM falhou para {pid}: {e}", {}
                    )
                    print(f"   ⚠ LLM falhou para {pid}: {e}")
                ticks_prontos.append(tick_origem)
        
        # Limpar futuros concluídos
        for t in ticks_prontos:
            del self._llm_fila[t]
        
        return resultado

    def _disparar_proximo_llm(self):
        """Dispara LLM para o próximo personagem (round-robin, assíncrono)"""
        if not self.agente_llm or not self.agente_llm.verificar_pronto():
            return
        
        # Escolher próximo personagem (round-robin, apenas controlados por LLM)
        n = len(self.personagens)
        for _ in range(n):
            p = self.personagens[self._prox_personagem_idx]
            self._prox_personagem_idx = (self._prox_personagem_idx + 1) % n
            
            # Pular personagens sem LLM, inativos ou com futuro pendente
            if not p.controlado_por_llm:
                continue
            if not p.pode_interagir or p.dormindo or p.estado == EstadoPersonagem.LOCOMOVENDO:
                continue
            
            # Já tem um futuro pendente para este personagem?
            if any(pid == p.id for _, (pid, _) in self._llm_fila.items()):
                continue
            
            # Coletar encontros e disparar
            try:
                encontros = self._obter_encontros(p)
                if not encontros:
                    continue
                contexto = {
                    "local": p.local_atual,
                    "hora": self.estado.hora,
                    "outros": self._listar_outros_no_local(p)
                }
                
                # Future manual + daemon thread (não bloqueia exit)
                futuro = concurrent.futures.Future()
                def rodar(fut, llm, pers, encs, ctx):
                    try:
                        res = llm.decidir_acao(pers, encs, ctx)
                        fut.set_result(res)
                    except BaseException as e:
                        fut.set_exception(e)
                
                if self.verbose >= 1:
                    print(f"   📋 Alternativas para {p.nome}:")
                    for i, e in enumerate(encontros, start=1):
                        print(f"      {i}. {e.descricao} ({e.tipo.value}, {e.tag})")
                t = threading.Thread(
                    target=rodar,
                    args=(futuro, self.agente_llm, p, encontros, contexto),
                    daemon=True,
                )
                t.start()
                self._llm_fila[self.estado.tick_atual] = (p.id, futuro)
                print(f"   🧠 LLM consultado para {p.nome} (tick {self.estado.tick_atual})")
            except Exception as e:
                print(f"   ⚠ LLM falhou para {p.nome}: {e}")
            break  # Só dispara um por tick

    def _alternar_personagem_llm(self):
        """Alterna o personagem controlado por LLM para o próximo"""
        if not self.personagens or self._alternancia_intervalo <= 0:
            return
        # Desmarcar todos
        for p in self.personagens:
            p.controlado_por_llm = False
        # Encontrar índice do próximo
        self._indice_llm_atual = (self._indice_llm_atual + 1) % len(self.personagens)
        prox = self.personagens[self._indice_llm_atual]
        prox.controlado_por_llm = True
        self._alternancia_prox_tick = self.estado.tick_atual + self._alternancia_intervalo
        print(f"   🔄 LLM agora controla {prox.nome} (próxima troca em {self._alternancia_intervalo} ticks)")

    def _consultar_llm_sincrono(self) -> Optional[dict]:
        """
        Consulta LLM de forma síncrona (bloqueante) para o personagem
        controlado por LLM. Retorna a decisão ou None.
        """
        if not self.agente_llm or not self.agente_llm.verificar_pronto():
            return None

        # Alternar personagem quando atingir o tick marcado
        if self._alternancia_intervalo > 0 and self.estado.tick_atual >= self._alternancia_prox_tick:
            self._alternar_personagem_llm()

        # Encontrar personagem LLM que pode agir
        personagem = None
        for p in self.personagens:
            if p.controlado_por_llm and p.pode_interagir and not p.dormindo \
                    and p.estado != EstadoPersonagem.LOCOMOVENDO:
                personagem = p
                break
        if not personagem:
            return None

        encontros = self._obter_encontros(personagem)
        if not encontros:
            return None

        contexto = {
            "local": personagem.local_atual,
            "hora": self.estado.hora,
            "outros": self._listar_outros_no_local(personagem),
        }

        print(f"   🧠 LLM consultado para {personagem.nome} (tick {self.estado.tick_atual})")
        if self.verbose >= 1:
            print("   📋 Alternativas apresentadas:")
            for i, e in enumerate(encontros, start=1):
                print(f"      {i}. {e.descricao} ({e.tipo.value}, {e.tag})")
        decisao = self.agente_llm.decidir_acao(personagem, encontros, contexto)
        if self.verbose >= 1:
            escolha = decisao.get('escolha', '?')
            razao = decisao.get('razao', '')
            emocao = decisao.get('emocao', '')
            print(f"   💭 LLM raciocinou: {razao[:150]}")
            if emocao:
                print(f"   😶 Emoção: {emocao}")
            if isinstance(escolha, int) and 1 <= escolha <= len(encontros):
                escolhido = encontros[escolha - 1]
                print(f"   👉 Escolheu opção {escolha}: {escolhido.descricao[:100]}")
        decisao["_personagem_id"] = personagem.id
        return decisao

    def _processar_personagem(
        self,
        personagem: Personagem,
        encontro_escolhido: Optional[EncontroDisponivel] = None,
        decisao_info: Optional[dict] = None,
    ) -> dict:
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

        # Aplicar efeitos noturnos (frio, mosquitos, escuridão)
        personagem.aplicar_efeitos_noturnos(local, self.estado.hora)
        
        # Atualizar necessidades
        personagem.tick_necessidades()
        personagem.tick_afetos()

        # Encontros noturnos automáticos (frio, mosquitos)
        if not self.estado.e_dia:
            self._processar_encontros_noturnos(personagem, local, resultado)
        
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
        
        # Verificar se deve dormir (apenas p/ personagens nÃ£o-LLM; LLM decide dormir como opÃ§Ã£o de encontro)
        # Forçar dormir se energia está criticamente baixa (qualquer personagem)
        if personagem.necessidades.energia < 0.15 or personagem.decidir_dormir():
            personagem.dormindo = True
            personagem.estado = EstadoPersonagem.DORMINDO
            self.estado.registrar_evento(
                f"{personagem.nome} foi dormir" +
                (" (exaustão)" if personagem.necessidades.energia < 0.15 else ""),
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
        
        # Obter encontros disponíveis (se não veio pré-selecionado)
        if encontro_escolhido is None:
            encontros = self._obter_encontros(personagem)
            
            # Fallback: decisão simples
            encontro_escolhido = self._decidir_acao_simples(personagem, encontros)
            
            # Último fallback: escolher aleatório
            if encontro_escolhido is None and encontros:
                encontro_escolhido = random.choice(encontros)
        
        # Registrar pensamento do LLM
        if decisao_info:
            resultado["decisoes"].append({
                "personagem": personagem.nome,
                "razao": decisao_info.get("razao", ""),
                "emocao": decisao_info.get("emocao", "neutro")
            })
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

            # Verificar se Ã© DORMIR
            elif encontro_escolhido.tag == "sono":
                personagem.dormindo = True
                personagem.estado = EstadoPersonagem.DORMINDO
                self.estado.registrar_evento(
                    f"{personagem.nome} foi dormir",
                    {"personagem": personagem.id}
                )
            
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
        # FASE 1: Necessidades — moduladas pela RAZÃO (Espinosa)
        # Personagens racionais compreendem que a verdadeira solução
        # para a escassez está na engenharia, não na coleta imediata.
        # Suportam mais privação em prol do investimento de longo prazo.
        razao = personagem.razao_vs_paixao
        
        # O limiar de necessidade crítica diminui com a razão:
        #   razão 0.0 → limiar 0.40 (reage à menor fome)
        #   razão 0.5 → limiar 0.35
        #   razão 1.0 → limiar 0.25 (só age quando fome é severa)
        limiar_fome = max(0.20, 0.40 - razao * 0.15)
        limiar_sede = max(0.20, 0.40 - razao * 0.15)
        
        # Antes de agir por necessidade, a razão avalia se há
        # oportunidade de investimento que resolva a causa raiz
        craftings = [e for e in encontros if e.tag == "crafting"]
        experimental_crafts = [e for e in encontros if e.tag == "crafting_experimental"]
        
        # FASE 0: RAZÃO — visão de longo prazo
        # O sábio espinozista intui que excedentes vêm da engenharia.
        # Prioriza criar ferramentas que multiplicarão sua potência.
        if razao > 0.5:
            chance_engenharia = (razao - 0.5) * 0.5  # 0% a 25%
            
            # Se há algo NOVO para aprender (experimental), chance extra
            if experimental_crafts and random.random() < chance_engenharia + 0.10:
                return random.choice(experimental_crafts)
            
            # Se há crafts úteis (ferramentas, construção, processamento)
            crafts_uteis = [e for e in craftings if any(
                t in e.descricao.lower()
                for t in ["machado", "picareta", "abrigo", "cabana", "cordas",
                          "pranchas", "metal", "fogueira", "armazem"]
            )]
            if crafts_uteis and random.random() < chance_engenharia:
                return random.choice(crafts_uteis)
        
        # Curiosidade (não-racional): desejo espinozista de aumentar
        # potência por conhecimento — 15% mesmo com necessidades baixas
        if experimental_crafts and random.random() < 0.15:
            return random.choice(experimental_crafts)
        
        # FASE 1: Necessidades críticas (com limiar ajustado pela razão)
        if personagem.necessidades.fome < limiar_fome:
            for e in encontros:
                if "comida" in e.objeto or "comer" in e.descricao.lower():
                    return e
        
        if personagem.necessidades.sede < limiar_sede:
            for e in encontros:
                if "água" in e.objeto or "poço" in e.objeto or "beber" in e.descricao.lower():
                    return e
        
        # FASE 2: Coleta e crafting quando há materiais
        coletas = [e for e in encontros
                   if e.tag in ("recurso", "alimento", "sobrevivencia", "producao")
                   and e.origem != OrigemEncontro.SOCIAL
                   and "mover_" not in e.objeto]
        
        if craftings or experimental_crafts:
            # Preferir tentativas experimentais (aprender coisas novas)
            if experimental_crafts and random.random() < 0.60:
                return random.choice(experimental_crafts)
            if craftings and random.random() < 0.50:
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

    def _processar_encontros_noturnos(
        self,
        personagem: Personagem,
        local: Optional[Local],
        resultado: dict
    ):
        """
        Processa encontros negativos automáticos durante a noite (frio, mosquitos).
        Só afeta personagens em ermos sem proteção.
        """
        if 6 <= self.estado.hora <= 20:
            return

        # Verificar se está protegido (na própria moradia ou local com abrigo)
        protegido = False
        if local:
            if local.id == personagem.moradia_local and personagem.tem_moradia:
                protegido = True
            elif local.construcoes.get("abrigo", 0) > 0 or local.construcoes.get("cabana", 0) > 0:
                protegido = True

        if protegido:
            return

        # Registrar encontro no resultado (as penalidades de necessidades
        # já foram aplicadas por aplicar_efeitos_noturnos em personagem.py)
        detalhes_noturnos = []
        if local:
            detalhes_noturnos.append("frio cortante")
        if local and local.id in {"floresta", "rio", "pantano", "lago", "praia", "planicie"}:
            detalhes_noturnos.append("mosquitos")
        if local and local.nivel_desenvolvimento == 0:
            detalhes_noturnos.append("escuridão total")

        if detalhes_noturnos:
            desc = f"Noite em {local.nome if local else 'ermos'}: {', '.join(detalhes_noturnos)}"
            resultado["encontros"].append({
                "personagem": personagem.nome,
                "tipo": "ambiental",
                "resultado": "dissolucao",
                "delta": -0.05,
                "descricao": desc,
                "detalhes": desc
            })
    
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
        # Recuperar necessidades (aumentado para 0.10)
        personagem.necessidades.energia += 0.10
        personagem.necessidades.saude += 0.02  # sono recupera saúde
        
        # Abrigo recupera melhor na própria moradia
        if personagem.tem_moradia and personagem.local_atual == personagem.moradia_local:
            personagem.necessidades.abrigo += 0.02
            personagem.necessidades.saude += 0.02  # dormir em casa recupera mais
        else:
            personagem.necessidades.abrigo += 0.005  # dormir ao relento
        
        personagem.necessidades.normalizar()
        
        # Acordar quando energia alta (mais cedo: 0.7)
        if personagem.necessidades.energia > 0.7:
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
        
        skill_insuficiente = False
        if not pode:
            # Se falhou só por skill, permitir tentativa experimental
            if "Habilidade" in motivo or "habilidade" in motivo.lower():
                skill_insuficiente = True
            else:
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
        
        # Se skill é insuficiente, usar nível efetivo penalizado
        if skill_insuficiente:
            nivel_efetivo = max(0.05, nivel_habilidade * 0.5)
        else:
            nivel_efetivo = nivel_habilidade
        
        resultado = self.motor_crafting.tentar_crafting(
            receita, materiais_dict, nivel_efetivo
        )
        
        # Bônus de XP para tentativas experimentais (aprender fazendo)
        if skill_insuficiente:
            resultado.xp_ganho = int(resultado.xp_ganho * 1.5)
        
        # Aplicar resultado
        if resultado.itens_criados:
            for nome, qtd in resultado.itens_criados:
                personagem.inventario.adicionar_item(nome, qtd)
        
        # Ganhar XP
        if resultado.xp_ganho > 0:
            subiu = personagem.ganhar_xp(receita.habilidade_requerida, resultado.xp_ganho)
        
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
                # Observador ganha XP da observação (aprende vendo)
                xp_obs = max(1, resultado.xp_ganho // 4)
                outro.ganhar_xp(receita.habilidade_requerida, xp_obs)
        
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

                    # PEDIDO SOCIAL: personagens racionais pedem ajuda
                    # Espinosa: agir por razão é cooperar para aumentar
                    # a potência coletiva. Um sábio pede ajuda a outro.
                    self._tentar_pedido(p1, p2)
                    self._tentar_pedido(p2, p1)

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
                    f"{[f'{item.quantidade} {item.nome}' for item in proposta.ofertando]} por " +
                    f"{[f'{item.quantidade} {item.nome}' for item in proposta.pedindo]}",
                    {
                        "tipo": "troca",
                        "proponente": proponente.id,
                        "receptor": receptor.id
                    }
                )
    
    def _tentar_pedido(self, p1: Personagem, p2: Personagem):
        """
        Pedido social: personagem racional pede a outro que realize
        uma tarefa que ele mesmo não pode fazer.
        
        Espinosa: agir por razão é cooperar — reconhecer que a
        potência coletiva supera a individual. Um sábio pede ajuda
        a outro cuja habilidade complementa a sua.
        """
        # Identificar quem é o mais racional (quem pode fazer o pedido)
        if p1.razao_vs_paixao < 0.5 and p2.razao_vs_paixao < 0.5:
            return  # nenhum é racional o suficiente
        
        if p1.razao_vs_paixao >= p2.razao_vs_paixao:
            requisitante, ajudante = p1, p2
        else:
            requisitante, ajudante = p2, p1
        
        # Um racional reconhece sua ignorância — pede ajuda quando
        # o outro TEM uma skill que ele não tem (ou tem mais fraca)
        # Isso é independente de necessidades imediatas.
        from habilidades import MotorEnsino
        motor_ensino = MotorEnsino()
        
        # Verificar se o ajudante pode ensinar algo útil
        pode_ensinar = ajudante.habilidades_pode_ensinar()
        pode_aprender = requisitante.habilidades_pode_aprender(ajudante)
        
        tem_skill_util = bool(pode_ensinar and pode_aprender)
        
        if not tem_skill_util:
            # Talvez o ajudante possa CRAFTAR algo que o requisitante não pode
            materiais_req = requisitante.inventario.get_materiais_dict()
            if not materiais_req:
                return
            habilidades_ajud = {nome: hab.nivel for nome, hab in ajudante.habilidades.items()}
            # Não precisa de skill se for receita com nivel_minimo=0.0
            # Mas o requisitante quer algo que ELE não pode fazer
            for r in self.motor_crafting.banco.receitas.values():
                if not r.habilidade_requerida:
                    continue
                # Requisitante não tem a skill ou tem nível baixo
                nivel_req = requisitante.get_nivel_habilidade(r.habilidade_requerida)
                if nivel_req >= r.nivel_minimo:
                    continue  # requisitante já pode fazer
                # Ajudante tem a skill?
                nivel_ajud = ajudante.get_nivel_habilidade(r.habilidade_requerida)
                if nivel_ajud >= r.nivel_minimo:
                    # Verificar materiais
                    if all(materiais_req.get(mat, 0) >= qtd for mat, qtd in r.materiais.items()):
                        tem_skill_util = True
                        break
        
        if not tem_skill_util:
            return  # não há o que pedir
        
        # O ajudante aceita? Baseado na relação
        relacao = requisitante.get_ou_criar_relacao(ajudante.id, "personagem", ajudante.nome)
        chance_aceitar = 0.5 + relacao.get_modificador() * 0.2
        if ajudante.necessidades.media() < 0.3:
            chance_aceitar *= 0.5  # ajudante em necessidade própria
        
        if random.random() > chance_aceitar:
            return  # recusou
        
        # ========== PRIORIDADE 1: ENSINAR ==========
        if pode_ensinar and pode_aprender:
            # Escolher skill com maior gap (mais a aprender)
            skill_escolhida = None
            maior_gap = 0.0
            for s in pode_ensinar:
                if s in pode_aprender:
                    nivel_req = requisitante.get_nivel_habilidade(s)
                    gap = ajudante.habilidades[s].nivel - nivel_req
                    if gap > maior_gap:
                        maior_gap = gap
                        skill_escolhida = s
            
            if skill_escolhida is not None:
                nivel_prof = ajudante.habilidades[skill_escolhida].nivel
                nivel_aluno_val = requisitante.get_nivel_habilidade(skill_escolhida)
                
                xp = motor_ensino.calcular_ganho_ensino(nivel_aluno_val, nivel_prof)
                if xp > 0:
                    subiu = requisitante.ganhar_xp(skill_escolhida, xp)
                    ajudante.ganhar_xp(skill_escolhida, max(1, xp // 4))
                    
                    msg = f"🙏 {requisitante.nome} pediu que {ajudante.nome} ensinasse {skill_escolhida}"
                    if subiu:
                        msg += " (subiu de nível!)"
                    
                    self.estado.registrar_evento(msg, {
                        "tipo": "pedido",
                        "requisitante": requisitante.id,
                        "ajudante": ajudante.id,
                        "skill": skill_escolhida,
                        "xp": xp
                    })
                    return
        
        # ========== PRIORIDADE 2: CRAFTAR ==========
        materiais_req = requisitante.inventario.get_materiais_dict()
        if not materiais_req:
            return
        
        habilidades_ajud = {nome: hab.nivel for nome, hab in ajudante.habilidades.items()}
        
        # Encontrar receita que o ajudante pode fazer e o requisitante não
        receita_escolhida = None
        for r in self.motor_crafting.banco.receitas.values():
            if not r.habilidade_requerida:
                continue
            nivel_req = requisitante.get_nivel_habilidade(r.habilidade_requerida)
            if nivel_req >= r.nivel_minimo:
                continue
            nivel_ajud = ajudante.get_nivel_habilidade(r.habilidade_requerida)
            if nivel_ajud < r.nivel_minimo:
                continue
            if not all(materiais_req.get(mat, 0) >= qtd for mat, qtd in r.materiais.items()):
                continue
            receita_escolhida = r
            break
        
        if not receita_escolhida:
            return
        
        # Ajudante crafta usando os materiais do requisitante
        for mat, qtd in receita_escolhida.materiais.items():
            requisitante.inventario.remover_material(mat, qtd)
        
        nivel_skill = ajudante.get_nivel_habilidade(receita_escolhida.habilidade_requerida)
        resultado = self.motor_crafting.tentar_crafting(
            receita_escolhida, materiais_req, nivel_skill
        )
        
        if resultado.itens_criados:
            for nome, qtd in resultado.itens_criados:
                requisitante.inventario.adicionar_item(nome, qtd)
            
            ajudante.ganhar_xp(receita_escolhida.habilidade_requerida, resultado.xp_ganho)
            requisitante.ganhar_xp(receita_escolhida.habilidade_requerida, max(1, resultado.xp_ganho // 3))
            
            self.estado.registrar_evento(
                f"🙏 {requisitante.nome} pediu que {ajudante.nome} fizesse {receita_escolhida.nome} — "
                f"{resultado.mensagem}",
                {
                    "tipo": "pedido_craft",
                    "requisitante": requisitante.id,
                    "ajudante": ajudante.id,
                    "receita": receita_escolhida.nome,
                    "sucesso": resultado.resultado.value
                }
            )
    
    def _gerar_resumo_tick(self) -> str:
        """Gera resumo textual do tick"""
        linhas = []
        
        emoji_estacao = {"primavera": "🌸", "verao": "☀️", "outono": "🍂", "inverno": "❄️"}
        ico = emoji_estacao.get(self.estado.estacao_atual.value, "")
        linhas.append(f"⏰ Tick {self.estado.tick_atual} | Dia {self.estado.dia} | {self.estado.nome_periodo} ({self.estado.hora}:00) {ico} {self.estado.estacao_atual.value}")
        
        # Personagens
        if self.personagens:
            linhas.append(f"👥 {len(self.personagens)} personagens:")
            for p in self.personagens:
                estado = "💤" if p.dormindo else "🚶" if p.estado == EstadoPersonagem.LOCOMOVENDO else "🧑"
                llm_ico = "🤖 " if p.controlado_por_llm else ""
                skills = [nome for nome, hab in p.habilidades.items() if hab.nivel >= 0.4]
                sufixo_skills = f" [{', '.join(skills)}]" if skills else ""
                linhas.append(f"   {estado} {llm_ico}{p.nome} em {p.local_atual} (potência: {p.potencia_atual:.0%}){sufixo_skills}")
        
        # Eventos
        if self.estado.eventos_ativos:
            linhas.append(f"🎯 Eventos ativos:")
            for e in self.estado.eventos_ativos:
                linhas.append(f"   - {e.nome}: {e.descricao} ({e.duracao - e.tick_atual} ticks restantes)")
        
        # Relações entre personagens no mesmo local
        relacoes_exibidas = []
        for p in self.personagens:
            if not p.relacoes:
                continue
            for rid, r in p.relacoes.items():
                if r.tipo == "personagem" and abs(r.afeto) > 0.3:
                    # Verificar se a outra pessoa está no mesmo local
                    outro_id = rid.split(":", 1)[-1]
                    outro = self.get_personagem(outro_id)
                    if outro and outro.local_atual == p.local_atual:
                        if abs(r.afeto) > 0.5:
                            emo = "❤️" if r.afeto > 0 else "💔"
                            relacoes_exibidas.append(f"   {emo} {p.nome} {r.sentimento} {r.entidade_nome} (afeto: {r.afeto:+.2f})")
        if relacoes_exibidas:
            linhas.append("🤝 Relações:")
            linhas.extend(relacoes_exibidas[:5])
        
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

        # Relações entre personagens no mesmo local
        relacoes_exibidas = []
        for p in self.personagens:
            if not p.relacoes:
                continue
            for rid, r in p.relacoes.items():
                if r.tipo == "personagem" and abs(r.afeto) > 0.3:
                    outro_id = rid.split(":", 1)[-1]
                    outro = self.get_personagem(outro_id)
                    if outro and outro.local_atual == p.local_atual:
                        emo = "❤️" if r.afeto > 0 else "💔"
                        relacoes_exibidas.append(f"   {emo} {p.nome} {r.sentimento} {r.entidade_nome} (afeto: {r.afeto:+.2f})")
        if relacoes_exibidas:
            print("\n🤝 Relações:")
            for linha in relacoes_exibidas[:5]:
                print(linha)

        print("=" * 60)
    
    # =========================================================================
    # CONTROLES
    # =========================================================================
    
    def rodar(self, ticks: int = None, pausa_a_cada: int = 10):
        """
        Roda a simulação
        
        Args:
            ticks: Número de ticks para rodar (None = infinito)
            pausa_a_cada: Pausar a cada N ticks (None = sem pausas)
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
                
                # Pausa periódica
                if pausa_a_cada and tick_count % pausa_a_cada == 0:
                    input("\n[Enter para continuar...]")
        
        except KeyboardInterrupt:
            print("\n\n⏹️  Simulação interrompida")
        
        self._mostrar_estatisticas_finais()
    
    def rodar_interativo(self, ticks_iniciais: int = 0):
        """Delega para interface.rodar_interativo"""
        rodar_interativo(self, ticks_iniciais)

    def _tick_silencioso(self) -> bool:
        """Delega para interface.tick_silencioso"""
        return tick_silencioso(self)

    def _mostrar_estatisticas_finais(self):
        """Delega para interface.mostrar_estatisticas_finais"""
        mostrar_estatisticas_finais(self)

def carregar_elenco(caminho_elenco: str) -> list[Personagem]:
    """
    Carrega personagens de um arquivo JSON de elenco.
    
    O arquivo de elenco contém referências a arquivos JSON individuais
    de personagens. Exemplo:
    
    {
        "nome": "Meu Elenco",
        "personagens": [
            "personagens/maria.json",
            "personagens/joao.json"
        ]
    }
    
    Cada arquivo de personagem segue o schema de Personalidade + metadados.
    """
    # Resolver caminho base (diretório do arquivo de elenco)
    caminho_elenco = os.path.abspath(caminho_elenco)
    if not os.path.exists(caminho_elenco):
        raise FileNotFoundError(f"Arquivo de elenco não encontrado: {caminho_elenco}")
    
    with open(caminho_elenco, "r", encoding="utf-8") as f:
        dados_elenco = json.load(f)
    
    refs = dados_elenco.get("personagens", [])
    if not refs:
        raise ValueError(f"Elenco '{caminho_elenco}' não contém personagens")
    
    base_dir = os.path.dirname(caminho_elenco)
    
    personagens = []
    for ref in refs:
        # Resolver caminho relativo ao diretório do elenco ou absoluto
        caminho_personagem = ref
        if not os.path.isabs(caminho_personagem):
            # Tentar relativo ao diretório do elenco
            caminho_personagem = os.path.join(base_dir, caminho_personagem)
            if not os.path.exists(caminho_personagem):
                # Tentar relativo ao workspace (raiz do projeto)
                caminho_personagem = os.path.join(os.getcwd(), ref)
        
        if not os.path.exists(caminho_personagem):
            print(f"⚠ Personagem não encontrado: {ref} — ignorando")
            continue
        
        with open(caminho_personagem, "r", encoding="utf-8") as f:
            dados = json.load(f)
        
        # Construir Personalidade
        personalidade = Personalidade(
            nome=dados["nome"],
            arquetipo=dados["arquetipo"],
            idade=dados.get("idade", 30),
            descricao=dados.get("descricao", ""),
            razao_innata=dados.get("razao_innata", 0.5),
            motivacoes=dados.get("motivacoes", {
                "sobrevivencia": 0.8,
                "conforto": 0.5,
                "curiosidade": 0.4
            }),
            valores=dados.get("valores", ["honestidade"]),
            medos=dados.get("medos", ["solidão"])
        )
        
        local = dados.get("local_inicial", "vila")
        potencia = dados.get("potencia_inicial", 0.7)
        
        p = Personagem(personalidade, local_inicial=local, potencia_inicial=potencia)
        p.controlado_por_llm = dados.get("controlado_por_llm", False)
        
        personagens.append(p)
    
    return personagens


def criar_simulacao_padrao(
    usar_llm: bool = True,
    config_llm: ConfigLLM = None,
    verbose: int = 0,
    elenco_path: Optional[str] = None
) -> Simulacao:
    """
    Cria simulação.
    
    Args:
        elenco_path: Caminho para arquivo JSON de elenco.
                     Se None, usa o elenco padrão (hardcoded).
    """
    mapa = criar_mapa_padrao()
    
    # Carregar personagens
    personagens = []
    if elenco_path:
        personagens = carregar_elenco(elenco_path)
    else:
        personagens = _criar_personagens_padrao()
    
    return Simulacao(mapa=mapa, personagens=personagens, usar_llm=usar_llm, config_llm=config_llm, verbose=verbose)


def _criar_personagens_padrao() -> list[Personagem]:
    """Cria personagens padrão embutidos no código"""
    personagens = []
    
    # Maria - Generosa
    
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
    p_maria = Personagem(maria, local_inicial="vila")
    p_maria.controlado_por_llm = True
    personagens.append(p_maria)
    
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
    
    return personagens


# =============================================================================
# EXEMPLO DE USO
# =============================================================================

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Mundo Aberto — Simulação Espinozista")
    parser.add_argument("-i", "--interativo", nargs="?", const=0, type=int,
                        help="Modo interativo (arg opcional: ticks iniciais)")
    parser.add_argument("--llm", action="store_true", default=False,
                        help="Usar LLM (Ollama) para controlar personagem marcado")
    parser.add_argument("--provider", choices=["ollama", "llamacpp"], default=None,
                        help="Provedor LLM (padrão: ollama)")
    parser.add_argument("--model", type=str, default=None,
                        help="Modelo (ex: qwen2.5:0.5b, padrão: qwen2.5:1.5b)")
    parser.add_argument("--url", type=str, default=None,
                        help="URL do servidor LLM (padrão: http://localhost:11434)")
    parser.add_argument("--alternar", type=int, default=0,
                        help="Alternar LLM entre personagens a cada N ticks (padrão: 0 = desligado)")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Aumenta verbosidade (-v mostra alternativas do LLM)")
    parser.add_argument("--elenco", type=str, default=None,
                        help="Caminho para arquivo JSON de elenco (ex: elenco/experimental.json)")
    parser.add_argument("--listar-personagens", action="store_true",
                        help="Lista personagens disponíveis no elenco e sai")
    
    args = parser.parse_args()
    
    # Listar personagens de um elenco e sair
    if args.listar_personagens:
        caminho = args.elenco or "elenco/default.json"
        if not os.path.exists(caminho):
            print(f"Arquivo não encontrado: {caminho}")
            sys.exit(1)
        personagens = carregar_elenco(caminho)
        print(f"\n📋 Elenco: {caminho}")
        for p in personagens:
            extra = " 🤖" if p.controlado_por_llm else ""
            print(f"  - {p.nome:12s} ({p.personalidade.arquetipo:12s}) razão={p.razao_vs_paixao:.2f}{extra}  — {p.local_atual}")
        print(f"\nTotal: {len(personagens)} personagens")
        sys.exit(0)
    
    # Configurar LLM se solicitado
    config_llm = None
    usar_llm = False
    if args.llm:
        from llm import ProviderLLM
        usar_llm = True
        provider = ProviderLLM.OLLAMA if args.provider in (None, "ollama") else ProviderLLM.LLAMACPP
        config_llm = ConfigLLM(
            provider=provider,
            modelo=args.model or "qwen2.5:1.5b",
            ollama_url=args.url or "http://localhost:11434",
            llamacpp_url=args.url or "http://localhost:8080",
        )
    
    sim = criar_simulacao_padrao(
        usar_llm=usar_llm,
        config_llm=config_llm,
        verbose=args.verbose,
        elenco_path=args.elenco
    )
    
    # Configurar alternância de personagem LLM
    if args.llm and args.alternar > 0:
        sim._alternancia_intervalo = args.alternar
        # Primeira alternância após N ticks (tick 0 não conta — primeiro tick é 1)
        sim._alternancia_prox_tick = args.alternar + 1
    
    if args.interativo is not None:
        sim.rodar_interativo(ticks_iniciais=args.interativo)
    elif args.llm:
        sim.rodar()
    else:
        sim.rodar(ticks=50, pausa_a_cada=None)
