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


async def run_test():
    print()
    print("=" * 60)
    print("POST /products")
    print("Thinking level: low")
    print("=" * 60)

    prompt = adapter._build_prompt(POST_CONTEXT)

    start = time.perf_counter()

    interaction = await client.aio.interactions.create(
        model="gemini-3.6-flash",
        input=prompt,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": POST_CONTEXT["response_schema"]
        },
        generation_config={
            "thinking_level": "low"
        },
        timeout=180
    )

    elapsed = time.perf_counter() - start

    usage = interaction.usage

    response_data = interaction.output_text

    print(f"Tempo Gemini:         {elapsed:.2f}s")
    print(f"Input tokens:         {usage.total_input_tokens}")
    print(f"Output tokens:        {usage.total_output_tokens}")
    print(f"Thought tokens:       {usage.total_thought_tokens}")
    print(f"Total tokens:         {usage.total_tokens}")

    print()
    print("Resposta:")
    print(response_data)


async def main():
    print("DIAGNÓSTICO — THINKING LEVEL")
    print()
    print("Nenhuma alteração no código principal.")
    print("Teste único: POST /products com thinking_level=low.")
    print("Timeout de 180s usado somente no diagnóstico.")

    await run_test()


if __name__ == "__main__":
    asyncio.run(main())