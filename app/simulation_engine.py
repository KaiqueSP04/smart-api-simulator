from .models import Endpoint
from .validator import PayloadValidator


class SimulationEngine:
    def __init__(self, endpoints: list[Endpoint]):
        self.endpoints = endpoints
        self.validator = PayloadValidator()

    def find_endpoint(self, path: str, method: str):
        method = method.upper()

        for endpoint in self.endpoints:
            if endpoint.path == path and endpoint.method == method:
                return endpoint

        return None

    def simulate(self, path: str, method: str):
        endpoint = self.find_endpoint(path, method)

        if endpoint is None:
            return {
                "status_code": 404,
                "message": "Endpoint não encontrado"
            }

        status_code = int(next(iter(endpoint.responses)))

        response_data = self.generate_response(endpoint)

        response_schema = self.get_response_schema(endpoint)

        if response_schema:
            is_valid = self.validator.validate(
                response_data,
                response_schema
            )

            if not is_valid:
                return {
                    "status_code": 500,
                    "message": "Payload gerado não corresponde ao schema"
                }

        return {
            "status_code": status_code,
            "data": response_data
        }

    def generate_response(self, endpoint: Endpoint):
        response = next(iter(endpoint.responses.values()))

        content = response.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema", {})

        return self.generate_from_schema(schema)

    def get_response_schema(self, endpoint: Endpoint):
        response = next(iter(endpoint.responses.values()))

        content = response.get("content", {})
        json_content = content.get("application/json", {})

        return json_content.get("schema")

    def generate_from_schema(self, schema: dict):
        schema_type = schema.get("type")

        if schema_type == "object":
            result = {}

            for name, property_schema in schema.get("properties", {}).items():
                result[name] = self.generate_from_schema(property_schema)

            return result

        if schema_type == "array":
            item_schema = schema.get("items", {})

            return [
                self.generate_from_schema(item_schema)
            ]

        if schema_type == "integer":
            return 1

        if schema_type == "number":
            return 10.0

        if schema_type == "string":
            return "exemplo"

        if schema_type == "boolean":
            return True

        return None