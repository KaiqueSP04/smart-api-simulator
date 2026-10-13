"""Documentation of the simulator's HTTP envelope and usage."""

from copy import deepcopy

from ..models import Endpoint


DESCRIPTION = """
Simule pedidos e pagamentos e acompanhe os recursos de uma mesma sessão.

### Experimente um fluxo completo
1. Abra **POST /orders**, clique em **Try it out** e use o exemplo do corpo.
2. Preencha **X-Session-ID** com `checkout-demo-001` e clique em **Execute**.
3. Copie o identificador de **data.id** da resposta.
4. Em **GET /orders/{id}**, informe esse identificador e repita o mesmo cabeçalho.
5. Em **POST /payments**, coloque o identificador do pedido em **order_id**
   e use a mesma sessão. Copie o novo **data.id**, que identifica o pagamento.
6. Use esse identificador em **POST /payments/{id}/confirm** e consulte
   **GET /payments/{id}**, sempre com a mesma sessão.

### Sessões e respostas
- **X-Session-ID** é opcional. Use-o para manter os recursos entre chamadas.
  Sem ele, as chamadas não compartilham estado persistente.
- Repita o valor em cada requisição. Os exemplos de IDs são ilustrativos:
  substitua-os pelos identificadores retornados na sua sessão.
- A sessão expira após 30 minutos sem gravação de estado.
- O recurso retornado fica em **data**. **status_code** indica o resultado;
  **parameters**, **request_body** e **context** mostram os dados da simulação.
- Em caso de erro, leia **message**. Um **404** com sessão pode indicar que o
  recurso não foi criado nela ou que a sessão expirou.
"""


def resource_tag(endpoint: Endpoint) -> str:
    resource = endpoint.path.strip("/").split("/")[0]
    return {"orders": "Pedidos", "payments": "Pagamentos"}.get(
        resource, resource.replace("-", " ").title()
    )


def documented_responses(endpoint: Endpoint) -> dict:
    responses = {}
    for key, response in endpoint.responses.items():
        # The simulated payload is wrapped in `data` by the HTTP adapter.
        json_content = deepcopy(response.get("content", {}).get("application/json", {}))
        payload_schema = json_content.get("schema", {})
        envelope = {
            "type": "object",
            "required": ["status_code", "data", "parameters", "request_body", "context"],
            "properties": {
                "status_code": {"type": "integer", "example": int(key)},
                "data": payload_schema,
                "parameters": {"type": "object", "additionalProperties": True},
                "request_body": {"anyOf": [{"type": "object"}, {"type": "null"}]},
                "context": {"type": "object", "additionalProperties": True},
            },
        }
        content = {"schema": envelope}
        # Preserve contract examples but display their actual HTTP envelope.
        for example_key in ("example", "examples"):
            if example_key == "example" and example_key in json_content:
                content[example_key] = _example(int(key), json_content[example_key])
            elif example_key in json_content:
                content[example_key] = deepcopy(json_content[example_key])
                for example in content[example_key].values():
                    if "value" in example:
                        example["value"] = _example(int(key), example["value"])
        responses[int(key)] = {
            "description": response.get("description", "Operação realizada") + ". O recurso está em data.",
            "content": {"application/json": content},
        }

    errors = {
        400: ("Dados incompatíveis com o contrato", "Request body não corresponde ao schema"),
        404: ("Recurso não encontrado nesta sessão", "Recurso não encontrado na sessão"),
        429: ("Limite do serviço de geração; tente novamente mais tarde", "Limite de requisições do serviço de geração excedido"),
        503: ("Geração indisponível ou resposta inválida; tente novamente", "Serviço de geração indisponível"),
    }
    for status, (description, message) in errors.items():
        if status in responses:
            continue
        responses[status] = {
            "description": description,
            "content": {"application/json": {
                "schema": {
                    "type": "object",
                    "required": ["status_code", "message"],
                    "properties": {
                        "status_code": {"type": "integer"},
                        "message": {"type": "string"},
                    },
                },
                "example": {"status_code": status, "message": message},
            }},
        }
    return responses


def _example(status: int, payload) -> dict:
    return {
        "status_code": status,
        "data": payload,
        "parameters": {},
        "request_body": None,
        "context": {},
    }
