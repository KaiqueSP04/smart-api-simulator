from .models import Endpoint


class ContextBuilder:

    def __init__(self, contract: dict):
        self.contract = contract

    def build(self, endpoint: Endpoint, parameters=None, request_body=None):
        return {
            "endpoint": {
                "method": endpoint.method,
                "path": endpoint.path,
                "summary": endpoint.summary,
            },
            "parameters": parameters or {},
            "request_body": request_body,
            "request_schema": self._get_request_schema(endpoint),
            "response_schema": self._get_response_schema(endpoint),
        }

    def _get_request_schema(self, endpoint: Endpoint):
        if not endpoint.request_body:
            return None

        content = endpoint.request_body.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema")

        return self._resolve_schema(schema)

    def _get_response_schema(self, endpoint: Endpoint):
        if not endpoint.responses:
            return None

        status_code = next(iter(endpoint.responses))
        response = endpoint.responses.get(str(status_code))

        if not response:
            return None

        content = response.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema")

        return self._resolve_schema(schema)

    def _resolve_schema(self, schema):
        if not isinstance(schema, dict):
            return schema

        if "$ref" not in schema:
            return schema

        ref = schema["$ref"]

        if not ref.startswith("#/"):
            return schema

        current = self.contract

        for part in ref[2:].split("/"):
            current = current.get(part)

            if current is None:
                return schema

        return self._resolve_schema(current)