from .models import Endpoint
from .validator import PayloadValidator


class SimulationEngine:
    def __init__(self, endpoints: list[Endpoint]):
        self.endpoints = endpoints
        self.validator = PayloadValidator()

    def find_endpoint(self, path: str, method: str):
        for endpoint in self.endpoints:
            if endpoint.path == path and endpoint.method.upper() == method.upper():
                return endpoint

        return None

    def get_response_schema(self, endpoint: Endpoint):
        if not endpoint.responses:
            return None

        response = endpoint.responses.get(
            str(next(iter(endpoint.responses)))
        )

        if not response:
            return None

        content = response.get("content", {})
        json_content = content.get("application/json", {})

        return json_content.get("schema")

    def get_request_body_schema(self, endpoint: Endpoint):
        if not endpoint.request_body:
            return None

        content = endpoint.request_body.get("content", {})
        json_content = content.get("application/json", {})

        return json_content.get("schema")

    def generate_response(self, endpoint: Endpoint, parameters=None):
        schema = self.get_response_schema(endpoint)

        if not schema:
            return None

        return self.generate_from_schema(schema, parameters or {})

    def generate_from_schema(self, schema, parameters):
        schema_type = schema.get("type")

        if schema_type == "object":
            result = {}

            for name, property_schema in schema.get("properties", {}).items():
                if name in parameters:
                    result[name] = self.convert_parameter_value(
                        parameters[name],
                        property_schema
                    )
                else:
                    result[name] = self.generate_from_schema(
                        property_schema,
                        parameters
                    )

            return result

        if schema_type == "array":
            item_schema = schema.get("items", {})

            return [
                self.generate_from_schema(item_schema, parameters)
            ]

        if schema_type == "string":
            return "exemplo"

        if schema_type == "integer":
            return 1

        if schema_type == "number":
            return 10.0

        if schema_type == "boolean":
            return True

        return None

    def convert_parameter_value(self, value, schema):
        schema_type = schema.get("type")

        if schema_type == "integer":
            return int(value)

        if schema_type == "number":
            return float(value)

        if schema_type == "boolean":
            return str(value).lower() == "true"

        return str(value)

    def simulate(
        self,
        path: str,
        method: str,
        parameters=None,
        request_body=None
    ):
        endpoint = self.find_endpoint(path, method)

        if endpoint is None:
            return {
                "status_code": 404,
                "message": "Endpoint não encontrado"
            }

        request_schema = self.get_request_body_schema(endpoint)

        if request_schema:
            if request_body is None:
                return {
                    "status_code": 400,
                    "message": "Request body obrigatório"
                }

            is_valid = self.validator.validate(
                request_body,
                request_schema
            )

            if not is_valid:
                return {
                    "status_code": 400,
                    "message": "Request body não corresponde ao schema"
                }

        status_code = int(next(iter(endpoint.responses)))

        response_data = self.generate_response(
            endpoint,
            parameters
        )

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
            "data": response_data,
            "parameters": parameters or {},
            "request_body": request_body
        }