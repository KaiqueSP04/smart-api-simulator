"""Documentation of the simulator's HTTP envelope and usage."""

from copy import deepcopy

from ..models import Endpoint


DESCRIPTION = """
Simule pedidos e pagamentos e acompanhe os recursos de uma mesma sessão.

### Experimente um fluxo completo
1. Abra **POST /pedidos**, clique em **Try it out** e preencha cliente e itens.
2. Preencha **X-Session-ID** com `checkout-demo-001` e clique em **Execute**.
3. Confira **dados.total**, calculado automaticamente, e copie **dados.id**.
4. Em **GET /pedidos/{id}**, informe esse identificador e repita o mesmo cabeçalho.
5. Em **POST /pagamentos**, coloque o identificador do pedido em **pedido_id**,
   escolha **metodo** e repita a sessão. O valor vem automaticamente do pedido.
   Copie o novo **dados.id**.
6. Use o ID do pagamento em **POST /pagamentos/{id}/confirmar** e consulte
   **GET /pagamentos/{id}**, sempre com a mesma sessão.

### Preenchimento simples
| Campo | O que informar |
| --- | --- |
| nome_cliente | Nome do cliente |
| itens | Lista dos produtos; adicione um objeto por produto diferente |
| nome_produto | Nome do produto |
| quantidade | Número inteiro de unidades, a partir de 1 |
| preco_unitario | Preço de uma unidade, com ponto decimal e até duas casas: 124.95 |

Não informe **total** na criação do pedido: o sistema soma quantidade × preço
de cada item. Dois pedidos separados exigem duas chamadas de criação.

### Sessões e respostas
- **X-Session-ID** é opcional. Use-o para manter os recursos entre chamadas.
  Sem ele, as chamadas não compartilham estado persistente.
- Repita o valor em cada requisição. Os exemplos de IDs são ilustrativos:
  substitua-os pelos identificadores retornados na sua sessão.
- A sessão expira após 30 minutos sem gravação de estado.
- O recurso retornado fica em **dados**. **codigo_status** indica o resultado.
- **X-Debug** fica em **false** por padrão. Selecione **true** para incluir
  **diagnostico**, com parâmetros, corpo enviado e contexto técnico da simulação.
- Em caso de erro, leia **mensagem**. Um **404** com sessão pode indicar que o
  recurso não foi criado nela ou que a sessão expirou.
"""


def resource_tag(endpoint: Endpoint) -> str:
    resource = endpoint.path.strip("/").split("/")[0]
    return {"pedidos": "Pedidos", "pagamentos": "Pagamentos"}.get(
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
            "required": ["codigo_status", "dados"],
            "properties": {
                "codigo_status": {"type": "integer", "example": int(key)},
                "dados": payload_schema,
                "diagnostico": {
                    "type": "object",
                    "description": "Incluído somente com X-Debug: true. Não faz parte dos dados do pedido.",
                    "properties": {
                        "parametros": {"type": "object", "additionalProperties": True},
                        "corpo_requisicao": {"anyOf": [{"type": "object"}, {"type": "null"}]},
                        "contexto": {"type": "object", "additionalProperties": True},
                    },
                },
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
            "description": response.get("description", "Operação realizada") + ". O recurso está em dados.",
            "content": {"application/json": content},
        }

    errors = {
        400: ("Dados incompatíveis com o contrato", "Dados inválidos. Confira os campos obrigatórios e os limites descritos na documentação."),
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
                    "required": ["codigo_status", "mensagem"],
                    "properties": {
                        "codigo_status": {"type": "integer"},
                        "mensagem": {"type": "string"},
                    },
                },
                "example": {"codigo_status": status, "mensagem": message},
            }},
        }
    return responses


def _example(status: int, payload) -> dict:
    return {
        "codigo_status": status,
        "dados": payload,
    }
