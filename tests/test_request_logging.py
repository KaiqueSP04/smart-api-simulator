from unittest.mock import AsyncMock

import pytest

from app.adapters.mongodb_request_logger import RequestLogger
from app.application.results import FailureKind, SimulationResult


@pytest.mark.asyncio
@pytest.mark.parametrize("result, status, valid", [
    (SimulationResult(data={"id": 101}, response_key="201"), 201, True),
    (SimulationResult.failed(FailureKind.GENERATION_RATE_LIMITED, "Limite excedido"), 429, False),
])
async def test_logger_preserves_history_format(result, status, valid):
    collection = AsyncMock()
    logger = RequestLogger({"requests": collection})
    await logger.log("/orders", "POST", result, latency_ms=12.5, session_id="demo")
    document = collection.insert_one.call_args.args[0]
    assert document["status_code"] == status
    assert document["valid"] is valid
    assert document["fallback"] is False
    assert document["session_id"] == "demo"
    assert document["latency_ms"] == 12.5


@pytest.mark.asyncio
async def test_logging_failure_does_not_interrupt_simulation():
    collection = AsyncMock()
    collection.insert_one.side_effect = RuntimeError("Storage unavailable")
    logger = RequestLogger({"requests": collection})
    await logger.log("/orders", "POST", SimulationResult(data={}, response_key="201"))
