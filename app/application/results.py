"""Transport-independent results of a simulation."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, TypedDict


class EndpointContext(TypedDict):
    method: str
    path: str
    summary: str | None


class SimulationContext(TypedDict):
    endpoint: EndpointContext
    parameters: dict[str, Any]
    request_body: Any
    request_schema: dict | None
    response_schema: dict | None
    session_state: dict | None


class FailureKind(str, Enum):
    NOT_FOUND = "not_found"
    INVALID_REQUEST = "invalid_request"
    INVALID_STATE = "invalid_state"
    GENERATION_TIMEOUT = "generation_timeout"
    GENERATION_RATE_LIMITED = "generation_rate_limited"
    GENERATION_UNAVAILABLE = "generation_unavailable"
    INVALID_GENERATION = "invalid_generation"


@dataclass(frozen=True)
class SimulationFailure:
    kind: FailureKind
    message: str


@dataclass(frozen=True)
class SimulationResult:
    data: Any = None
    failure: SimulationFailure | None = None
    response_key: str | None = None
    parameters: dict[str, Any] | None = None
    request_body: Any = None
    context: SimulationContext | None = None

    @classmethod
    def failed(cls, kind: FailureKind, message: str) -> "SimulationResult":
        return cls(failure=SimulationFailure(kind, message))
