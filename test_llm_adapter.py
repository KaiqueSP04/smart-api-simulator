import asyncio

from app.adapters.gemini import GeminiResponseGenerator


async def main():
    adapter = GeminiResponseGenerator()

    context = {
        "endpoint": {
            "method": "GET",
            "path": "/products",
            "summary": "Lista produtos"
        },
        "parameters": {
            "category": "electronics"
        },
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
        "session_state": None
    }

    response = await adapter.generate(context)

    print("Resposta do Gemini:")
    print(response)


asyncio.run(main())