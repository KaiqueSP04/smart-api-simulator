from typing import Any


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
            return isinstance(payload, str)

        if schema_type == "integer":
            return isinstance(payload, int) and not isinstance(payload, bool)

        if schema_type == "number":
            return isinstance(payload, (int, float)) and not isinstance(payload, bool)

        if schema_type == "boolean":
            return isinstance(payload, bool)

        return True

    def validate_object(self, payload: Any, schema: dict) -> bool:
        if not isinstance(payload, dict):
            return False

        properties = schema.get("properties", {})
        required = schema.get("required", [])

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

        item_schema = schema.get("items")

        if item_schema:
            for item in payload:
                if not self.validate(item, item_schema):
                    return False

        return True