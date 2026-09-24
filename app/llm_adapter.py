import asyncio
import os
import time

from dotenv import load_dotenv
from google import genai

load_dotenv()

# Tempo máximo (em segundos) que esperamos pela resposta do Gemini.
# Serve para o sistema nunca ficar preso indefinidamente numa chamada.
TEMPO_MAXIMO = 180

# Erro que representa o Gemini ter estourado o nosso tempo limite.
class GeminiTimeout(Exception):
    pass

class LLMAdapter:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY não configurada."
            )

        self.client = genai.Client(
            api_key=api_key
        )

    async def generate(self, context: dict):
        prompt = self._build_prompt(context)

        response_schema = context.get("response_schema")

        if not response_schema:
            raise ValueError(
                "response_schema não encontrado no contexto."
            )

        inicio = time.perf_counter()

        try:
            # asyncio.wait_for corta a chamada se ela passar de TEMPO_MAXIMO
            # segundos, contando o tempo TOTAL. Este é o corte confiável.
            interaction = await asyncio.wait_for(
                self._chamar_gemini(prompt, response_schema),
                timeout=TEMPO_MAXIMO
            )

        except asyncio.TimeoutError:
            duracao = time.perf_counter() - inicio
            print(f"[TEMPO GEMINI - CORTE NOSSO] cortou em {duracao:.2f}s")
            raise GeminiTimeout("Gemini excedeu o tempo limite")

        except Exception as exc:
            duracao = time.perf_counter() - inicio
            print(f"[TEMPO GEMINI - ERRO] falhou em {duracao:.2f}s ({type(exc).__name__})")
            raise

        duracao = time.perf_counter() - inicio
        print(f"[TEMPO GEMINI] {duracao:.2f}s")

        return interaction.output_text

    async def _chamar_gemini(self, prompt, response_schema):
        return await self.client.aio.interactions.create(
            model="gemini-3.6-flash",
            input=prompt,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": response_schema
            },
            generation_config={
                "thinking_config": {
                    "thinking_level": "low"
                }
            },
            timeout=TEMPO_MAXIMO
        )

    def _build_prompt(self, context: dict):
        return f"""Você é um simulador de API REST. Sua tarefa é preencher o JSON de resposta.

Contexto da requisição:

{context}

Regras:
- Preencha os campos exigidos pelo response_schema com valores plausíveis.
- Use os dados de request_body e session_state onde fizerem sentido, para manter coerência entre as requisições.
- Os nomes dos campos e os valores técnicos (como status) devem seguir a convenção dos schemas. As descrições (summary) servem apenas como contexto e não definem o idioma dos valores.
- Não explique. Não raciocine em texto. Retorne somente o JSON da resposta."""
