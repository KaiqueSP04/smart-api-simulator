from datetime import datetime, timezone

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
        status_code: int,
        latency_ms: float | None = None,
        valid: bool | None = None,
        fallback: bool = False,
        session_id: str | None = None
    ):
        document = {
            "endpoint": path,
            "method": method,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "valid": valid,
            "fallback": fallback,
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc)
        }

        try:
            await self.requests.insert_one(document)
        except Exception:
            # Log é best-effort: não derruba a requisição se falhar.
            pass
