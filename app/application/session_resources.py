from typing import Any

from .ports import SessionStore


class SessionResources:
    def __init__(self, session_store: SessionStore):
        self.session_store = session_store

    async def get_state(self, session_id: str | None) -> dict | None:
        if session_id is None:
            return None

        return await self.session_store.get_session(session_id)

    async def contains(self, session_id: str, resource_type: str, entity_id: Any) -> bool:
        state = await self.get_state(session_id) or {}
        resources = state.get(resource_type, {})
        return isinstance(resources, dict) and str(entity_id) in resources

    async def get_resource(
        self,
        session_id: str,
        resource_type: str,
        entity_id: Any,
    ) -> dict | None:
        state = await self.get_state(session_id) or {}
        resources = state.get(resource_type, {})
        if not isinstance(resources, dict):
            return None

        resource = resources.get(str(entity_id))
        return resource if isinstance(resource, dict) else None

    async def save_response(
        self,
        session_id: str,
        resource_type: str | None,
        response_data: Any,
    ) -> dict | None:
        if (
            resource_type is None
            or not isinstance(response_data, dict)
            or response_data.get("id") is None
        ):
            return None

        state = await self.get_state(session_id) or {}
        resources = state.get(resource_type)
        if not isinstance(resources, dict):
            resources = {}

        entity_id = str(response_data["id"])
        existing_data = resources.get(entity_id)
        if isinstance(existing_data, dict) and existing_data:
            updated_data = existing_data.copy()
            if "status" in response_data:
                updated_data["status"] = response_data["status"]
            resources[entity_id] = updated_data
        else:
            resources[entity_id] = response_data

        state[resource_type] = resources
        await self.session_store.save_session(session_id, state)
        return resources[entity_id]
