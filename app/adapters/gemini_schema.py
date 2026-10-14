"""Adapt OpenAPI schemas for the configured Gemini structured-output API.

The original contract remains the authority for application validation.
"""

from copy import deepcopy


def to_gemini_schema(schema: dict) -> dict:
    adapted = deepcopy(schema)
    _adapt(adapted)
    return adapted


def _adapt(schema: dict) -> None:
    # OpenAPI 3.0 uses boolean modifiers; Gemini expects numeric bounds.
    for keyword, bound in (("exclusiveMinimum", "minimum"), ("exclusiveMaximum", "maximum")):
        value = schema.get(keyword)
        if isinstance(value, bool):
            schema.pop(keyword)
            if value and bound in schema:
                schema[keyword] = schema[bound]

    # maxItems=100 was rejected by the configured model. Do not impose a
    # smaller business limit on Gemini; validate the original limit locally.
    schema.pop("maxItems", None)

    # Traverse schema positions only, preserving property names and examples.
    for keyword in ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas"):
        for child in schema.get(keyword, {}).values():
            if isinstance(child, dict):
                _adapt(child)

    for keyword in (
        "items", "additionalProperties", "contains", "propertyNames",
        "not", "if", "then", "else", "unevaluatedProperties", "unevaluatedItems",
    ):
        child = schema.get(keyword)
        if isinstance(child, dict):
            _adapt(child)
        elif isinstance(child, list):
            for item in child:
                if isinstance(item, dict):
                    _adapt(item)

    for keyword in ("allOf", "anyOf", "oneOf", "prefixItems"):
        for child in schema.get(keyword, []):
            if isinstance(child, dict):
                _adapt(child)
