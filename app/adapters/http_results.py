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


def to_http_response(result: SimulationResult) -> tuple[int, dict]:
    if result.failure is not None:
        status = FAILURE_STATUS_CODES[result.failure.kind]
        return status, {"status_code": status, "message": result.failure.message}

    # The response key comes from the OpenAPI contract, not an application error.
    status = int(result.response_key or "200")
    return status, {
        "status_code": status,
        "data": result.data,
        "parameters": result.parameters or {},
        "request_body": result.request_body,
        "context": result.context,
    }
