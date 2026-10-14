"""Map application outcomes to the public HTTP response envelope."""

from ..application.results import FailureKind, SimulationResult


FAILURE_STATUS_CODES = {
    FailureKind.NOT_FOUND: 404,
    FailureKind.INVALID_REQUEST: 400,
    FailureKind.INVALID_STATE: 503,
    FailureKind.GENERATION_TIMEOUT: 503,
    FailureKind.GENERATION_RATE_LIMITED: 429,
    FailureKind.GENERATION_UNAVAILABLE: 503,
    FailureKind.INVALID_GENERATION: 503,
}


def to_http_response(result: SimulationResult, debug: bool = False) -> tuple[int, dict]:
    if result.failure is not None:
        status = FAILURE_STATUS_CODES[result.failure.kind]
        return status, {"codigo_status": status, "mensagem": result.failure.message}

    # The response key comes from the OpenAPI contract, not an application error.
    status = int(result.response_key or "200")
    content = {"codigo_status": status, "dados": result.data}
    if debug:
        content["diagnostico"] = {
            "parametros": result.parameters or {},
            "corpo_requisicao": result.request_body,
            "contexto": result.context,
        }
    return status, content
