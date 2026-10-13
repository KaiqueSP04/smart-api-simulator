"""Resource conventions shared by the simulation use cases."""

from ..models import Endpoint


def get_resource_type(path: str) -> str | None:
    segments = [part for part in path.split("/") if part and not part.startswith("{")]
    return segments[0] if segments else None


def is_creation(endpoint: Endpoint) -> bool:
    resource_type = get_resource_type(endpoint.path)
    return (
        resource_type is not None
        and endpoint.method.upper() == "POST"
        and endpoint.path.rstrip("/") == f"/{resource_type}"
    )


def uses_resource_id(path: str) -> bool:
    parts = [part for part in path.split("/") if part]
    return len(parts) >= 2 and parts[1] == "{id}"
