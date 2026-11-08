"""Documentation of the simulator's HTTP envelope and usage."""

from copy import deepcopy

from ..models import Endpoint


DESCRIPTION = """
Simule as operações definidas no contrato OpenAPI carregado.

### Como utilizar
1. Escolha uma operação e consulte seus parâmetros, schemas e exemplos.
2. Clique em **Try it out**, preencha os dados e execute a chamada.
3. Quando o recurso retornar **dados.id**, utilize esse identificador nas operações relacionadas.

### Sessões e respostas
- **X-Session-ID** é opcional. Repita o mesmo valor para manter recursos entre chamadas.
- O vencimento da sessão é definido para 30 minutos após cada gravação de estado.
- O recurso retornado fica em **dados**; **codigo_status** indica o resultado.
- Quando a proteção estiver habilitada, informe a chave em **Authorize**.
- **X-Debug: true** solicita diagnóstico somente quando permitido pela configuração.
- Em caso de erro, consulte **mensagem** ou os detalhes de validação retornados.
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
                    "description": "Incluído somente com X-Debug: true. Não faz parte dos dados do recurso.",
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
