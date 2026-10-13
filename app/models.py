from pydantic import BaseModel, Field
from typing import Any


class Parameter(BaseModel):
    name: str
    location: str
    required: bool = False
    description: str | None = None
    example: Any = None
    schema_data: dict[str, Any] = Field(default_factory=dict, alias="schema")

class Endpoint(BaseModel):
    path: str
    method: str
    summary: str | None = None
    description: str | None = None
    parameters: list[Parameter] = Field(default_factory=list)
    request_body: dict[str, Any] | None = None
    responses: dict[str, Any] = Field(default_factory=dict)