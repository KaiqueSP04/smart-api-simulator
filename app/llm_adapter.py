import os

from dotenv import load_dotenv
from google import genai


load_dotenv()


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

        interaction = await self.client.aio.interactions.create(
            model="gemini-3.6-flash",
            input=prompt,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": response_schema
            },
            timeout=10
        )

        return interaction.output_text

    def _build_prompt(self, context: dict):
        return f"""
Você é um simulador de API REST.

Gere uma resposta para a requisição com base no contexto abaixo.

Contexto:

{context}

Gere uma resposta coerente com os dados da requisição,
com o estado da sessão e com o contexto do endpoint.
"""