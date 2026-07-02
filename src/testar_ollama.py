#!/usr/bin/env python3
"""
Script de teste com Ollama real

Rode na sua máquina onde o Ollama está instalado:
python3 testar_ollama.py
"""

import sys
import os

# Adicionar src ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm import criar_llm, ConfigLLM, ProviderLLM
from personagem import Personagem, Personalidade, TipoEncontro
from encontros import MotorEncontros, EncontroDisponivel, OrigemEncontro, DisponibilidadeEncontro
from mapa import criar_mapa_padrao


def testar_conexao():
    """Testa conexão com Ollama"""
    print("=" * 60)
    print("🔌 TESTANDO CONEXÃO COM OLLAMA")
    print("=" * 60)
    
    config = ConfigLLM(
        provider=ProviderLLM.OLLAMA,
        modelo="qwen2.5:0.5b"
    )
    
    llm = criar_llm(config)
    print(f"\nTipo de LLM: {type(llm).__name__}")
    print(f"Disponível: {llm.verificar_disponivel()}")
    
    if hasattr(llm, 'listar_modelos'):
        modelos = llm.listar_modelos()
        print(f"Modelos disponíveis: {modelos}")
    
    return llm


def testar_inferencia(llm):
    """Testa inferência básica"""
    print("\n" + "=" * 60)
    print("🧠 TESTANDO INFERÊNCIA")
    print("=" * 60)
    
    prompt = """Papel: Você É Maria, 35 anos.
Maria tem fome 40% e sede 60%.
Maria pode:
1. Comer no depósito
2. Buscar água
3. Conversar com João

Maria escolhe:"""
    
    print("\nPrompt enviado:")
    print("-" * 40)
    print(prompt[:500] + "...")
    print("-" * 40)
    
    print("\n⏳ Gerando resposta...")
    resposta = llm.inferir(prompt)
    
    print("\n📝 Resposta do LLM:")
    print("-" * 40)
    print(resposta)
    print("-" * 40)
    
    return resposta


def testar_personagem_com_llm(llm):
    """Testa tomada de decisão de personagem com LLM"""
    print("\n" + "=" * 60)
    print("👤 TESTANDO DECISÃO DE PERSONAGEM")
    print("=" * 60)
    
    from llm import AgenteLLM
    
    agente = AgenteLLM(llm)
    
    # Criar personagem
    pers = Personalidade(
        nome="Maria",
        arquetipo="generoso",
        idade=35,
        descricao="Mulher calorosa que acredita no poder da comunidade",
        razao_innata=0.6,
        motivacoes={
            "sobrevivencia": 0.8,
            "ajudar_outros": 0.9,
            "reputacao": 0.7
        },
        valores=["solidariedade", "honestidade"],
        medos=["traição", "solidão"]
    )
    
    maria = Personagem(pers, local_inicial="vila")
    maria.necessidades.fome = 0.4  # com fome
    
    print(f"\nPersonagem: {maria.nome}")
    print(f"Fome: {maria.necessidades.fome:.0%}")
    print(f"Potência: {maria.potencia_atual:.0%}")
    
    # Criar encontros disponíveis
    encontros = [
        EncontroDisponivel(
            id="comida_1",
            origem=OrigemEncontro.RECURSO,
            tipo=TipoEncontro.RECURSO,
            objeto="comida",
            descricao="Pegar comida do depósito comum",
            intensidade=0.2,
            disponibilidade=DisponibilidadeEncontro.SEMPRE
        ),
        EncontroDisponivel(
            id="agua_1",
            origem=OrigemEncontro.RECURSO,
            tipo=TipoEncontro.RECURSO,
            objeto="agua",
            descricao="Buscar água no poço",
            intensidade=0.15,
            disponibilidade=DisponibilidadeEncontro.SEMPRE
        ),
        EncontroDisponivel(
            id="joao_1",
            origem=OrigemEncontro.SOCIAL,
            tipo=TipoEncontro.SOCIAL,
            objeto="joao",
            descricao="Conversar com João sobre o grupo",
            intensidade=0.3,
            disponibilidade=DisponibilidadeEncontro.SEMPRE
        )
    ]
    
    contexto = {
        "local": "vila",
        "hora": 10,
        "outros": "João e Lúcia"
    }
    
    print("\n🎯 Encontros disponíveis:")
    for i, e in enumerate(encontros, 1):
        print(f"  {i}. {e.descricao}")
    
    print("\n⏳ LLM decidindo...")
    decisao = agente.decidir_acao(maria, encontros, contexto)
    
    print("\n💡 Decisão do LLM:")
    print(f"  Escolha: {decisao.get('escolha')}")
    print(f"  Razão: {decisao.get('razao')}")
    print(f"  Emoção: {decisao.get('emocao')}")
    
    if decisao.get("encontro"):
        print(f"  Encontro selecionado: {decisao['encontro'].descricao}")


def testar_simulacao_completa():
    """Testa simulação completa com Ollama"""
    print("\n" + "=" * 60)
    print("🌍 SIMULAÇÃO COMPLETA (5 ticks)")
    print("=" * 60)
    
    from mundo import Simulacao, criar_mapa_padrao
    from personagem import Personagem, Personalidade
    
    # Criar personagens
    personagens = []
    
    pers_maria = Personalidade(
        nome="Maria",
        arquetipo="generoso",
        idade=35,
        descricao="Mulher calorosa",
        razao_innata=0.6
    )
    personagens.append(Personagem(pers_maria, local_inicial="vila"))
    
    pers_joao = Personalidade(
        nome="João",
        arquetipo="prudente",
        idade=40,
        descricao="Homem cauteloso",
        razao_innata=0.7
    )
    personagens.append(Personagem(pers_joao, local_inicial="vila"))
    
    pers_ana = Personalidade(
        nome="Ana",
        arquetipo="ativo",
        idade=28,
        descricao="Jovem energica",
        razao_innata=0.4
    )
    personagens.append(Personagem(pers_ana, local_inicial="planicie"))
    
    # Criar simulação com LLM
    config = ConfigLLM(
        provider=ProviderLLM.OLLAMA,
        modelo="qwen2.5:0.5b",
        temperature=0.7,
        max_tokens=150
    )
    
    sim = Simulacao(
        mapa=criar_mapa_padrao(),
        personagens=personagens,
        usar_llm=True,
        config_llm=config
    )
    
    print(f"\nLLM ativo: {sim.agente_llm is not None}")
    print(f"Tipo: {type(sim.agente_llm.llm).__name__}")
    
    # Rodar 5 ticks
    for i in range(5):
        print(f"\n--- Tick {i+1} ---")
        sim.tick()


def main():
    """Função principal"""
    print("🚀 TESTE DE SIMULAÇÃO COM OLLAMA")
    print("=" * 60)
    
    # 1. Testar conexão
    llm = testar_conexao()
    
    if not llm.verificar_disponivel():
        print("\n❌ Ollama não está disponível!")
        print("Verifique se o Ollama está rodando: ollama serve")
        return
    
    # 2. Testar inferência
    testar_inferencia(llm)
    
    # 3. Testar decisão de personagem
    testar_personagem_com_llm(llm)
    
    # 4. Simulação completa (opcional - mais lento)
    resposta = input("\n\nRodar simulação completa? (s/n): ")
    if resposta.lower() == 's':
        testar_simulacao_completa()
    
    print("\n✅ Testes concluídos!")


if __name__ == "__main__":
    main()
