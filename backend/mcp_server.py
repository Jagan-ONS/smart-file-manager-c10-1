from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv


# Load backend/.env if present (local dev convenience).
# Use override=True so restarting servers picks up changes reliably.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=True)

# Sandbox root (all tool paths are relative to this root).
# If SMARTFM_ROOT is set but invalid, fall back to repo root.
_DEFAULT_ROOT = Path(__file__).resolve().parents[1]
_ENV_ROOT = (os.environ.get("SMARTFM_ROOT") or "").strip()
SMARTFM_ROOT = (Path(_ENV_ROOT).resolve() if _ENV_ROOT else _DEFAULT_ROOT).resolve()
if not SMARTFM_ROOT.exists():
    SMARTFM_ROOT = _DEFAULT_ROOT.resolve()

# MCP service configuration.
DEFAULT_MCP_PORT = int(os.environ.get("SMARTFM_MCP_PORT", "8000"))
MCP_HOST = os.environ.get("SMARTFM_MCP_HOST", "127.0.0.1")

# Guardrails
MAX_READ_BYTES = int(os.environ.get("SMARTFM_MAX_READ_BYTES", "200000"))
MAX_WRITE_BYTES = int(os.environ.get("SMARTFM_MAX_WRITE_BYTES", "200000"))
MAX_SEARCH_RESULTS = int(os.environ.get("SMARTFM_MAX_SEARCH_RESULTS", "100"))
MAX_SEARCH_FILES_SCANNED = int(os.environ.get("SMARTFM_MAX_SEARCH_FILES", "5000"))

_DENY_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
}


def _is_hidden_path(rel_path: Path) -> bool:
    parts = [p for p in rel_path.parts if p not in ("", ".", os.sep)]
    for part in parts:
        if part.startswith("."):
            return True
        if part in _DENY_DIRS:
            return True
    return False


def _safe_resolve(user_path: str | None) -> Path:
    rel = Path(user_path or ".")
    # Disallow absolute paths and Windows drive-relative paths like C:foo
    if rel.is_absolute() or re.match(r"^[a-zA-Z]:", (user_path or "")):
        raise ValueError("Path must be relative to SMARTFM_ROOT")

    candidate = (SMARTFM_ROOT / rel).resolve()
    try:
        candidate.relative_to(SMARTFM_ROOT)
    except Exception as exc:
        raise ValueError("Path escapes SMARTFM_ROOT") from exc

    rel_to_root = candidate.relative_to(SMARTFM_ROOT)
    if _is_hidden_path(rel_to_root):
        raise ValueError("Hidden/system paths are not allowed")

    return candidate


def _rel_str(path: Path) -> str:
    return path.relative_to(SMARTFM_ROOT).as_posix()


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


PREFERRED_MCP_PORTS = [DEFAULT_MCP_PORT] + [p for p in range(8002, 8011) if p != DEFAULT_MCP_PORT]
MCP_PORT = DEFAULT_MCP_PORT if os.environ.get("SMARTFM_MCP_PORT") else _find_free_port(MCP_HOST, PREFERRED_MCP_PORTS)
if MCP_PORT != DEFAULT_MCP_PORT:
    print(f"SMARTFM_MCP_PORT not set, using free port {MCP_PORT}")

MCP_PORT_FILE = Path(__file__).resolve().parent / ".mcp_port"
try:
    MCP_PORT_FILE.write_text(str(MCP_PORT), encoding="utf-8")
except Exception as exc:
    print(f"Warning: unable to write MCP port file: {exc}")

mcp = FastMCP(
    "smart-file-manager",
    host=MCP_HOST,
    port=MCP_PORT,
    streamable_http_path="/mcp",
)


@mcp.tool()
def read_file(path: str, *, max_bytes: int | None = None) -> dict[str, Any]:
    """Read a UTF-8 text file within SMARTFM_ROOT (size limited)."""
    p = _safe_resolve(path)
    if not p.is_file():
        raise ValueError("Path is not a file")

    limit = min(int(max_bytes or MAX_READ_BYTES), MAX_READ_BYTES)
    size = p.stat().st_size
    if size > limit:
        raise ValueError(f"File too large to read ({size} bytes > {limit} bytes)")

    data = p.read_bytes()
    if len(data) > limit:
        raise ValueError(f"Read exceeded limit ({len(data)} bytes > {limit} bytes)")

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")

    return {"path": _rel_str(p), "bytes": len(data), "content": text}


@mcp.tool()
def list_directory(
    path: str | None = None,
    *,
    recursive: bool = False,
    max_entries: int = 500,
    max_depth: int = 10,
) -> dict[str, Any]:
    """List directory contents under SMARTFM_ROOT (hidden filtered)."""
    p = _safe_resolve(path)
    if not p.exists():
        raise ValueError("Directory does not exist")
    if not p.is_dir():
        raise ValueError("Path is not a directory")

    max_entries = max(1, min(int(max_entries), 5000))
    max_depth = max(0, min(int(max_depth), 50))

    items: list[dict[str, Any]] = []

    def add_entry(child: Path) -> None:
        rel = child.relative_to(SMARTFM_ROOT)
        if _is_hidden_path(rel):
            return
        st = child.stat()
        items.append(
            {
                "path": rel.as_posix(),
                "name": child.name,
                "is_dir": child.is_dir(),
                "size": int(st.st_size) if child.is_file() else None,
                "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            }
        )

    if not recursive:
        for child in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if len(items) >= max_entries:
                break
            add_entry(child)
    else:
        for root, dirs, files in os.walk(p):
            root_p = Path(root)
            depth = len(root_p.relative_to(p).parts)
            if depth > max_depth:
                dirs[:] = []
                continue

            kept_dirs: list[str] = []
            for d in dirs:
                rel = (root_p / d).relative_to(SMARTFM_ROOT)
                if _is_hidden_path(rel):
                    continue
                kept_dirs.append(d)
            dirs[:] = kept_dirs

            for d in dirs:
                if len(items) >= max_entries:
                    break
                add_entry(root_p / d)
            for f in files:
                if len(items) >= max_entries:
                    break
                rel = (root_p / f).relative_to(SMARTFM_ROOT)
                if _is_hidden_path(rel):
                    continue
                add_entry(root_p / f)

            if len(items) >= max_entries:
                break

    return {"root": str(SMARTFM_ROOT), "path": _rel_str(p), "items": items}


@mcp.tool()
def get_file_metadata(path: str) -> dict[str, Any]:
    """Return basic metadata for a file/dir under SMARTFM_ROOT."""
    p = _safe_resolve(path)
    if not p.exists():
        raise ValueError("Path does not exist")
    st = p.stat()
    return {
        "path": _rel_str(p),
        "is_dir": p.is_dir(),
        "is_file": p.is_file(),
        "size": int(st.st_size) if p.is_file() else None,
        "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
    }


@mcp.tool()
def write_file(
    path: str,
    content: str,
    *,
    overwrite: bool = False,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    """Write a text file under SMARTFM_ROOT (size limited)."""
    p = _safe_resolve(path)
    data = content.encode(encoding, errors="strict")
    if len(data) > MAX_WRITE_BYTES:
        raise ValueError(f"Write too large ({len(data)} bytes > {MAX_WRITE_BYTES} bytes)")

    if p.exists() and not overwrite:
        raise ValueError("File exists (set overwrite=true to replace)")

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return {"ok": True, "path": _rel_str(p), "bytes": len(data)}


@mcp.tool()
def search_files(
    query: str,
    *,
    path: str | None = None,
    mode: Literal["name", "content", "both"] = "both",
    case_sensitive: bool = False,
    max_results: int | None = None,
) -> dict[str, Any]:
    """Search for a string in file names and/or file content under SMARTFM_ROOT."""
    base = _safe_resolve(path)
    if not base.exists() or not base.is_dir():
        raise ValueError("Search path must be an existing directory")

    if not query:
        return {"query": query, "results": []}

    max_results_eff = min(int(max_results or MAX_SEARCH_RESULTS), MAX_SEARCH_RESULTS)
    flags = 0 if case_sensitive else re.IGNORECASE
    needle = re.compile(re.escape(query), flags=flags)

    results: list[dict[str, Any]] = []
    scanned = 0

    for root, dirs, files in os.walk(base):
        root_p = Path(root)
        kept_dirs: list[str] = []
        for d in dirs:
            rel = (root_p / d).relative_to(SMARTFM_ROOT)
            if _is_hidden_path(rel):
                continue
            kept_dirs.append(d)
        dirs[:] = kept_dirs

        for fname in files:
            rel = (root_p / fname).relative_to(SMARTFM_ROOT)
            if _is_hidden_path(rel):
                continue

            scanned += 1
            if scanned > MAX_SEARCH_FILES_SCANNED:
                return {
                    "query": query,
                    "truncated": True,
                    "reason": "max_files_scanned",
                    "files_scanned": scanned,
                    "results": results,
                }

            full = SMARTFM_ROOT / rel

            if mode in ("name", "both") and needle.search(fname):
                results.append({"path": rel.as_posix(), "match": "name"})
                if len(results) >= max_results_eff:
                    return {"query": query, "results": results, "files_scanned": scanned, "truncated": True}

            if mode in ("content", "both") and full.is_file():
                try:
                    if full.stat().st_size > MAX_READ_BYTES:
                        continue
                    text = full.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                for i, line in enumerate(text.splitlines(), start=1):
                    if needle.search(line):
                        results.append(
                            {
                                "path": rel.as_posix(),
                                "match": "content",
                                "line": i,
                                "snippet": line.strip()[:400],
                            }
                        )
                        if len(results) >= max_results_eff:
                            return {
                                "query": query,
                                "results": results,
                                "files_scanned": scanned,
                                "truncated": True,
                            }

    return {"query": query, "results": results, "files_scanned": scanned, "truncated": False}


if __name__ == "__main__":
    # Real MCP server over Streamable HTTP.
    MCP_PORT_FILE = Path(__file__).resolve().parent / ".mcp_port"
    try:
        MCP_PORT_FILE.write_text(str(MCP_PORT), encoding="utf-8")
    except Exception as exc:
        print(f"Warning: unable to write MCP port file: {exc}")

    print(f"Starting MCP server at http://{MCP_HOST}:{MCP_PORT}{mcp.settings.streamable_http_path}")
    mcp.run(transport="streamable-http", mount_path="/mcp")
