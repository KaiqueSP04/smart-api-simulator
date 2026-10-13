import yaml

from ..models import Endpoint, Parameter


def parse_openapi(file_path: str):
    with open(file_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def resolve_schema(schema, contract):
    if not isinstance(schema, dict):
        return schema

    ref = schema.get("$ref")

    if not ref:
        return schema

    if not ref.startswith("#/"):
        return schema

    current = contract

    for part in ref[2:].split("/"):
        current = current.get(part)

        if current is None:
            return schema

    return current


def resolve_refs(data, contract):
    if isinstance(data, dict):
        if "$ref" in data:
            return resolve_schema(data, contract)

        return {
            key: resolve_refs(value, contract)
            for key, value in data.items()
        }

    if isinstance(data, list):
        return [
            resolve_refs(item, contract)
            for item in data
        ]

    return data


def get_endpoints(contract):
    endpoints = []

    for path, methods in contract.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue

        for method, details in methods.items():
            if method.lower() not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "options",
                "head"
            }:
                continue

            parameters = []

            for parameter in details.get("parameters", []):
                parameters.append(
                    Parameter(
                        name=parameter.get("name"),
                        location=parameter.get("in"),
                        required=parameter.get("required", False),
                        description=parameter.get("description"),
                        example=parameter.get(
                            "example",
                            parameter.get("schema", {}).get("example"),
                        ),
                        schema=resolve_refs(
                            parameter.get("schema", {}),
                            contract
                        )
                    )
                )

            request_body = resolve_refs(
                details.get("requestBody"),
                contract
            )

            responses = resolve_refs(
                details.get("responses", {}),
                contract
            )

            endpoint = Endpoint(
                path=path,
                method=method.upper(),
                summary=details.get("summary"),
                description=details.get("description"),
                parameters=parameters,
                request_body=request_body,
                responses=responses
            )

            endpoints.append(endpoint)

    return endpoints