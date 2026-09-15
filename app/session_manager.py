from datetime import datetime, timedelta, timezone


class SessionManager:
    def __init__(self, db):
        self.db = db
        self.states = db["states"]

    async def initialize(self):
        await self.states.create_index(
            "expires_at",
            expireAfterSeconds=0
        )

    async def save_session(self, session_id: str, state: dict):
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        await self.states.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "state": state,
                    "expires_at": expires_at
                }
            },
            upsert=True
        )

    async def get_session(self, session_id: str):
        document = await self.states.find_one(
            {"session_id": session_id}
        )

        if document is None:
            return None

        return document.get("state")

    async def delete_session(self, session_id: str):
        await self.states.delete_one(
            {"session_id": session_id}
        )