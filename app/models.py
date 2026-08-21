from pydantic import BaseModel, Field
from typing import Any


class Endpoint(BaseModel):
    path: str
    method: str
    summary: str | None = None
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    request_body: dict[str, Any] | None = None
    responses: dict[str, Any] = Field(default_factory=dict)