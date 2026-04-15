"""
MCP Client Manager - The Python helper for the use-mcp Skill.

This module handles:
- Connecting to MCP servers via stdio transport
- Discovering tools from connected servers
- Converting MCP tool schemas to OpenAI-compatible format
- Executing tool calls with safety guardrails
- Logging all interactions for traceability

Architecture Note:
    MCP's stdio_client uses anyio task groups internally, which makes
    manual context manager handling tricky. This module uses a background
    task approach: each MCP server runs in its own asyncio.Task, and
    communication happens via asyncio.Queue.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger("use-mcp.client")


class _MCPServerConnection:
    """
    Wraps a single MCP server connection that runs in a background task.
    
    The stdio_client context manager needs to stay alive for the duration
    of the connection, so we run it in a background task and communicate
    via queues.
    """

    def __init__(self, name: str, command: str, args: list[str]):
        self.name = name
        self.command = command
        self.args = args
        self.tools: list[dict] = []
        self._session: ClientSession | None = None
        self._task: asyncio.Task | None = None
        self._ready_event = asyncio.Event()
        self._shutdown_event = asyncio.Event()
        self._request_queue: asyncio.Queue = asyncio.Queue()
        self._error: Exception | None = None

    async def start(self):
        """Start the MCP server connection in a background task."""
        self._task = asyncio.create_task(self._run(), name=f"mcp-{self.name}")
        # Wait for the connection to be ready
        await self._ready_event.wait()
        if self._error:
            raise self._error

    async def _run(self):
        """Background task that manages the stdio connection lifecycle."""
        try:
            server_params = StdioServerParameters(
                command=self.command,
                args=self.args,
                env=None,
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._session = session

                    # Discover tools
                    tools_result = await session.list_tools()
                    self.tools = []
                    for tool in tools_result.tools:
                        schema = {}
                        if hasattr(tool, 'inputSchema'):
                            schema = tool.inputSchema
                        elif hasattr(tool, 'input_schema'):
                            schema = tool.input_schema
                        self.tools.append({
                            "name": tool.name,
                            "description": tool.description or "",
                            "inputSchema": schema,
                        })

                    logger.info(
                        f"✅ Server '{self.name}' ready — {len(self.tools)} tools: "
                        f"{', '.join(t['name'] for t in self.tools)}"
                    )

                    # Signal that we're ready
                    self._ready_event.set()

                    # Process requests until shutdown
                    while not self._shutdown_event.is_set():
                        try:
                            # Check for requests with a short timeout
                            request = await asyncio.wait_for(
                                self._request_queue.get(), timeout=0.1
                            )
                            tool_name, arguments, response_future = request
                            try:
                                result = await session.call_tool(tool_name, arguments)
                                response_future.set_result(result)
                            except Exception as e:
                                response_future.set_exception(e)
                        except asyncio.TimeoutError:
                            continue

        except Exception as e:
            self._error = e
            self._ready_event.set()  # Unblock start() even on error
            logger.error(f"❌ Server '{self.name}' error: {e}")

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """Send a tool call request to the background task and await result."""
        future = asyncio.get_event_loop().create_future()
        await self._request_queue.put((tool_name, arguments, future))
        return await future

    async def shutdown(self):
        """Signal shutdown and wait for the background task to finish."""
        self._shutdown_event.set()
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass


class MCPClientManager:
    """
    Manages connections to multiple MCP servers and provides a unified
    interface for tool discovery and execution.

    This is the 'muscle' of the use-mcp Skill — it handles all the
    deterministic, code-level concerns so the LLM can focus on reasoning.
    """

    def __init__(self):
        self._connections: dict[str, _MCPServerConnection] = {}
        self._tool_call_log: list[dict] = []

    async def start_server(self, name: str, command: str, args: list[str]) -> list[dict]:
        """
        Start and connect to an MCP server via stdio transport.

        Args:
            name: Unique server name (e.g., 'math', 'filesystem')
            command: Command to run (e.g., 'python')
            args: Command arguments (e.g., ['path/to/server.py'])

        Returns:
            List of tool definitions from the server
        """
        logger.info(f"🔌 Starting MCP server: {name} ({command} {' '.join(args)})")

        conn = _MCPServerConnection(name, command, args)
        await conn.start()
        self._connections[name] = conn
        return conn.tools

    def list_all_tools(self) -> dict[str, list[dict]]:
        """
        Return all discovered tools, grouped by server name.

        Returns:
            { "server_name": [ { name, description, inputSchema }, ... ] }
        """
        return {name: conn.tools for name, conn in self._connections.items()}

    def convert_to_openai_tools(self) -> list[dict]:
        """
        Convert all MCP tools to OpenAI-compatible tool schemas.

        Each tool gets a qualified name: {server_name}__{tool_name}
        This allows the LLM to call tools via standard OpenAI tool_call format,
        and the agent loop can route back to the correct MCP server.

        Returns:
            List of OpenAI tool definitions
        """
        openai_tools = []
        for server_name, conn in self._connections.items():
            for tool in conn.tools:
                qualified_name = f"{server_name}__{tool['name']}"
                openai_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": qualified_name,
                            "description": f"[Server: {server_name}] {tool['description']}",
                            "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
                        },
                    }
                )
        return openai_tools

    async def call_tool(
        self,
        qualified_name: str,
        arguments: dict[str, Any],
    ) -> dict:
        """
        Execute a tool call via MCP.

        Args:
            qualified_name: Tool name in format 'server__tool'
            arguments: Tool arguments

        Returns:
            { "status": "success"|"error", "server": str, "tool": str, "result": str }
        """
        # Parse qualified name
        parts = qualified_name.split("__", 1)
        if len(parts) != 2:
            return {
                "status": "error",
                "server": "unknown",
                "tool": qualified_name,
                "result": f"Invalid tool name format. Expected 'server__tool', got '{qualified_name}'",
            }

        server_name, tool_name = parts

        if server_name not in self._connections:
            return {
                "status": "error",
                "server": server_name,
                "tool": tool_name,
                "result": f"Server '{server_name}' not found. Available: {list(self._connections.keys())}",
            }

        # Log the call
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "server": server_name,
            "tool": tool_name,
            "arguments": arguments,
            "status": "pending",
        }
        self._tool_call_log.append(log_entry)

        logger.info(
            f"🔧 Calling {server_name}::{tool_name} "
            f"args={json.dumps(arguments, default=str)}"
        )

        try:
            conn = self._connections[server_name]
            result = await conn.call_tool(tool_name, arguments)

            # Extract text from result content
            result_text = ""
            if hasattr(result, 'content') and result.content:
                for content in result.content:
                    if hasattr(content, 'text'):
                        result_text += content.text
                    else:
                        result_text += str(content)
            else:
                result_text = str(result)

            log_entry["status"] = "success"
            log_entry["result_preview"] = result_text[:200]

            logger.info(f"✅ Result from {server_name}::{tool_name}: {result_text[:100]}...")

            return {
                "status": "success",
                "server": server_name,
                "tool": tool_name,
                "result": result_text,
            }

        except Exception as e:
            log_entry["status"] = "error"
            log_entry["error"] = str(e)
            logger.error(f"❌ Error calling {server_name}::{tool_name}: {e}")

            return {
                "status": "error",
                "server": server_name,
                "tool": tool_name,
                "result": f"Tool execution failed: {e}",
            }

    def get_call_log(self) -> list[dict]:
        """Return the complete tool call log for traceability."""
        return self._tool_call_log.copy()

    def get_stats(self) -> dict:
        """Return statistics about connected servers and tool calls."""
        total_tools = sum(len(conn.tools) for conn in self._connections.values())
        return {
            "connected_servers": len(self._connections),
            "total_tools": total_tools,
            "total_calls": len(self._tool_call_log),
            "successful_calls": sum(
                1 for log in self._tool_call_log if log["status"] == "success"
            ),
            "failed_calls": sum(
                1 for log in self._tool_call_log if log["status"] == "error"
            ),
            "servers": {
                name: [t["name"] for t in conn.tools]
                for name, conn in self._connections.items()
            },
        }

    async def shutdown(self):
        """Gracefully shutdown all MCP server connections."""
        for name, conn in self._connections.items():
            logger.info(f"🔌 Shutting down MCP server: {name}")
            await conn.shutdown()
        self._connections.clear()
        logger.info("All MCP servers shut down.")
