"""Validation helpers used by the simulation application."""

from typing import Any
from decimal import Decimal
import math


class PayloadValidator:

    def validate(self, payload: Any, schema: dict) -> bool:
        schema_type = schema.get("type")

        if "enum" in schema and payload not in schema["enum"]:
            return False

        if schema_type == "object":
            return self.validate_object(payload, schema)

        if schema_type == "array":
            return self.validate_array(payload, schema)

        if schema_type == "string":
            return (
                isinstance(payload, str)
                and len(payload.strip()) >= schema.get("minLength", 0)
                and len(payload) <= schema.get("maxLength", float("inf"))
            )

        if schema_type == "integer":
            return self.validate_number(payload, schema, integer=True)

        if schema_type == "number":
            return self.validate_number(payload, schema)

        if schema_type == "boolean":
            return isinstance(payload, bool)

        return True

    def validate_number(self, payload: Any, schema: dict, integer=False) -> bool:
        numeric_type = int if integer else (int, float)
        if not isinstance(payload, numeric_type) or isinstance(payload, bool):
            return False
        try:
            if not math.isfinite(payload):
                return False
        except OverflowError:
            return False
        if "minimum" in schema and payload < schema["minimum"]:
            return False
        if "maximum" in schema and payload > schema["maximum"]:
            return False
        if schema.get("exclusiveMinimum") is True and payload == schema.get("minimum"):
            return False
        if "multipleOf" in schema:
            if Decimal(str(payload)) % Decimal(str(schema["multipleOf"])) != 0:
                return False
        return True

    def validate_object(self, payload: Any, schema: dict) -> bool:
        if not isinstance(payload, dict):
            return False

        properties = schema.get("properties", {})
        required = schema.get("required", [])

        if schema.get("additionalProperties") is False and set(payload) - set(properties):
            return False

        for field in required:
            if field not in payload:
                return False

        for field, field_schema in properties.items():
            if field in payload:
                if not self.validate(payload[field], field_schema):
                    return False

        return True

    def validate_array(self, payload: Any, schema: dict) -> bool:
        if not isinstance(payload, list):
            return False

        if not schema.get("minItems", 0) <= len(payload) <= schema.get("maxItems", float("inf")):
            return False

        item_schema = schema.get("items")

        if item_schema:
            for item in payload:
                if not self.validate(item, item_schema):
                    return False

        return True
