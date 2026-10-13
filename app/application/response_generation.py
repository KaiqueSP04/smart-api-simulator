import json
import logging
from dataclasses import dataclass
from typing import Any

from ..models import Endpoint
from .ports import (
    GenerationRateLimited,
    GenerationTimeout,
    ResponseGenerator,
)
from .session_resources import SessionResources
from .resource_rules import get_resource_type, is_creation
from .results import FailureKind, SimulationContext, SimulationFailure
from .validator import PayloadValidator


logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    data: Any = None
    error: SimulationFailure | None = None


class ResponseGenerationService:
    def __init__(
        self,
        response_generator: ResponseGenerator,
        validator: PayloadValidator,
        session_resources: SessionResources,
        attempts: int = 3,
    ):
        self.response_generator = response_generator
        self.validator = validator
        self.session_resources = session_resources
        self.attempts = attempts

    async def generate(
        self,
        context: SimulationContext,
        endpoint: Endpoint,
        parameters: dict,
        session_id: str | None,
    ) -> GenerationResult:
        response_schema = context.get("response_schema")
        resource_type = get_resource_type(endpoint.path)
        creating_resource = is_creation(endpoint)

        for _ in range(self.attempts):
            try:
                response_text = await self.response_generator.generate(context)
            except GenerationTimeout:
                return GenerationResult(error=SimulationFailure(
                    FailureKind.GENERATION_TIMEOUT,
                    "Serviço de geração excedeu o tempo limite",
                ))
            except GenerationRateLimited:
                return GenerationResult(error=SimulationFailure(
                    FailureKind.GENERATION_RATE_LIMITED,
                    "Limite de requisições do serviço de geração excedido",
                ))
            except Exception:
                logger.exception("Falha ao gerar resposta da simulação")
                return GenerationResult(error=SimulationFailure(
                    FailureKind.GENERATION_UNAVAILABLE,
                    "Serviço de geração indisponível",
                ))

            try:
                response_data = json.loads(response_text)
            except json.JSONDecodeError:
                continue

            if response_data is None:
                continue

            if response_schema and not self.validator.validate(
                response_data, response_schema
            ):
                continue

            if "{id}" in endpoint.path and isinstance(response_data, dict):
                requested_id = parameters.get("id")
                returned_id = response_data.get("id")
                if returned_id is None or str(returned_id) != str(requested_id):
                    continue

            if (
                session_id
                and creating_resource
                and isinstance(response_data, dict)
            ):
                entity_id = response_data.get("id")
                if entity_id is None:
                    continue
                if await self.session_resources.contains(
                    session_id, resource_type, entity_id
                ):
                    continue

            return GenerationResult(data=response_data)

        if creating_resource:
            message = (
                "Não foi possível gerar um recurso válido e único após "
                f"{self.attempts} tentativas"
            )
        else:
            message = (
                "Não foi possível gerar uma resposta válida após "
                f"{self.attempts} tentativas"
            )

        return GenerationResult(error=SimulationFailure(
            FailureKind.INVALID_GENERATION, message,
        ))
