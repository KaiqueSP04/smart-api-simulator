import yaml
from .models import Endpoint


def parse_openapi(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        contract = yaml.safe_load(file)

    return contract


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

            endpoint = Endpoint(
                path=path,
                method=method.upper(),
                summary=details.get("summary"),
                parameters=details.get("parameters", []),
                request_body=details.get("requestBody"),
                responses=details.get("responses", {})
            )

            endpoints.append(endpoint)

    return endpoints