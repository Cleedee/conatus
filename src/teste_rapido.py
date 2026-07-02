#!/usr/bin/env python3
"""
Teste rápido com Ollama

Uso: python3 teste_rapido.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm import criar_llm, ConfigLLM, ProviderLLM

def main():
    print("🔌 Conectando com Ollama...")
    
    config = ConfigLLM(
        provider=ProviderLLM.OLLAMA,
        modelo="qwen2.5:0.5b"
    )
    
    llm = criar_llm(config)
    
    if not llm.verificar_disponivel():
        print("❌ Ollama não encontrado!")
        print("   Certifique-se que está rodando: ollama serve")
        return
    
    print(f"✓ Conectado: {type(llm).__name__}")
    print(f"✓ Modelos: {llm.listar_modelos()}")
    
    # Teste simples
    print("\n📝 Teste de prompt:")
    
    prompt = """Papel: Você É Maria, 35 anos.
Maria tem fome 40% e sede 60%.
Maria pode:
1. Comer no depósito
2. Buscar água

Maria escolhe:"""
    
    print(prompt)
    print("⏳ Gerando resposta...\n")
    
    resposta = llm.inferir(prompt)
    print("Resposta:")
    print(resposta)
    
    # Tentar parsear
    try:
        import re
        json_match = re.search(r'\{[^{}]+\}', resposta, re.DOTALL)
        if json_match:
            dados = json.loads(json_match.group())
            print(f"\n✓ Parseado: {dados}")
    except:
        print("\n⚠ Não foi possível parsear como JSON")

if __name__ == "__main__":
    main()
