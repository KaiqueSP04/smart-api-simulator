from typing import Protocol

from .results import SimulationContext, SimulationResult


class SessionStore(Protocol):
    async def initialize(self) -> None: ...

    async def save_session(self, session_id: str, state: dict) -> None: ...

    async def get_session(self, session_id: str) -> dict | None: ...

    async def delete_session(self, session_id: str) -> None: ...


class ResponseGenerator(Protocol):
    async def generate(self, context: SimulationContext) -> str: ...


class RequestLog(Protocol):
    async def log(
        self,
        path: str,
        method: str,
        result: SimulationResult,
        latency_ms: float | None = None,
        session_id: str | None = None,
    ) -> None: ...


class GenerationTimeout(Exception):
    """The configured response generator exceeded its time limit."""


class GenerationRateLimited(Exception):
    """The configured response generator rejected a request due to quota."""
