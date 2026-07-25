from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.db import DatabaseClient
from app.logging_setup import get_logger

logger = get_logger(__name__)

ToolFunc = Callable[..., Awaitable[Any]]


@dataclass
class ToolInfo:
    name: str
    description: str
    func: ToolFunc
    read_only: bool = True
    param_names: list[str] = field(default_factory=list)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolInfo] = {}

    def register(self, tool: ToolInfo) -> None:
        if tool.name in self._tools:
            logger.warning("tool_overridden", name=tool.name)
        self._tools[tool.name] = tool
        logger.debug("tool_registered", name=tool.name)

    def get(self, name: str) -> ToolInfo | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolInfo]:
        return list(self._tools.values())

    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    async def execute(
        self,
        name: str,
        db: DatabaseClient,
        **kwargs: Any,
    ) -> Any:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not found in registry")
        if not tool.read_only:
            logger.warning("tool_not_read_only", name=name)
        result = await tool.func(db, **kwargs)
        logger.debug(
            "tool_executed",
            name=name,
            read_only=tool.read_only,
        )
        return result


registry = ToolRegistry()
