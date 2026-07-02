"""
Módulo de Mercado e Trocas

Permite que personagens troquem itens entre si.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import random


class TipoTransacao(Enum):
    """Tipos de transação"""
    TROCA = "troca"              # Item por item
    DOACAO = "doacao"            # Dar sem receber
    VENDA = "venda"              # Vender por "reputação" ou favor
    EMPRESTIMO = "emprestimo"    # Pegar emprestado temporariamente


@dataclass
class ItemTransacao:
    """Item sendo transacionado"""
    nome: str
    quantidade: int
    qualidade: float = 1.0


@dataclass
class PropostaTroca:
    """Proposta de troca entre personagens"""
    id: str
    proponente: str              # ID de quem propõe
    receptor: str                # ID de quem recebe
    
    # O que está sendo oferecido
    ofertando: list[ItemTransacao]
    
    # O que está sendo pedido
    pedindo: list[ItemTransacao]
    
    # Tipo de transação
    tipo: TipoTransacao
    
    # Estado
    aceita: Optional[bool] = None  # None = pendente
    motivo_recusa: str = ""


class Mercado:
    """
    Gerencia trocas entre personagens
    """
    
    def __init__(self):
        self.propostas: list[PropostaTroca] = []
        self.historico: list[dict] = []
    
    def criar_proposta(
        self,
        proponente_id: str,
        receptor_id: str,
        ofertando: list[tuple[str, int]],
        pedindo: list[tuple[str, int]],
        tipo: TipoTransacao = TipoTransacao.TROCA
    ) -> PropostaTroca:
        """
        Cria uma proposta de troca
        """
        proposta = PropostaTroca(
            id=f"troca_{len(self.propostas)}_{proponente_id}_{receptor_id}",
            proponente=proponente_id,
            receptor=receptor_id,
            ofertando=[ItemTransacao(nome, qtd) for nome, qtd in ofertando],
            pedindo=[ItemTransacao(nome, qtd) for nome, qtd in pedindo],
            tipo=tipo
        )
        
        self.propostas.append(proposta)
        return proposta
    
    def avaliar_proposta(
        self,
        proposta: PropostaTroca,
        personagem_receptor
    ) -> tuple[bool, str]:
        """
        Avalia se o receptor aceita a proposta
        
        Returns:
            (aceita, motivo)
        """
        # Verificar se tem os itens que está sendo pedido
        for item in proposta.pedindo:
            if not personagem_receptor.tem_item(item.nome, item.quantidade):
                return False, f"Não tenho {item.nome} suficiente"
        
        # Verificar se é uma troca justa
        valor_oferta = sum(item.quantidade for item in proposta.ofertando)
        valor_pedido = sum(item.quantidade for item in proposta.pedindo)
        
        # Avaliar baseado na personalidade
        arquetipo = personagem_receptor.personalidade.arquetipo
        
        # Generoso aceita mais fácil
        if arquetipo == "generoso":
            if valor_oferta >= valor_pedido * 0.5:  # Aceita metade do valor
                return True, "Troca justa"
        
        # Prudente é mais exigente
        elif arquetipo == "prudente":
            if valor_oferta >= valor_pedido * 1.2:  # Quer 20% a mais
                return True, "Compensa pra mim"
            else:
                return False, "Não vale a pena"
        
        # Dominador quer vantagem
        elif arquetipo == "dominador":
            if valor_oferta >= valor_pedido * 1.5:  # Quer 50% a mais
                return True, "Bom negócio"
            else:
                return False, "Não me convence"
        
        # Padrão: troca justa
        if valor_oferta >= valor_pedido:
            return True, "Troca justa"
        else:
            return False, "Não compensa"
    
    def executar_troca(
        self,
        proposta: PropostaTroca,
        proponente,
        receptor
    ) -> dict:
        """
        Executa uma troca aprovada
        
        Returns:
            Resultado da troca
        """
        # Verificar se ambos têm os itens
        for item in proposta.ofertando:
            if not proponente.tem_item(item.nome, item.quantidade):
                return {"sucesso": False, "motivo": f"{proponente.nome} não tem {item.nome}"}
        
        for item in proposta.pedindo:
            if not receptor.tem_item(item.nome, item.quantidade):
                return {"sucesso": False, "motivo": f"{receptor.nome} não tem {item.nome}"}
        
        # Executar transferência
        # Proponente entrega
        for item in proposta.ofertando:
            proponente.remover_item(item.nome, item.quantidade)
            receptor.adicionar_item(item.nome, item.quantidade)
        
        # Receptor entrega
        for item in proposta.pedindo:
            receptor.remover_item(item.nome, item.quantidade)
            proponente.adicionar_item(item.nome, item.quantidade)
        
        # Atualizar relações (troca gera afeto positivo)
        relacao_p = proponente.get_ou_criar_relacao(receptor.id)
        relacao_r = receptor.get_ou_criar_relacao(proponente.id)
        
        relacao_p.afeto = min(1.0, relacao_p.afeto + 0.1)
        relacao_r.afeto = min(1.0, relacao_r.afeto + 0.1)
        
        # Registrar no histórico
        self.historico.append({
            "proponente": proponente.id,
            "receptor": receptor.id,
            "oferecido": [(i.nome, i.quantidade) for i in proposta.ofertando],
            "recebido": [(i.nome, i.quantidade) for i in proposta.pedindo],
            "sucesso": True
        })
        
        return {"sucesso": True, "mensagem": "Troca realizada com sucesso!"}
    
    def gerar_propostas_automaticas(
        self,
        personagem,
        todos_personagens: list
    ) -> list[PropostaTroca]:
        """
        Gera propostas automáticas baseadas em necessidades
        
        Returns:
            Lista de propostas para outros personagens
        """
        propostas = []
        
        # Verificar necessidades
        precisa_comida = personagem.necessidades.fome < 0.5
        precisa_agua = personagem.necessidades.sede < 0.5
        
        # Verificar o que tem para trocar
        materiais = personagem.inventario.get_materiais_dict()
        
        if not materiais:
            return propostas
        
        # Para cada outro personagem
        for outro in todos_personagens:
            if outro.id == personagem.id:
                continue
            
            if outro.local_atual != personagem.local_atual:
                continue
            
            outros_materiais = outro.inventario.get_materiais_dict()
            
            # Verificar se o outro tem algo que precisa
            if precisa_comida and "comida" in outros_materiais:
                # Procurar algo para oferecer
                for mat, qtd in materiais.items():
                    if qtd > 1 and mat != "comida":  # Não trocar comida por comida
                        proposta = self.criar_proposta(
                            proponente_id=personagem.id,
                            receptor_id=outro.id,
                            ofertando=[(mat, 1)],
                            pedindo=[("comida", 1)]
                        )
                        propostas.append(proposta)
                        break
            
            if precisa_agua and "água" in outros_materiais:
                for mat, qtd in materiais.items():
                    if qtd > 1 and mat != "água":
                        proposta = self.criar_proposta(
                            proponente_id=personagem.id,
                            receptor_id=outro.id,
                            ofertando=[(mat, 1)],
                            pedindo=[("água", 1)]
                        )
                        propostas.append(proposta)
                        break
        
        return propostas


# =============================================================================
# EXEMPLO DE USO
# =============================================================================

if __name__ == "__main__":
    from personagem import Personagem, Personalidade
    from habilidades import Habilidade
    
    print("=== Teste de Mercado ===\n")
    
    # Criar personagens
    pers1 = Personalidade(nome='Maria', arquetipo='generoso', descricao='test')
    maria = Personagem(pers1, local_inicial='vila')
    maria.adicionar_item('madeira', 5)
    maria.necessidades.fome = 0.3  # com fome
    
    pers2 = Personalidade(nome='João', arquetipo='prudente', descricao='test')
    joao = Personagem(pers2, local_inicial='vila')
    joao.adicionar_item('comida', 3)
    
    print(f'Maria: {maria.inventario.get_materiais_dict()}')
    print(f'Fome: {maria.necessidades.fome:.0%}')
    print(f'João: {joao.inventario.get_materiais_dict()}')
    
    # Criar mercado
    mercado = Mercado()
    
    # Maria propõe troca
    proposta = mercado.criar_proposta(
        proponente_id=maria.id,
        receptor_id=joao.id,
        ofertando=[('madeira', 2)],
        pedindo=[('comida', 1)]
    )
    
    print(f'\nProposta: Maria dá 2 madeira por 1 comida')
    
    # João avalia
    aceita, motivo = mercado.avaliar_proposta(proposta, joao)
    print(f'João aceita? {aceita} - {motivo}')
    
    if aceita:
        resultado = mercado.executar_troca(proposta, maria, joao)
        print(f'\n{resultado["mensagem"]}')
        print(f'Maria agora: {maria.inventario.get_materiais_dict()}')
        print(f'João agora: {joao.inventario.get_materiais_dict()}')
