from app.adapters.http_api import create_http_app
from app.adapters.openapi_parser import get_endpoints, parse_openapi


def test_swagger_request_examples_include_every_schema_field():
    contract = parse_openapi("contracts/test-api.yaml")
    endpoints = get_endpoints(contract)
    app = create_http_app(endpoints, engine=object(), lifespan=None)
    schema = app.openapi()

    create_order = schema["paths"]["/pedidos"]["post"]
    request_body = create_order["requestBody"]["content"]["application/json"]
    assert create_order["summary"] == "Cria um pedido"
    assert request_body["schema"]["required"] == ["nome_cliente", "itens"]
    assert set(request_body["schema"]["properties"]) == {
        "nome_cliente",
        "itens",
    }
    assert request_body["examples"]["pedido_completo"]["value"] == {
        "nome_cliente": "Maria Silva",
        "itens": [{"nome_produto": "Mouse sem fio", "quantidade": 2, "preco_unitario": 124.95}],
    }

    create_payment = schema["paths"]["/pagamentos"]["post"]
    payment_body = create_payment["requestBody"]["content"]["application/json"]
    payment_fields = set(payment_body["schema"]["properties"])
    payment_example = payment_body["examples"]["pagamento_completo"]["value"]
    assert payment_fields == {"pedido_id", "metodo"}
    assert set(payment_example) == payment_fields

    get_order = schema["paths"]["/pedidos/{id}"]["get"]
    pedido_id = next(
        parameter
        for parameter in get_order["parameters"]
        if parameter["name"] == "id"
    )
    assert pedido_id["schema"]["type"] == "integer"
    assert pedido_id["examples"]["example"]["value"] == 101
    assert "POST /pedidos" in pedido_id["description"]


def test_swagger_documents_actual_envelope_and_creation_status():
    endpoints = get_endpoints(parse_openapi("contracts/test-api.yaml"))
    app = create_http_app(endpoints, engine=object(), lifespan=None)
    schema = app.openapi()

    operation = schema["paths"]["/pedidos"]["post"]
    assert operation["tags"] == ["Pedidos"]
    assert "200" not in operation["responses"]
    response = operation["responses"]["201"]["content"]["application/json"]["schema"]
    assert response["properties"]["dados"]["required"] == [
        "id", "nome_cliente", "itens", "total", "situacao",
    ]
    assert set(response["properties"]) == {
        "codigo_status", "dados", "diagnostico",
    }
    error = operation["responses"]["404"]["content"]["application/json"]
    assert error["example"]["codigo_status"] == 404
    assert error["schema"]["required"] == ["codigo_status", "mensagem"]
    assert "dados.id" in schema["info"]["description"]
    assert "30 minutos" in schema["info"]["description"]
    assert schema["paths"]["/pagamentos"]["post"]["tags"] == ["Pagamentos"]
    assert response["required"] == ["codigo_status", "dados"]
    debug = next(p for p in operation["parameters"] if p["name"] == "X-Debug")
    assert debug["schema"]["default"] is False
    assert debug["schema"]["type"] == "boolean"
    assert "/docs" not in schema["paths"]
