import asyncio
import os
import time

from dotenv import load_dotenv
from google import genai

from app.llm_adapter import LLMAdapter


load_dotenv()


client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

adapter = LLMAdapter()


GET_CONTEXT = {
    "endpoint": {
        "method": "GET",
        "path": "/products",
        "summary": "Lista produtos",
    },
    "parameters": {},
    "request_body": None,
    "request_schema": None,
    "response_schema": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "integer"
                },
                "name": {
                    "type": "string"
                },
                "price": {
                    "type": "number"
                }
            }
        }
    },
    "session_state": None,
}


POST_CONTEXT = {
    "endpoint": {
        "method": "POST",
        "path": "/products",
        "summary": "Cria um produto",
    },
    "parameters": {},
    "request_body": {
        "name": "Mouse Gamer",
        "price": 150
    },
    "request_schema": {
        "type": "object",
        "required": [
            "name",
            "price"
        ],
        "properties": {
            "name": {
                "type": "string"
            },
            "price": {
                "type": "number"
            }
        }
    },
    "response_schema": {
        "type": "object",
        "required": [
            "id",
            "name",
            "price"
        ],
        "properties": {
            "id": {
                "type": "integer"
            },
            "name": {
                "type": "string"
            },
            "price": {
                "type": "number"
            }
        }
    },
    "session_state": None,
}


async def run_test(name, context):
    print()
    print("=" * 60)
    print(name)
    print("=" * 60)

    prompt = adapter._build_prompt(context)

    start = time.perf_counter()

    interaction = await client.aio.interactions.create(
        model="gemini-3.6-flash",
        input=prompt,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": context["response_schema"]
        },
        timeout=180
    )

    elapsed = time.perf_counter() - start

    usage = interaction.usage

    print(f"Tempo total: {elapsed:.2f} segundos")

    print(f"Input tokens: {usage.total_input_tokens}")
    print(f"Output tokens: {usage.total_output_tokens}")
    print(f"Thought tokens: {usage.total_thought_tokens}")
    print(f"Total tokens: {usage.total_tokens}")

    print()
    print("Resposta:")
    print(interaction.output_text)


async def main():
    print("Iniciando diagnóstico de latência...")
    print("O timeout de 180s é SOMENTE para este diagnóstico.")

    await run_test(
        "TESTE 1 — POST /products",
        POST_CONTEXT
    )

    await run_test(
        "TESTE 2 — GET /products",
        GET_CONTEXT
    )


if __name__ == "__main__":
    asyncio.run(main())