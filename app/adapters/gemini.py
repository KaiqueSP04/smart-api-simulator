import asyncio
import logging
import os
import time

from google import genai
from .gemini_schema import to_gemini_schema
from ..application.results import SimulationContext
from ..application.ports import GenerationRateLimited, GenerationTimeout

# Tempo máximo (em segundos) que esperamos pela resposta do Gemini.
# Serve para o sistema nunca ficar preso indefinidamente numa chamada.
TEMPO_MAXIMO = 180

logger = logging.getLogger(__name__)


class GeminiResponseGenerator:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY não configurada."
            )

        self.client = genai.Client(
            api_key=api_key
        )

    async def generate(self, context: SimulationContext):
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
            logger.warning(
                "Gemini excedeu o timeout da aplicação após %.2f s",
                duracao,
            )
            raise GenerationTimeout("Gemini excedeu o tempo limite") from None

        except Exception as exc:
            duracao = time.perf_counter() - inicio
            logger.exception(
                "Falha na chamada ao Gemini após %.2f s",
                duracao,
            )
            if getattr(exc, "status_code", None) == 429:
                raise GenerationRateLimited(
                    "Limite de requisições do Gemini excedido"
                ) from exc
            if type(exc).__name__ == "APITimeoutError":
                raise GenerationTimeout(
                    "Gemini excedeu o tempo limite"
                ) from exc
            raise

        duracao = time.perf_counter() - inicio
        logger.info("Resposta do Gemini recebida em %.2f s", duracao)

        return interaction.output_text

    async def _chamar_gemini(self, prompt, response_schema):
        return await self.client.aio.interactions.create(
            model="gemini-3.5-flash-lite",
            input=prompt,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": to_gemini_schema(response_schema)
            },
            generation_config={
                "thinking_config": {
                    "thinking_level": "high"
                }
            },
            timeout=TEMPO_MAXIMO
        )

    def _build_prompt(self, context: SimulationContext):
        return f"""Você é um simulador de API REST. Sua tarefa é preencher o JSON de resposta.

Contexto da requisição:

{context}

Regras:
- Preencha os campos exigidos pelo response_schema com valores plausíveis.
- Use os dados de request_body e session_state onde fizerem sentido, para manter coerência entre as requisições.
- Os nomes dos campos e os valores técnicos (como status) devem seguir a convenção dos schemas. As descrições (summary) servem apenas como contexto e não definem o idioma dos valores.
- Não explique. Não raciocine em texto. Retorne somente o JSON da resposta."""
