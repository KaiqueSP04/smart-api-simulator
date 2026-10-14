import time
from typing import Any

from ..models import Endpoint
from .context_builder import ContextBuilder
from .ports import RequestLog, RequestPolicy
from .response_generation import ResponseGenerationService
from .session_resources import SessionResources
from .resource_rules import get_resource_type, is_creation, uses_resource_id
from .results import FailureKind, SimulationContext, SimulationResult
from .validator import PayloadValidator


class SimulationEngine:
    def __init__(
        self,
        endpoints: list[Endpoint],
        context_builder: ContextBuilder,
        session_resources: SessionResources,
        response_generation: ResponseGenerationService,
        validator: PayloadValidator,
        request_logger: RequestLog | None = None,
        request_policy: RequestPolicy | None = None,
    ):
        self.endpoints = {
            (endpoint.path, endpoint.method.upper()): endpoint
            for endpoint in endpoints
        }
        self.context_builder = context_builder
        self.session_resources = session_resources
        self.response_generation = response_generation
        self.validator = validator
        self.request_logger = request_logger
        self.request_policy = request_policy

    def find_endpoint(self, path: str, method: str) -> Endpoint | None:
        return self.endpoints.get((path, method.upper()))

    async def simulate(
        self,
        path: str,
        method: str,
        parameters: dict[str, Any] | None = None,
        request_body: Any = None,
        session_id: str | None = None,
    ) -> SimulationResult:
        started_at = time.perf_counter()
        result = await self._run(
            path,
            method,
            parameters,
            request_body,
            session_id,
        )

        if self.request_logger is not None:
            latency_ms = (time.perf_counter() - started_at) * 1000
            await self.request_logger.log(
                path=path,
                method=method,
                result=result,
                latency_ms=round(latency_ms, 2),
                session_id=session_id,
            )

        return result

    async def _run(
        self,
        path: str,
        method: str,
        parameters: dict[str, Any] | None = None,
        request_body: Any = None,
        session_id: str | None = None,
    ) -> SimulationResult:
        endpoint = self.find_endpoint(path, method)
        if endpoint is None:
            return SimulationResult.failed(
                FailureKind.NOT_FOUND,
                "Endpoint não encontrado",
            )

        parameters = parameters or {}
        session_state = await self.session_resources.get_state(session_id)
        context = self.context_builder.build(
            endpoint=endpoint,
            parameters=parameters,
            request_body=request_body,
            session_state=session_state,
        )

        request_schema = context.get("request_schema")
        if request_schema:
            if request_body is None:
                return SimulationResult.failed(
                    FailureKind.INVALID_REQUEST,
                    "Corpo da requisição obrigatório",
                )
            if not self.validator.validate(request_body, request_schema):
                return SimulationResult.failed(
                    FailureKind.INVALID_REQUEST,
                    "Dados inválidos. Confira os campos obrigatórios e os limites descritos na documentação.",
                )

        if self.request_policy is not None:
            failure = self.request_policy.validate(context, session_id)
            if failure is not None:
                return SimulationResult(failure=failure)

        method_upper = method.upper()
        resource_type = get_resource_type(path)
        entity_id = parameters.get("id")

        if (
            session_id
            and method_upper in {"GET", "POST"}
            and uses_resource_id(path)
            and not await self.session_resources.contains(
                session_id, resource_type, entity_id
            )
        ):
            return SimulationResult.failed(
                FailureKind.NOT_FOUND,
                "Recurso não encontrado na sessão",
            )

        response_schema = context.get("response_schema")
        response_key = next(iter(endpoint.responses))

        if session_id and method_upper == "GET" and "{id}" in path:
            stored_data = await self.session_resources.get_resource(
                session_id,
                resource_type,
                entity_id,
            )
            if stored_data is None:
                return SimulationResult.failed(
                    FailureKind.NOT_FOUND,
                    "Recurso não encontrado na sessão",
                )
            if response_schema and not self.validator.validate(
                stored_data, response_schema
            ):
                return SimulationResult.failed(
                    FailureKind.INVALID_STATE,
                    (
                        "Estado armazenado incompatível com o schema da resposta"
                    ),
                )
            return self._success_result(
                response_key,
                stored_data,
                parameters,
                request_body,
                context,
            )

        generation = await self.response_generation.generate(
            context=context,
            endpoint=endpoint,
            parameters=parameters,
            session_id=session_id,
        )
        if generation.error is not None:
            return SimulationResult(failure=generation.error)

        response_data = generation.data
        creating_resource = is_creation(endpoint)
        if session_id and method_upper != "GET":
            stored_data = await self.session_resources.save_response(
                session_id,
                resource_type,
                response_data,
            )
            if not creating_resource and stored_data is not None:
                response_data = stored_data

        return self._success_result(
            response_key,
            response_data,
            parameters,
            request_body,
            context,
        )

    @staticmethod
    def _success_result(
        response_key: str,
        response_data: Any,
        parameters: dict[str, Any],
        request_body: Any,
        context: SimulationContext,
    ) -> SimulationResult:
        return SimulationResult(
            response_key=response_key,
            data=response_data,
            parameters=parameters,
            request_body=request_body,
            context=context,
        )
