from app.adapters.http_api import create_http_app
from app.adapters.openapi_parser import get_endpoints, parse_openapi


def test_swagger_request_examples_include_every_schema_field():
    contract = parse_openapi("contracts/test-api.yaml")
    endpoints = get_endpoints(contract)
    app = create_http_app(endpoints, engine=object(), lifespan=None)
    schema = app.openapi()

    create_order = schema["paths"]["/orders"]["post"]
    request_body = create_order["requestBody"]["content"]["application/json"]
    assert create_order["summary"] == "Cria um pedido"
    assert request_body["schema"]["required"] == ["customer_name", "total"]
    assert set(request_body["schema"]["properties"]) == {
        "customer_name",
        "total",
    }
    assert request_body["examples"]["pedido_completo"]["value"] == {
        "customer_name": "Maria Silva",
        "total": 249.90,
    }

    create_payment = schema["paths"]["/payments"]["post"]
    payment_body = create_payment["requestBody"]["content"]["application/json"]
    payment_fields = set(payment_body["schema"]["properties"])
    payment_example = payment_body["examples"]["pagamento_completo"]["value"]
    assert payment_fields == {"order_id", "amount", "method"}
    assert set(payment_example) == payment_fields

    get_order = schema["paths"]["/orders/{id}"]["get"]
    order_id = next(
        parameter
        for parameter in get_order["parameters"]
        if parameter["name"] == "id"
    )
    assert order_id["schema"]["type"] == "integer"
    assert order_id["examples"]["example"]["value"] == 101
    assert "POST /orders" in order_id["description"]


def test_swagger_documents_actual_envelope_and_creation_status():
    endpoints = get_endpoints(parse_openapi("contracts/test-api.yaml"))
    app = create_http_app(endpoints, engine=object(), lifespan=None)
    schema = app.openapi()

    operation = schema["paths"]["/orders"]["post"]
    assert operation["tags"] == ["Pedidos"]
    assert "200" not in operation["responses"]
    response = operation["responses"]["201"]["content"]["application/json"]["schema"]
    assert response["properties"]["data"]["required"] == [
        "id", "customer_name", "total", "status",
    ]
    assert set(response["properties"]) == {
        "status_code", "data", "parameters", "request_body", "context",
    }
    error = operation["responses"]["404"]["content"]["application/json"]
    assert error["example"]["status_code"] == 404
    assert error["schema"]["required"] == ["status_code", "message"]
    assert "data.id" in schema["info"]["description"]
    assert "30 minutos" in schema["info"]["description"]
    assert schema["paths"]["/payments"]["post"]["tags"] == ["Pagamentos"]
