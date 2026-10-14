"""Deterministic order values, independent of the language model."""

from copy import deepcopy
from decimal import Decimal
from typing import Any

from .results import SimulationContext


class OrderCalculation:
    def normalize(self, context: SimulationContext, data: Any) -> Any:
        endpoint = context["endpoint"]
        if endpoint["path"] != "/pedidos" or endpoint["method"].upper() != "POST":
            return data
        if not isinstance(data, dict):
            return data
        body = context["request_body"]
        total = sum(
            (Decimal(str(item["preco_unitario"])) * item["quantidade"] for item in body["itens"]),
            Decimal("0"),
        )
        # The model supplies an ID; customer, items and amount come from the request.
        return {
            "id": data.get("id"),
            "nome_cliente": body["nome_cliente"],
            "itens": deepcopy(body["itens"]),
            "total": float(total.quantize(Decimal("0.01"))),
            "situacao": "criado",
        }
