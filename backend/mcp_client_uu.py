from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


@dataclass
class MCPTool:
    name: str
    description: str | None
    input_schema: dict[str, Any] | None


class MCPHttpSession:
    def __init__(self, url: str):
        self.url = url
        self._session: ClientSession | None = None
        self._streams_cm = None

    async def __aenter__(self) -> "MCPHttpSession":
        self._streams_cm = streamable_http_client(self.url)
        read_stream, write_stream, _get_session_id = await self._streams_cm.__aenter__()
        self._session = ClientSession(read_stream, write_stream)
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._session is not None:
            await self._session.__aexit__(exc_type, exc, tb)
        if self._streams_cm is not None:
            await self._streams_cm.__aexit__(exc_type, exc, tb)

    async def list_tools(self) -> list[MCPTool]:
        if self._session is None:
            raise RuntimeError("Session not initialized")
        tools = await self._session.list_tools()
        out: list[MCPTool] = []
        for t in tools:
            out.append(
                MCPTool(
                    name=t.name,
                    description=getattr(t, "description", None),
                    input_schema=getattr(t, "inputSchema", None),
                )
            )
        return out

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        if self._session is None:
            raise RuntimeError("Session not initialized")
        return await self._session.call_tool(name, arguments or {})

