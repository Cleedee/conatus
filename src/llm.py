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
    modelo: str = "qwen2.5:0.5b"
    
    # llama.cpp
    llamacpp_url: str = "http://localhost:8080"
    
    # HTTP genérico
    http_url: str = ""
    http_headers: dict = None
    
    # Parâmetros de geração
    temperature: float = 0.7
    max_tokens: int = 200
    top_p: float = 0.9
    
    # Timeout
    timeout: int = 30


# =============================================================================
# FUNÇÕES AUXILIARES HTTP
# =============================================================================

def http_post_json(url: str, data: dict, timeout: int = 30) -> dict:
    """Faz POST com JSON usando urllib"""
    headers = {"Content-Type": "application/json"}
    data_bytes = json.dumps(data).encode("utf-8")
    
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise Exception(f"Erro HTTP: {e}")


def http_get_json(url: str, timeout: int = 10) -> Optional[dict]:
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
        """Retorna resposta simulada"""
        import random
        
        # Análise simples do prompt para gerar resposta contextual
        if "comida" in prompt.lower() or "fome" in prompt.lower():
            acao = 1  # primeira opção geralmente é comida
            razao = "Estou com fome, preciso comer"
        elif "água" in prompt.lower() or "sede" in prompt.lower():
            acao = 1
            razao = "Preciso de água"
        elif "dormir" in prompt.lower() or "sono" in prompt.lower():
            acao = "evitar"
            razao = "Estou cansado, vou descansar"
        elif "social" in prompt.lower() or "conversa" in prompt.lower():
            acao = 1
            razao = "Vou interagir com os outros"
        elif "perigo" in prompt.lower():
            acao = "evitar"
            razao = "Isso parece perigoso, vou evitar"
        else:
            acoes_num = [1, 2, 3, "evitar"]
            acao = random.choice(acoes_num)
            razao = "Escolhi esta opção baseado na situação"
        
        return json.dumps({
            "escolha": acao,
            "razao": razao,
            "emocao": random.choice(["alegria", "neutro", "temor", "esperança"])
        })
    
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
        Gera prompt para decisão do personagem
        """
        # Formatar encontros
        encontros_texto = "\n".join([
            f"{i+1}. {e.descricao} (tipo: {e.tipo.value}, intensidade: {e.intensidade:.1f})"
            for i, e in enumerate(encontros)
        ])
        
        # Formatar memórias relevantes
        memorias = personagem.get_contexto_memoria()
        
        prompt = f"""Papel: Você É {personagem.personalidade.nome}. Não é assistente.
{personagem.personalidade.nome} está com fome {personagem.necessidades.fome:.0%} e sede {personagem.necessidades.sede:.0%}.
{personagem.personalidade.nome} pode:
{encontros_texto}

{personagem.personalidade.nome} escolhe:"""
        return prompt
    
    @staticmethod
    def prompt_resposta_social(
        personagem,
        interlocutor,
        contexto: str
    ) -> str:
        """
        Gera prompt para resposta social (diálogo)
        """
        # Buscar relação
        relacao = personagem.get_ou_criar_relacao(interlocutor.id)
        
        prompt = f"""Você é {personagem.personalidade.nome}.

INTERLOCUTOR: {interlocutor.nome}
Sua relação com {interlocutor.nome}:
- Afeto: {relacao.afeto:.2f} (-1 a 1)
- Confiança: {relacao.confianca:.2f} (0 a 1)
- Encontros anteriores: {relacao.encontros_positivos} positivos, {relacao.encontros_negativos} negativos

SEU ESTADO:
- Potência: {personagem.potencia_atual:.0%}
- Alegria: {personagem.afetos.alegria:.2f}
- Temor: {personagem.afetos.temor:.2f}

CONTEXTO:
{contexto}

PERSONALIDADE:
{personagem.personalidade.descricao}
Valores: {', '.join(personagem.personalidade.valores)}

Como você responde? Seja fiel à sua personalidade e relação com a pessoa.

Responda APENAS em JSON:
{{
    "fala": "<o que você diz>",
    "tom": "<amigável|neutro|desconfiado|hostil|ajudativo>",
    "pensamento": "<o que pensa internamente>"
}}
"""
        return prompt
    
    @staticmethod
    def prompt_observacao(
        personagem,
        cena: str
    ) -> str:
        """
        Gera prompt para observação de cena
        """
        prompt = f"""Você é {personagem.personalidade.nome}.

VOCÊ OBSERVA:
{cena}

SEU ESTADO:
- Potência: {personagem.potencia_atual:.0%}
- Razão: {personagem.razao_vs_paixao:.0%}
- Medos: {', '.join(personagem.personalidade.medos)}

Como você interpreta o que vê? O que pensa? Algo muda em sua opinião?

Responda APENAS em JSON:
{{
    "interpretacao": "<o que você entende da cena>",
    "reacao_interna": "<como se sente>",
    "mudanca_opiniao": <true|false>
}}
"""
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
        
        # Procurar números no início ou após "opção"/"escolha"
        match_num = re.search(r'(?:opção|escolha|opcao)[:\s]*(\d+)', resposta, re.IGNORECASE)
        if match_num:
            resultado["escolha"] = int(match_num.group(1))
        else:
            # Procurar qualquer número isolado
            match_num2 = re.search(r'\b(\d)\b', resposta)
            if match_num2:
                resultado["escolha"] = int(match_num2.group(1))
        
        # Usar a resposta inteira como razão se não achou padrão
        resultado["razao"] = resposta[:200].strip()
        
        return resultado
    
    @staticmethod
    def parsear_resposta_social(resposta: str) -> dict:
        """Parseia resposta social"""
        return ParseRespostas._extrair_json(resposta, {
            "fala": "...",
            "tom": "neutro",
            "pensamento": "..."
        })
    
    @staticmethod
    def parsear_observacao(resposta: str) -> dict:
        """Parseia resposta de observação"""
        return ParseRespostas._extrair_json(resposta, {
            "interpretacao": "Nenhuma interpretação",
            "reacao_interna": "neutro",
            "mudanca_opiniao": False
        })
    
    @staticmethod
    def _extrair_json(texto: str, padrao: dict) -> dict:
        """Extrai JSON de texto, com fallback"""
        # Tentar encontrar JSON no texto
        padrao_json = re.findall(r'\{[^{}]+\}', texto, re.DOTALL)
        
        for json_str in padrao_json:
            try:
                resultado = json.loads(json_str)
                # Mesclar com padrão
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
