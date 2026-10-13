import logging
from datetime import datetime, timezone

from ..application.results import SimulationResult
from .http_results import to_http_response


logger = logging.getLogger(__name__)

class RequestLogger:
    """Registra o histórico de requisições na coleção 'requests'.

    Serve de base para os indicadores de avaliação (endpoints, latência,
    status, uso de fallback). A gravação é best-effort: uma falha ao
    registrar o log nunca deve interromper a resposta ao cliente.
    """

    def __init__(self, db):
        self.db = db
        self.requests = db["requests"]

    async def log(
        self,
        path: str,
        method: str,
        result: SimulationResult,
        latency_ms: float | None = None,
        session_id: str | None = None
    ):
        status_code, _ = to_http_response(result)
        document = {
            "endpoint": path,
            "method": method,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "valid": result.failure is None,
            "fallback": False,
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc)
        }

        try:
            await self.requests.insert_one(document)
        except Exception:
            # Log é best-effort: não derruba a requisição se falhar.
            logger.exception("Não foi possível registrar a requisição")
