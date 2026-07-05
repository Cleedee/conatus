"""
Módulo LLM — Interface com Modelos de Linguagem

Fornece integração com:
- Ollama (local)
- llama.cpp (local)
- APIs HTTP genéricas

Usado para decisões dos personagens na simulação.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import json
import re
from abc import ABC, abstractmethod

# Usar urllib que já vem no Python padrão
import urllib.request
import urllib.error


# =============================================================================
# ENUMS E CONFIGURAÇÕES
# =============================================================================

class ProviderLLM(Enum):
    """Provedores de LLM suportados"""
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"
    HTTP = "http"


@dataclass
class ConfigLLM:
    """Configuração para conexão com LLM"""
    provider: ProviderLLM = ProviderLLM.OLLAMA
    
    # Ollama
    ollama_url: str = "http://localhost:11434"
    modelo: str = "qwen2.5:1.5b"
    
    # llama.cpp
    llamacpp_url: str = "http://localhost:8080"
    
    # HTTP genérico
    http_url: str = ""
    http_headers: dict = None
    
    # Parâmetros de geração
    temperature: float = 0.7
    max_tokens: int = 120
    top_p: float = 0.9
    
    # Timeout (segundos)
    timeout: int = 120


# =============================================================================
# FUNÇÕES AUXILIARES HTTP
# =============================================================================

def http_post_json(url: str, data: dict, timeout: int = 120) -> dict:
    """Faz POST com JSON usando urllib"""
    headers = {"Content-Type": "application/json"}
    data_bytes = json.dumps(data).encode("utf-8")
    
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise Exception(f"Erro HTTP: {e}")


def http_get_json(url: str, timeout: int = 30) -> Optional[dict]:
    """Faz GET e retorna JSON usando urllib"""
    req = urllib.request.Request(url)
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except:
        return None


# =============================================================================
# ABSTRAÇÃO DE LLM
# =============================================================================

class LLMInterface(ABC):
    """Interface abstrata para LLMs"""
    
    @abstractmethod
    def inferir(self, prompt: str) -> str:
        """Gera resposta a partir de prompt"""
        pass
    
    @abstractmethod
    def verificar_disponivel(self) -> bool:
        """Verifica se o LLM está disponível"""
        pass


# =============================================================================
# IMPLEMENTAÇÕES
# =============================================================================

class OllamaLLM(LLMInterface):
    """Interface com Ollama"""
    
    def __init__(self, config: ConfigLLM):
        self.config = config
        self.base_url = config.ollama_url
    
    def inferir(self, prompt: str) -> str:
        """Gera resposta usando Ollama"""
        try:
            resultado = http_post_json(
                f"{self.base_url}/api/generate",
                data={
                    "model": self.config.modelo,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.config.temperature,
                        "num_predict": self.config.max_tokens,
                        "top_p": self.config.top_p
                    }
                },
                timeout=self.config.timeout
            )
            return resultado.get("response", "")
        
        except Exception as e:
            print(f"Erro ao conectar com Ollama: {e}")
            return ""
    
    def verificar_disponivel(self) -> bool:
        """Verifica se Ollama está rodando"""
        resultado = http_get_json(f"{self.base_url}/api/tags", timeout=5)
        return resultado is not None
    
    def listar_modelos(self) -> list[str]:
        """Lista modelos disponíveis"""
        resultado = http_get_json(f"{self.base_url}/api/tags")
        if resultado:
            return [m["name"] for m in resultado.get("models", [])]
        return []


class LlamaCppLLM(LLMInterface):
    """Interface com llama.cpp server"""
    
    def __init__(self, config: ConfigLLM):
        self.config = config
        self.base_url = config.llamacpp_url
    
    def inferir(self, prompt: str) -> str:
        """Gera resposta usando llama.cpp"""
        try:
            resultado = http_post_json(
                f"{self.base_url}/completion",
                data={
                    "prompt": prompt,
                    "n_predict": self.config.max_tokens,
                    "temperature": self.config.temperature,
                    "top_p": self.config.top_p,
                    "stream": False
                },
                timeout=self.config.timeout
            )
            return resultado.get("content", "")
        
        except Exception as e:
            print(f"Erro ao conectar com llama.cpp: {e}")
            return ""
    
    def verificar_disponivel(self) -> bool:
        """Verifica se llama.cpp está rodando"""
        resultado = http_get_json(f"{self.base_url}/health", timeout=5)
        return resultado is not None


class HTTPLLM(LLMInterface):
    """Interface HTTP genérica"""
    
    def __init__(self, config: ConfigLLM):
        self.config = config
        self.headers = config.http_headers or {
            "Content-Type": "application/json"
        }
    
    def inferir(self, prompt: str) -> str:
        """Gera resposta usando API HTTP genérica"""
        try:
            # Criar request manualmente para custom headers
            data = {
                "prompt": prompt,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
            data_bytes = json.dumps(data).encode("utf-8")
            
            req = urllib.request.Request(
                self.config.http_url,
                data=data_bytes,
                headers=self.headers,
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                resultado = json.loads(response.read().decode("utf-8"))
            
            # Tentar diferentes formatos de resposta
            if "choices" in resultado:
                return resultado["choices"][0].get("text", "")
            elif "response" in resultado:
                return resultado["response"]
            elif "content" in resultado:
                return resultado["content"]
            else:
                return str(resultado)
        
        except Exception as e:
            print(f"Erro na API HTTP: {e}")
            return ""
    
    def verificar_disponivel(self) -> bool:
        """Verifica se API está disponível"""
        try:
            base_url = self.config.http_url.rsplit("/", 1)[0]
            req = urllib.request.Request(base_url)
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status < 500
        except:
            return False


# =============================================================================
# GERADOR DE LLM
# =============================================================================

def criar_llm(config: ConfigLLM = None) -> LLMInterface:
    """
    Cria instância de LLM baseado na configuração
    
    Tenta detectar automaticamente se não especificado
    """
    if config is None:
        config = ConfigLLM()
    
    # Tentar detectar automaticamente
    if config.provider == ProviderLLM.OLLAMA:
        llm = OllamaLLM(config)
        if llm.verificar_disponivel():
            return llm
    
    if config.provider == ProviderLLM.LLAMACPP:
        llm = LlamaCppLLM(config)
        if llm.verificar_disponivel():
            return llm
    
    # Fallback: tentar cada um
    for LLMClass, cfg in [
        (OllamaLLM, ConfigLLM(provider=ProviderLLM.OLLAMA)),
        (LlamaCppLLM, ConfigLLM(provider=ProviderLLM.LLAMACPP))
    ]:
        try:
            llm = LLMClass(cfg)
            if llm.verificar_disponivel():
                print(f"✓ LLM detectado: {cfg.provider.value}")
                return llm
        except:
            continue
    
    # Se nenhum disponível, usar mock
    print("⚠ Nenhum LLM detectado. Usando decisões simuladas.")
    return MockLLM()


class MockLLM(LLMInterface):
    """LLM mock para testes sem modelo real"""
    
    def inferir(self, prompt: str) -> str:
        """Retorna resposta simulada — tenta simular decisão contextual"""
        import re

        # Extrair o número de opções do prompt
        opcoes = re.findall(r'^(\d+)\.\s+(.*)', prompt, re.MULTILINE)
        n_opcoes = len(opcoes)

        def _encontrar_opcao(palavras_chave):
            """Retorna o índice (1-based) da primeira opção que contém alguma palavra-chave"""
            for num, desc in opcoes:
                desc_lower = desc.lower()
                if any(p.lower() in desc_lower for p in palavras_chave):
                    return int(num)
            return None

        # 1. Se está vulnerável e há opção de sono/abrigo, priorizar descanso
        if "vulnerável" in prompt.lower() or "AVISO" in prompt:
            idx_sono = _encontrar_opcao(["Dormir", "sono"])
            if idx_sono:
                return json.dumps({
                    "escolha": idx_sono,
                    "razao": "Estou vulnerável, preciso descansar e me recuperar",
                    "emocao": "temor"
                })
            idx_abrigo = _encontrar_opcao(["abrigo", "abrigar"])
            if idx_abrigo:
                return json.dumps({
                    "escolha": idx_abrigo,
                    "razao": "Preciso de um abrigo para me proteger",
                    "emocao": "temor"
                })

        # 2. Necessidades básicas
        if "fome" in prompt.lower() or "comida" in prompt.lower():
            idx = _encontrar_opcao(["comer", "comida", "caça", "caçar", "pescar", "colher"])
            if idx:
                return json.dumps({
                    "escolha": idx,
                    "razao": "Preciso de comida para sobreviver",
                    "emocao": "desejo"
                })

        if "sede" in prompt.lower() or "água" in prompt.lower():
            idx = _encontrar_opcao(["água", "beber", "poço"])
            if idx:
                return json.dumps({
                    "escolha": idx,
                    "razao": "Preciso de água",
                    "emocao": "desejo"
                })

        # 3. Perigo: evitar
        if "☠ PERIGO" in prompt or "perigosa" in prompt.lower():
            # Procurar opção SEM perigo
            for num, desc in opcoes:
                if "☠ PERIGO" not in desc and "prejudicado" not in desc.lower():
                    return json.dumps({
                        "escolha": int(num),
                        "razao": "Evito situações perigosas, especialmente agora",
                        "emocao": "temor"
                    })

        # 4. Fallback: comportamento baseado em arquétipo
        prompt_lower = prompt.lower()
        if "ativo" in prompt_lower:
            idx = _encontrar_opcao(["explorar", "locomocao", "aventura"])
            if idx:
                return json.dumps({"escolha": idx, "razao": "Quero explorar e agir", "emocao": "desejo"})
        if "prudente" in prompt_lower:
            idx = _encontrar_opcao(["recurso", "coletar", "craft", "construir"])
            if idx:
                return json.dumps({"escolha": idx, "razao": "Melhor garantir recursos", "emocao": "neutro"})
        if "generoso" in prompt_lower:
            idx = _encontrar_opcao(["social", "conversa", "falar", "ajudar"])
            if idx:
                return json.dumps({"escolha": idx, "razao": "Vou interagir com os outros", "emocao": "alegria"})

        # Fallback final: aleatório entre opções válidas
        if n_opcoes > 0:
            import random
            idx = random.choice(range(1, n_opcoes + 1))
            return json.dumps({
                "escolha": idx,
                "razao": "Escolhi esta opção baseado na situação",
                "emocao": random.choice(["neutro", "esperança"])
            })

        return json.dumps({"escolha": 1, "razao": "Vou agir", "emocao": "neutro"})
    
    def verificar_disponivel(self) -> bool:
        return True


# =============================================================================
# SISTEMA DE PROMPTS
# =============================================================================

class GeradorPrompts:
    """
    Gera prompts para os personagens tomarem decisões
    """
    
    @staticmethod
    def prompt_decisao(
        personagem,
        encontros: list,
        contexto: dict
    ) -> str:
        """
        Gera prompt de decisão rico para o personagem escolher uma ação.
        """
        # Determinar período do dia para contexto
        hora = contexto.get("hora", 8)
        e_noite = not (6 <= hora <= 20)
        periodo = "NOITE" if e_noite else ("MANHÃ" if hora < 12 else "TARDE" if hora < 18 else "ENTARDECER")

        # Indicador de perigo/benefício para cada opção
        encontros_texto = "\n".join([
            f"{i+1}. {e.descricao}"
            + (" ☠ PERIGO" if e.resultado_sugerido and e.resultado_sugerido.value == "dissolucao" else "")
            + (" ✅ BENÉFICO" if e.resultado_sugerido and e.resultado_sugerido.value == "adequacao" else "")
            + f" ({e.tipo.value}, {getattr(e, 'tag', '')})"
            for i, e in enumerate(encontros)
        ])

        motiv_str = ", ".join(
            f"{k}: {v:.0%}"
            for k, v in personagem.personalidade.motivacoes.items()
        )

        prompt = f"""Você é {personagem.personalidade.nome}, uma pessoa {personagem.personalidade.arquetipo}.

ESTADO ATUAL:
- Fome: {personagem.necessidades.fome:.0%} | Sede: {personagem.necessidades.sede:.0%}
- Energia: {personagem.necessidades.energia:.0%} | Saúde: {personagem.necessidades.saude:.0%}
- Potência: {personagem.potencia_atual:.0%} | Alegria: {personagem.afetos.alegria:.2f}

PERSONALIDADE:
- Arquétipo: {personagem.personalidade.arquetipo}
- Descrição: {personagem.personalidade.descricao}
- Valores: {', '.join(personagem.personalidade.valores)}
- Medos: {', '.join(personagem.personalidade.medos)}
- Motivações: {motiv_str}

"""

        # Contexto de local/horário
        prompt += f"📍 LOCAL: {contexto.get('local', '?')} — {periodo} ({hora}h)"
        if e_noite:
            prompt += " 🌙 Escuro, perigoso, difícil enxergar."
        prompt += f"\n{contexto.get('outros', 'Sozinho')}\n"

        # Aviso de vulnerabilidade
        if personagem.potencia_relativa < 0.3:
            prompt += f"\n⚠ AVISO: Sua potência está criticamente baixa ({personagem.potencia_atual:.0%}). Você está vulnerável. Evite riscos desnecessários. Priorize segurança, descanso ou abrigo.\n"

        # Aviso de necessidades críticas
        nec_criticas = []
        if personagem.necessidades.fome < 0.3:
            nec_criticas.append(f"fome extrema ({personagem.necessidades.fome:.0%})")
        if personagem.necessidades.sede < 0.3:
            nec_criticas.append(f"sede extrema ({personagem.necessidades.sede:.0%})")
        if personagem.necessidades.energia < 0.2:
            nec_criticas.append(f"exaustão ({personagem.necessidades.energia:.0%})")
        if personagem.necessidades.abrigo < 0.2:
            nec_criticas.append(f"sem abrigo ({personagem.necessidades.abrigo:.0%})")
        if personagem.necessidades.saude < 0.3:
            nec_criticas.append(f"saúde debilitada ({personagem.necessidades.saude:.0%})")
        if nec_criticas:
            prompt += f"\n⚠ URGENTE: {', '.join(nec_criticas)}. Atenda estas necessidades primeiro!\n"

        prompt += f"\nOPÇÕES DISPONÍVEIS:\n{encontros_texto}\n"

        prompt += f"""
Analise a situação, avalie os riscos e benefícios de cada opção,
considere suas necessidades urgentes e sua personalidade.

Responda neste formato (substitua X pelo número escolhido):
Raciocínio: [explique sua escolha]
Número: X"""

        return prompt

    @staticmethod
    def prompt_resposta_social(
        personagem,
        interlocutor,
        contexto: str
    ) -> str:
        """
        Gera prompt curto para resposta social (diálogo)
        """
        relacao = personagem.get_ou_criar_relacao(interlocutor.id)

        motiv_str = ", ".join(
            f"{k}: {v:.0%}"
            for k, v in personagem.personalidade.motivacoes.items()
        )

        prompt = f"""Você é {personagem.personalidade.nome}, {personagem.personalidade.arquetipo}.
{personagem.personalidade.descricao}
Motivações: {motiv_str}
Afeto por {interlocutor.nome}: {relacao.afeto:.2f}
Confiança: {relacao.confianca:.2f}

Contexto: {contexto}

Fale uma frase curta como {personagem.personalidade.nome} respondendo a {interlocutor.nome}:"""
        return prompt

    @staticmethod
    def prompt_observacao(
        personagem,
        cena: str
    ) -> str:
        """
        Gera prompt curto para observação de cena
        """
        prompt = f"""Você é {personagem.personalidade.nome}, {personagem.personalidade.arquetipo}.
{personagem.personalidade.descricao}
Medos: {', '.join(personagem.personalidade.medos)}

Você observa: {cena}

O que você pensa sobre isso? Uma frase curta:"""
        return prompt


# =============================================================================
# PARSE DE RESPOSTAS
# =============================================================================

class ParseRespostas:
    """
    Parseia respostas JSON dos LLMs
    """
    
    @staticmethod
    def parsear_decisao(resposta: str) -> dict:
        """Parseia resposta de decisão"""
        import re
        
        # Tentar JSON primeiro
        resultado = ParseRespostas._extrair_json(resposta, None)
        if resultado:
            resultado.setdefault("escolha", 1)
            resultado.setdefault("razao", "Sem razão")
            resultado.setdefault("emocao", "neutro")
            return resultado
        
        # Tentar extrair de texto livre
        resultado = {"escolha": 1, "razao": "", "emocao": "neutro"}
        
        # Extrair raciocínio/razão (novo formato: "Raciocínio: ...")
        match_razao = re.search(r'(?:Raciocínio|Razão|Raciocinio|Razao)[:\s]*(.*?)(?:\n|$)', resposta, re.IGNORECASE | re.DOTALL)
        if match_razao:
            resultado["razao"] = match_razao.group(1).strip()[:200]
        
        # Procurar número após "Número:" (novo formato) ou "opção"/"escolha" (formato antigo)
        match_num = re.search(r'(?:N[uúüÚÜ]mero|n[uúüÚÜ]mero|opção|escolha|opcao)[:\s]*(\d+)', resposta, re.IGNORECASE)
        if match_num:
            resultado["escolha"] = int(match_num.group(1))
        else:
            # Procurar qualquer número isolado (fallback)
            match_num2 = re.search(r'\b(\d+)\b', resposta)
            if match_num2:
                resultado["escolha"] = int(match_num2.group(1))
        
        # Se não encontrou raciocínio, usar a resposta inteira como razão
        if not resultado["razao"]:
            resultado["razao"] = resposta[:200].strip()
        
        return resultado
    
    @staticmethod
    def parsear_resposta_social(resposta: str) -> dict:
        """Parseia resposta social — extrai JSON ou usa texto puro"""
        resultado = ParseRespostas._extrair_json(resposta, None)
        if resultado:
            resultado.setdefault("fala", "...")
            resultado.setdefault("tom", "neutro")
            resultado.setdefault("pensamento", "")
            return resultado
        # Fallback: usar texto puro como fala
        fala = resposta.strip().strip('"').strip("'").strip()
        if len(fala) > 200:
            fala = fala[:200]
        return {"fala": fala, "tom": "neutro", "pensamento": ""}

    @staticmethod
    def parsear_observacao(resposta: str) -> dict:
        """Parseia resposta de observação — extrai JSON ou usa texto puro"""
        resultado = ParseRespostas._extrair_json(resposta, None)
        if resultado:
            resultado.setdefault("interpretacao", "Nenhuma interpretação")
            resultado.setdefault("reacao_interna", "neutro")
            resultado.setdefault("mudanca_opiniao", False)
            return resultado
        # Fallback: usar texto puro como interpretação
        texto = resposta.strip().strip('"').strip("'").strip()
        if len(texto) > 200:
            texto = texto[:200]
        return {"interpretacao": texto, "reacao_interna": "neutro", "mudanca_opiniao": False}
    
    @staticmethod
    def _extrair_json(texto: str, padrao: dict) -> dict:
        """Extrai JSON de texto, com fallback"""
        # Tentar encontrar JSON no texto
        padrao_json = re.findall(r'\{[^{}]+\}', texto, re.DOTALL)
        
        for json_str in padrao_json:
            try:
                resultado = json.loads(json_str)
                # Mesclar com padrão (se fornecido)
                if padrao is not None:
                    for chave, valor in padrao.items():
                        if chave not in resultado:
                            resultado[chave] = valor
                return resultado
            except json.JSONDecodeError:
                continue
        
        # Se não encontrou, retornar padrão
        return padrao


# =============================================================================
# INTERFACE ALTA NÍVEL
# =============================================================================

class AgenteLLM:
    """
    Interface de alto nível para usar LLM na simulação
    """
    
    def __init__(self, llm: LLMInterface = None):
        self.llm = llm or criar_llm()
        self.gerador_prompts = GeradorPrompts()
        self.parseador = ParseRespostas()
    
    def decidir_acao(
        self,
        personagem,
        encontros: list,
        contexto: dict
    ) -> dict:
        """
        LLM decide ação do personagem
        """
        if not encontros:
            return {"escolha": "ficar", "razao": "Nenhum encontro disponível"}
        
        # Gerar prompt
        prompt = self.gerador_prompts.prompt_decisao(
            personagem, encontros, contexto
        )
        
        # Obter resposta
        resposta = self.llm.inferir(prompt)
        
        # Parsear
        resultado = self.parseador.parsear_decisao(resposta)
        
        # Converter escolha para encontro
        escolha = resultado.get("escolha", 1)
        
        if escolha == "evitar" or escolha == "ficar":
            resultado["encontro"] = None
        elif isinstance(escolha, int) and 1 <= escolha <= len(encontros):
            resultado["encontro"] = encontros[escolha - 1]
        else:
            # Tentar converter para int
            try:
                idx = int(escolha) - 1
                if 0 <= idx < len(encontros):
                    resultado["encontro"] = encontros[idx]
                else:
                    resultado["encontro"] = encontros[0]  # fallback
            except:
                resultado["encontro"] = encontros[0]  # fallback
        
        return resultado
    
    def gerar_resposta_social(
        self,
        personagem,
        interlocutor,
        contexto: str
    ) -> dict:
        """
        LLM gera resposta social
        """
        prompt = self.gerador_prompts.prompt_resposta_social(
            personagem, interlocutor, contexto
        )
        
        resposta = self.llm.inferir(prompt)
        
        return self.parseador.parsear_resposta_social(resposta)
    
    def interpretar_observacao(
        self,
        personagem,
        cena: str
    ) -> dict:
        """
        LLM interpreta observação
        """
        prompt = self.gerador_prompts.prompt_observacao(personagem, cena)
        
        resposta = self.llm.inferir(prompt)
        
        return self.parseador.parsear_observacao(resposta)
    
    def verificar_pronto(self) -> bool:
        """Verifica se LLM está pronto para uso"""
        return self.llm.verificar_disponivel()


# =============================================================================
# EXEMPLO DE USO
# =============================================================================

if __name__ == "__main__":
    print("=== Teste de LLM ===\n")
    
    # Criar LLM
    llm = criar_llm()
    
    print(f"LLM criado: {type(llm).__name__}")
    print(f"Disponível: {llm.verificar_disponivel()}")
    
    # Teste básico
    if llm.verificar_disponivel():
        print("\nTeste de inferência:")
        resposta = llm.inferir("Olá, como vai?")
        print(f"Resposta: {resposta[:100]}...")
    else:
        print("\nUsando Mock LLM")
        resposta = llm.inferir("Preciso de comida, estou com fome")
        print(f"Resposta mock: {resposta}")
    
    # Testar Agente
    print("\n=== Teste de Agente ===\n")
    
    agente = AgenteLLM(llm)
    print(f"Agente criado e pronto: {agente.verificar_pronto()}")
