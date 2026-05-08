import anyio
import json
import os
import time
import uuid
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from openai import OpenAI

from fastmcp import Client as MCPClient
from dotenv import load_dotenv


# Load backend/.env if present (local dev convenience).
# Use override=True so restarting servers picks up changes reliably.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=True)


def _sse(event: str, data: Dict[str, Any]) -> bytes:
    return (f"event: {event}\n" f"data: {json.dumps(data, ensure_ascii=False)}\n\n").encode("utf-8")


def _openai_tools_from_mcp(tools: List[Any]) -> List[Dict[str, Any]]:
    # does this convert the tools from the mcp server to the openai tools format ?
    # yes i guess 
    # but why we are doing this ?  
    # because the openai api expects the tools in a specific format
    # what if i use someother model later on ?? 

    out: List[Dict[str, Any]] = []
    for t in tools:
        name = getattr(t, "name", None) or t.get("name")
        desc = getattr(t, "description", None) or t.get("description") or ""
        schema = getattr(t, "inputSchema", None) or getattr(t, "input_schema", None) or t.get("inputSchema")
        if schema is None:
            schema = {"type": "object", "properties": {}}
        out.append({"type": "function", "function": {"name": name, "description": desc, "parameters": schema}})
    return out


app = FastAPI(title="Smart File Manager Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
MCP_HOST = os.environ.get("SMARTFM_MCP_HOST", "127.0.0.1")
DEFAULT_MCP_PORT = int(os.environ.get("SMARTFM_MCP_PORT", "8000"))


def _find_free_port(host: str, preferred_ports: list[int]) -> int:
    import socket

    for port in preferred_ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, 0))
        return sock.getsockname()[1]


MCP_URL = os.environ.get("SMARTFM_MCP_URL")
# what is the MCP_PORT_FILE ? 
MCP_PORT_FILE = os.path.join(os.path.dirname(__file__), ".mcp_port")
if not MCP_URL:
    if os.path.exists(MCP_PORT_FILE):
        try:
            with open(MCP_PORT_FILE, "r", encoding="utf-8") as f:
                selected_port_text = f.read().strip()
            if selected_port_text.startswith(("'", '"')) and selected_port_text.endswith(("'", '"')):
                selected_port_text = selected_port_text[1:-1].strip()
            selected_port = int(selected_port_text)
        except Exception:
            selected_port = None
    else:
        selected_port = None

    if selected_port is None:
        preferred_ports = [DEFAULT_MCP_PORT] + [p for p in range(8001, 8011) if p != DEFAULT_MCP_PORT]
        selected_port = DEFAULT_MCP_PORT if os.environ.get("SMARTFM_MCP_PORT") else _find_free_port(MCP_HOST, preferred_ports)

    MCP_URL = f"http://{MCP_HOST}:{selected_port}/mcp"


@app.get("/health")
def health():
    return {"ok": True, "model": OPENAI_MODEL, "mcp_url": MCP_URL}


async def _mcp_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    # this will call the tool in the mcp server with the help of the MCPClient
    # how the response from the mcp server is going to be and how it's going to be used ? 

    async with MCPClient(MCP_URL) as client:
        res = await client.call_tool(tool_name, arguments)
        print("resource from mcp call to tool ", tool_name, " is ", res)
        content = getattr(res, "content", None) or []
        if content:
            text = getattr(content[0], "text", None)
            if isinstance(text, str):
                try:
                    return json.loads(text)
                except Exception:
                    return {"text": text}
        return {"result": str(res)}


@app.get("/tree")
async def tree(path: str = Query(default=".")):
    try:
        # Q : llm should decide this tool call right ?? 
        # this end point is hit only in the initial request   
        # so these normal deterministic tools like in the start we need to have the 
        # file directory here so llm don't create a tool call 
        # what usually happens is when we type something in the query box about the file directory 
        # the llm creates a tool call according to the query and then we need to execute the tool call  
        # by passing the arguments  
        # now take that tool call and execute it  
        # but how to call tools which are in the mcp server  , how do we do this ?
        return JSONResponse(
            await _mcp_call("list_directory", {"path": path, "recursive": False, "max_entries": 500})
        )
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/preview")
async def preview(path: str):
    try:
        return JSONResponse(await _mcp_call("read_file", {"path": path}))
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    user_message = body.get("message")
    conversation_id = body.get("conversation_id") or str(uuid.uuid4())

    if not isinstance(user_message, str) or not user_message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")

    openai = OpenAI()
    # Q : so stream is a generator which is used by StreamingResponse ??
    async def stream():
        async with MCPClient(MCP_URL) as mcp_client:
            mcp_tools = await mcp_client.list_tools()
            tools = _openai_tools_from_mcp(mcp_tools)

        messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are Smart File Manager. Use tools to inspect and modify files safely. "
                    "All paths must be relative to SMARTFM_ROOT. Keep answers concise."
                ),
            },
            {"role": "user", "content": user_message},
        ]

        max_rounds = 8
        for _ in range(max_rounds):
            def create_completion():

                # explain this clearly  
                # Q :  
                return openai.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                )

            resp = await anyio.to_thread.run_sync(create_completion)
            msg = resp.choices[0].message
            tool_calls = getattr(msg, "tool_calls", None) or []

            if not tool_calls:
                text = msg.content or ""
                if text:
                    yield _sse("assistant_delta", {"conversation_id": conversation_id, "text_delta": text})
                yield _sse("assistant_final", {"conversation_id": conversation_id, "full_text": text})
                return

            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in tool_calls
                    ],
                }
            )
            # Q : why so many yeilds what the hell is this doing 
            for tc in tool_calls:
                tool_call_id = tc.id or str(uuid.uuid4())
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {"_raw": tc.function.arguments}

                # Defensive normalization: some models may emit "" for optional path args.
                # In our MCP tools, `None` means "use root", but "" becomes a real Path("")
                # which resolves weirdly on Windows. Treat "" as None.
                if isinstance(args, dict):
                    for k in ("path", "directory"):
                        if args.get(k) == "":
                            args[k] = None

                yield _sse(
                    "tool_call",
                    {
                        "conversation_id": conversation_id,
                        "tool_call_id": tool_call_id,
                        "name": name,
                        "arguments": args,
                    },
                )

                t0 = time.time()
                try:
                    tool_data = await _mcp_call(name, args if isinstance(args, dict) else {})
                    duration_ms = int((time.time() - t0) * 1000)
                    yield _sse(
                        "tool_result",
                        {
                            "conversation_id": conversation_id,
                            "tool_call_id": tool_call_id,
                            "ok": True,
                            "data": {"duration_ms": duration_ms, "result": tool_data},
                            "error": None,
                        },
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps(tool_data, ensure_ascii=False),
                        }
                    )
                except Exception as e:
                    yield _sse(
                        "tool_result",
                        {
                            "conversation_id": conversation_id,
                            "tool_call_id": tool_call_id,
                            "ok": False,
                            "data": None,
                            "error": {"message": str(e)},
                        },
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False),
                        }
                    )

        yield _sse(
            "error",
            {
                "conversation_id": conversation_id,
                "message": "Tool loop exceeded max iterations",
                "debug_code": "MAX_ITERS",
            },
        )

    return StreamingResponse(stream(), media_type="text/event-stream")

