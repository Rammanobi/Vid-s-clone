from __future__ import annotations

from typing import Any

from app.prompts import get_reel_bot_chat_prompt
from app.reel_bot.config import settings
from app.reel_bot.reel_db import ReelBotDatabaseClient
from app.reel_bot.reel_llm_client import ReelBotLLMClient
from app.reel_bot.reel_session_memory import ReelSessionMemory


def _format_reel_block(reels: list[dict[str, Any]]) -> str:
    """Format reels data into the context block."""
    if not reels:
        return "--- REEL DATA (LAST 20) ---\nNo reels found for this account.\n--- END REEL DATA ---"

    lines = ["--- REEL DATA (LAST 20) ---\n"]

    for i, reel in enumerate(reels, 1):
        lines.append(f"[REEL {i}]")
        # " · " not " | ": pipe-delimited metrics primed the LLM toward
        # markdown-table output even on qualitative questions - it saw
        # table-shaped data in context and defaulted to a table-shaped reply.
        lines.append(f"  Metrics: {reel['views']:,} views · {reel['likes']:,} likes · "
                     f"{reel['commentsCount']:,} comments · {reel['shares']:,} shares")

        if reel.get("durationSec"):
            lines.append(f"  Duration: {reel['durationSec']:.1f}s")
        if reel.get("wpm"):
            lines.append(f"  Speaking Pace (WPM): {reel['wpm']}")
        if reel.get("topKeywords"):
            keywords = ", ".join(reel["topKeywords"])
            lines.append(f"  Topics: {keywords}")

        if reel.get("cleanTranscript"):
            transcript = reel["cleanTranscript"]
            # Truncate if too long but preserve key content
            if len(transcript) > 300:
                transcript = transcript[:300] + "..."
            lines.append(f"  Transcript: \"{transcript}\"")
        else:
            lines.append(f"  Transcript: [NOT AVAILABLE - transcription failed]")

        lines.append("")

    lines.append("--- END REEL DATA ---")
    return "\n".join(lines)


def _build_prompt(
    reels: list[dict[str, Any]],
    conversation_history: list[dict[str, str]],
    user_message: str,
) -> list[dict[str, str]]:
    """Build the messages list for the LLM."""
    system_prompt = (
        get_reel_bot_chat_prompt()
        + "\n\nREEL DATA (LAST 20):\n\n"
        + _format_reel_block(reels)
        + "\n\nFollow these rules strictly. Your job is to be a data analyst grounded in the "
          "metrics above. Match your output format to what the user asked for."
    )

    messages = [{"role": "system", "content": system_prompt}]

    messages.extend(conversation_history)

    messages.append({"role": "user", "content": user_message})

    return messages


class ReelChatEngine:
    def __init__(
        self,
        db: ReelBotDatabaseClient,
        llm: ReelBotLLMClient,
    ) -> None:
        self.db = db
        self.llm = llm
        self.memory = ReelSessionMemory(db)

    async def run(
        self, session_id: str, instagram_handle: str, user_message: str
    ) -> str:
        """Run the chat engine: fetch reels, build prompt, call LLM, save turn."""
        reels = await self.db.get_recent_reels(
            instagram_handle, limit=settings.max_reels
        )

        history = await self.memory.get_recent(session_id)

        messages = _build_prompt(reels, history, user_message)

        response = await self.llm.chat(messages)

        await self.memory.append(session_id, "user", user_message)
        await self.memory.append(session_id, "assistant", response)

        return response
