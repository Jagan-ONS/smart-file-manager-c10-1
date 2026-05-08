import asyncio

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    url = "http://127.0.0.1:8001/mcp"
    async with streamable_http_client(url) as (read_stream, write_stream, _get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("TOOLS:", [t.name for t in tools])

            result = await session.call_tool("list_directory", {"path": None, "recursive": False})
            print("LIST RESULT:", result)


if __name__ == "__main__":
    asyncio.run(main())