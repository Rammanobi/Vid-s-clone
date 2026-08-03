from __future__ import annotations


from app.reel_bot.config import settings
from app.reel_bot.reel_db import ReelBotDatabaseClient


class ReelSessionMemory:
    def __init__(self, db: ReelBotDatabaseClient) -> None:
        self.db = db
        self.window_size = settings.memory_window

    async def get_recent(self, session_id: str) -> list[dict[str, str]]:
        """Get recent messages in sliding window format (last N messages)."""
        messages = await self.db.get_recent_messages(
            session_id, limit=self.window_size
        )

        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]

    async def append(
        self, session_id: str, role: str, content: str
    ) -> None:
        """Append a message to the session."""
        await self.db.append_message(session_id, role, content)
