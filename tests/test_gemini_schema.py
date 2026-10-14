from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.adapters.gemini import GeminiResponseGenerator
from app.adapters.gemini_schema import to_gemini_schema
from app.adapters.openapi_parser import get_endpoints, parse_openapi
from app.application.validator import PayloadValidator


def order_schema():
    endpoint = next(
        endpoint for endpoint in get_endpoints(parse_openapi("contracts/test-api.yaml"))
        if endpoint.path == "/pedidos" and endpoint.method == "POST"
    )
    return endpoint.responses["201"]["content"]["application/json"]["schema"]


def test_contract_is_preserved_and_limits_are_still_enforced_locally():
    original = order_schema()
    before = deepcopy(original)
    adapted = to_gemini_schema(original)
    assert original == before
    assert "maxItems" not in adapted["properties"]["itens"]
    price = adapted["properties"]["itens"]["items"]["properties"]["preco_unitario"]
    assert price["exclusiveMinimum"] == 0
    assert not isinstance(price["exclusiveMinimum"], bool)
    assert price["multipleOf"] == 0.01

    validator = PayloadValidator()
    item = {"nome_produto": "Mouse", "quantidade": 1, "preco_unitario": 150}
    data = {"id": 1, "nome_cliente": "Maria", "itens": [item] * 11, "total": 1650, "situacao": "criado"}
    assert validator.validate(data, original)
    assert not validator.validate({**data, "itens": [item] * 101}, original)
    assert not validator.validate({**data, "itens": [{**item, "preco_unitario": 0}]}, original)


def test_nested_conversion_preserves_property_names_and_example_values():
    schema = {
        "type": "object",
        "properties": {
            "maxItems": {"type": "integer"},
            "exclusiveMinimum": {"type": "boolean"},
            "value": {"anyOf": [
                {"type": "number", "minimum": 2, "exclusiveMinimum": True},
                {"type": "number", "maximum": 10, "exclusiveMaximum": True},
            ]},
        },
        "example": {"maxItems": 100, "exclusiveMinimum": True},
    }
    adapted = to_gemini_schema(schema)
    assert adapted["properties"]["maxItems"] == {"type": "integer"}
    assert adapted["example"] == schema["example"]
    assert adapted["properties"]["value"]["anyOf"][0]["exclusiveMinimum"] == 2
    assert adapted["properties"]["value"]["anyOf"][1]["exclusiveMaximum"] == 10
    assert "exclusiveMinimum" not in to_gemini_schema({"minimum": 0, "exclusiveMinimum": False})


@pytest.mark.asyncio
async def test_actual_sdk_call_uses_adapted_schema():
    generator = object.__new__(GeminiResponseGenerator)
    create = AsyncMock(return_value=SimpleNamespace(output_text="{}"))
    generator.client = SimpleNamespace(aio=SimpleNamespace(interactions=SimpleNamespace(create=create)))
    schema = order_schema()
    await generator._chamar_gemini("Pedido de teste", schema)
    sent = create.call_args.kwargs["response_format"]["schema"]
    assert "maxItems" not in sent["properties"]["itens"]
    assert schema["properties"]["itens"]["maxItems"] == 100
    assert sent["properties"]["itens"]["items"]["properties"]["preco_unitario"]["exclusiveMinimum"] == 0
