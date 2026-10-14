"""Payment values are derived from the order in the current session."""

from typing import Any

from .order_calculation import OrderCalculation
from .results import FailureKind, SimulationContext, SimulationFailure
from .validator import PayloadValidator


class CommerceRules:
    def validate(self, context: SimulationContext, session_id: str | None) -> SimulationFailure | None:
        if not self._is_payment(context):
            return None
        if not session_id:
            return SimulationFailure(FailureKind.INVALID_REQUEST, "Informe X-Session-ID da sessão em que o pedido foi criado.")
        order = self._order(context)
        if order is None:
            return SimulationFailure(FailureKind.NOT_FOUND, "Pedido não encontrado nesta sessão.")
        if order.get("situacao") != "criado":
            return SimulationFailure(FailureKind.INVALID_REQUEST, "O pedido precisa estar na situação criado para receber pagamento.")
        if not PayloadValidator().validate(order.get("total"), {
            "type": "number", "minimum": 0, "exclusiveMinimum": True, "multipleOf": 0.01,
        }):
            return SimulationFailure(FailureKind.INVALID_STATE, "O pedido armazenado não possui um total válido.")
        return None

    def normalize(self, context: SimulationContext, data: Any) -> Any:
        if not self._is_payment(context) or not isinstance(data, dict):
            return OrderCalculation().normalize(context, data)
        body = context["request_body"]
        order = self._order(context)
        return {
            "id": data.get("id"),
            "pedido_id": body["pedido_id"],
            "valor": order["total"],
            "metodo": body["metodo"],
            "situacao": "pendente",
        }

    @staticmethod
    def _is_payment(context: SimulationContext) -> bool:
        return context["endpoint"]["path"] == "/pagamentos" and context["endpoint"]["method"].upper() == "POST"

    @staticmethod
    def _order(context: SimulationContext) -> dict | None:
        orders = (context.get("session_state") or {}).get("pedidos", {})
        if not isinstance(orders, dict):
            return None
        order = orders.get(str(context["request_body"]["pedido_id"]))
        return order if isinstance(order, dict) else None
