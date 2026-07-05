"""
Módulo de Interface — Modo Interativo da Simulação Conatus

Fornece o REPL (cmd.Cmd) para exploração ao vivo da simulação.
"""

from __future__ import annotations
import cmd
from typing import Optional
from collections import defaultdict

from personagem import Personagem, EstadoPersonagem


def rodar_interativo(sim, ticks_iniciais: int = 0):
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
    # Rodar ticks iniciais
    for _ in range(ticks_iniciais):
        if not tick_silencioso(sim):
            break

    intro = (
        "\n🎮 MODO INTERATIVO"
        "\n   Digite 'ajuda' para comandos ou 'continuar' para avançar."
        "\n   Dica: use Tab para autocompletar nomes.\n"
    )

    repl = REPLSimulacao(sim)
    try:
        repl.cmdloop(intro)
    except KeyboardInterrupt:
        print()
    mostrar_estatisticas_finais(sim)


def tick_silencioso(sim) -> bool:
    """Roda um tick sem display. Retorna False se interrompido."""
    old = sim.callback_display
    sim.callback_display = lambda x: None
    try:
        sim.tick()
        return True
    finally:
        sim.callback_display = old


def mostrar_estatisticas_finais(sim):
    """Mostra estatísticas ao final"""
    print("\n" + "=" * 60)
    print("📊 ESTATÍSTICAS FINAIS")
    print("=" * 60)

    print(f"\n⏰ Tempo total:")
    print(f"   Ticks: {sim.estado.tick_atual}")
    print(f"   Dias: {sim.estado.dia}")
    print(f"   Semanas: {sim.estado.semana}")

    if sim.personagens:
        print(f"\n👥 Personagens:")
        for p in sim.personagens:
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
# REPL — SHELL INTERATIVO
# =============================================================================

class REPLSimulacao(cmd.Cmd):
    """Shell interativo para explorar a simulação ao vivo"""

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
        return (f"Energia={n.energia:.0%} Saciedade={n.fome:.0%} "
                f"Hidratação={n.sede:.0%} Abrigo={n.abrigo:.0%} Saúde={n.saude:.0%}")

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
                llm_ico = "🤖" if p.controlado_por_llm else ""
                skills = [nome for nome, hab in p.habilidades.items() if hab.nivel >= 0.4]
                sufixo = f" [{', '.join(skills)}]" if skills else ""
                print(f"      {estado} {llm_ico} {p.nome} ({p.personalidade.arquetipo}) — potência: {p.potencia_atual:.0%}{sufixo}")

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
                llm_ico = "🤖" if p.controlado_por_llm else ""
                skills = [nome for nome, hab in p.habilidades.items() if hab.nivel >= 0.4]
                sufixo = f" [{', '.join(skills)}]" if skills else ""
                print(f"      {estado} {llm_ico} {p.nome} ({p.personalidade.arquetipo}) — {self._formatar_necessidades(p)}{sufixo}")
        else:
            print(f"\n   👥 Personagens ({len(self.sim.personagens)}):")
            # Agrupar por local
            por_local = defaultdict(list)
            for p in self.sim.personagens:
                por_local[p.local_atual].append(p)

            for local_id, ps in sorted(por_local.items()):
                local = self.sim.mapa.get_local(local_id)
                nome_local = local.nome if local else local_id
                print(f"\n      📍 {nome_local}:")
                for p in ps:
                    estado = "💤" if p.dormindo else "🚶" if p.estado == EstadoPersonagem.LOCOMOVENDO else "🧑"
                    llm_ico = "🤖" if p.controlado_por_llm else ""
                    skills = [nome for nome, hab in p.habilidades.items() if hab.nivel >= 0.4]
                    sufixo = f" [{', '.join(skills)}]" if skills else ""
                    print(f"         {estado} {llm_ico} {p.nome} ({p.personalidade.arquetipo}) — potência: {p.potencia_atual:.0%}{sufixo}")

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
   │    Saciedade: {p.necessidades.fome:.0%} {self._barra_vida(p.necessidades.fome)}
   │    Hidratação: {p.necessidades.sede:.0%} {self._barra_vida(p.necessidades.sede)}
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
        print('''
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
                ''')

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
