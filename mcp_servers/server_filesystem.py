"""
MCP Server: Filesystem (Read-Only)
A simple FastMCP server that provides read-only filesystem access.
Transport: stdio

Safety: Only read operations. No write, delete, or modify.
"""

import os
import stat
from datetime import datetime
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="filesystem",
    instructions="Read-only filesystem access server. Can list directories, read files, and get file info. No write operations.",
)

# Restrict to project directory for safety
_ALLOWED_ROOT = Path(__file__).parent.parent.resolve()


def _is_safe_path(path_str: str) -> tuple[bool, Path]:
    """Validate that path is within allowed root directory."""
    try:
        resolved = Path(path_str).resolve()
        if str(resolved).startswith(str(_ALLOWED_ROOT)):
            return True, resolved
        return False, resolved
    except Exception:
        return False, Path(path_str)


@mcp.tool()
def list_directory(path: str = ".") -> str:
    """List contents of a directory.

    Args:
        path: Path to directory (relative to project root, or absolute within project).
              Defaults to project root.

    Returns:
        Formatted list of files and directories
    """
    # Handle relative paths
    if not os.path.isabs(path):
        full_path = _ALLOWED_ROOT / path
    else:
        full_path = Path(path)

    safe, resolved = _is_safe_path(str(full_path))
    if not safe:
        return f"Error: Access denied. Path must be within {_ALLOWED_ROOT}"

    if not resolved.exists():
        return f"Error: Path does not exist: {resolved}"

    if not resolved.is_dir():
        return f"Error: Not a directory: {resolved}"

    entries = []
    try:
        for item in sorted(resolved.iterdir()):
            if item.name.startswith("."):
                continue  # skip hidden files
            kind = "📁" if item.is_dir() else "📄"
            size = ""
            if item.is_file():
                size_bytes = item.stat().st_size
                if size_bytes < 1024:
                    size = f" ({size_bytes} B)"
                elif size_bytes < 1024 * 1024:
                    size = f" ({size_bytes / 1024:.1f} KB)"
                else:
                    size = f" ({size_bytes / (1024*1024):.1f} MB)"
            entries.append(f"  {kind} {item.name}{size}")
    except PermissionError:
        return f"Error: Permission denied for {resolved}"

    if not entries:
        return f"Directory is empty: {resolved}"

    header = f"📂 {resolved.relative_to(_ALLOWED_ROOT)}\n"
    return header + "\n".join(entries)


@mcp.tool()
def read_file(path: str, max_lines: int = 100) -> str:
    """Read contents of a text file.

    Args:
        path: Path to file (relative to project root, or absolute within project)
        max_lines: Maximum number of lines to read (default 100, max 500)

    Returns:
        File contents with line numbers
    """
    if not os.path.isabs(path):
        full_path = _ALLOWED_ROOT / path
    else:
        full_path = Path(path)

    safe, resolved = _is_safe_path(str(full_path))
    if not safe:
        return f"Error: Access denied. Path must be within {_ALLOWED_ROOT}"

    if not resolved.exists():
        return f"Error: File does not exist: {resolved}"

    if not resolved.is_file():
        return f"Error: Not a file: {resolved}"

    max_lines = min(max_lines, 500)

    try:
        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            for i, line in enumerate(f, 1):
                if i > max_lines:
                    lines.append(f"... (truncated at {max_lines} lines)")
                    break
                lines.append(f"{i:4d} | {line.rstrip()}")
        return f"📄 {resolved.name}\n" + "\n".join(lines)
    except Exception as e:
        return f"Error reading file: {e}"


@mcp.tool()
def file_info(path: str) -> str:
    """Get detailed information about a file or directory.

    Args:
        path: Path to file/directory (relative to project root, or absolute within project)

    Returns:
        File metadata: size, permissions, timestamps, type
    """
    if not os.path.isabs(path):
        full_path = _ALLOWED_ROOT / path
    else:
        full_path = Path(path)

    safe, resolved = _is_safe_path(str(full_path))
    if not safe:
        return f"Error: Access denied. Path must be within {_ALLOWED_ROOT}"

    if not resolved.exists():
        return f"Error: Path does not exist: {resolved}"

    try:
        st = resolved.stat()
        info_lines = [
            f"📋 File Info: {resolved.name}",
            f"   Path: {resolved.relative_to(_ALLOWED_ROOT)}",
            f"   Type: {'Directory' if resolved.is_dir() else 'File'}",
            f"   Size: {st.st_size:,} bytes",
            f"   Permissions: {stat.filemode(st.st_mode)}",
            f"   Modified: {datetime.fromtimestamp(st.st_mtime).isoformat()}",
            f"   Created: {datetime.fromtimestamp(st.st_ctime).isoformat()}",
        ]

        if resolved.is_file():
            info_lines.append(f"   Extension: {resolved.suffix or '(none)'}")

        if resolved.is_dir():
            count = sum(1 for _ in resolved.iterdir())
            info_lines.append(f"   Children: {count} items")

        return "\n".join(info_lines)
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
