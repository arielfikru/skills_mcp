"""
Agent Loop - Main entry point for the MCP-in-Skills POC.

New Architecture:
1. Skills are registered (metadata only) at startup.
2. MCP is NOT connected at startup.
3. LLM is given an 'activate_skill' tool and a catalog of available skills.
4. When LLM decides to use MCP, it calls activate_skill('use-mcp').
5. This triggers the activation hook, which connects MCP and loads SKILL.md.
6. The new MCP tools are dynamically added to the LLM's available tools.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from openai import AsyncOpenAI

import config
from framework.skill_manager import SkillManager

# ─── Logging Setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-15s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("agent")


# ─── Pretty Printing ─────────────────────────────────────────

C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_MAGENTA = "\033[35m"
C_BLUE = "\033[34m"


def print_banner():
    banner = f"""
{C_CYAN}{C_BOLD}╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🧩  MCP-in-Skills POC (Lazy Loading)                      ║
║   ────────────────────────────────────                       ║
║   Skills are registered via metadata only. MCP connects      ║
║   ONLY when the LLM explicitly calls activate_skill().       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝{C_RESET}
"""
    print(banner)


def print_divider(char="─", width=60):
    print(f"{C_DIM}{char * width}{C_RESET}")


def print_status(label: str, value: str, color: str = C_GREEN):
    print(f"  {C_DIM}│{C_RESET} {label}: {color}{value}{C_RESET}")


def print_tool_call(server: str, tool: str, args: dict):
    print(f"\n  {C_YELLOW}⚡ Tool Call{C_RESET}: {C_BOLD}{server}{C_RESET}::{C_CYAN}{tool}{C_RESET}")
    if args:
        for k, v in args.items():
            print(f"  {C_DIM}│{C_RESET}   {k} = {C_MAGENTA}{v}{C_RESET}")


def print_tool_result(server: str, tool: str, result: str, status: str):
    icon = "✅" if status == "success" else "❌"
    color = C_GREEN if status == "success" else C_RED
    cleaned_result = str(result)
    print(f"  {icon} {color}Result{C_RESET} from {server}::{tool}:")
    for line in cleaned_result.split("\n"):
        print(f"  {C_DIM}│{C_RESET}   {line}")


# ─── Agent Class ──────────────────────────────────────────────


class Agent:
    def __init__(self, skill_enabled: bool = True):
        self.skill_enabled = skill_enabled
        project_root = Path(__file__).parent
        
        self.skill_manager = SkillManager(project_root / "skills")
        self.mcp_manager = None
        
        self.openai_client = AsyncOpenAI(
            base_url=config.OPENROUTER_BASE_URL,
            api_key=config.OPENROUTER_API_KEY,
        )
        self.model = config.OPENROUTER_MODEL
        
        self.messages: list[dict] = []
        
        # Tools explicitly available to LLM at start
        self.base_tools = [
            {
                "type": "function",
                "function": {
                    "name": "activate_skill",
                    "description": "Activate a registered skill to load its instructions and enable its tools.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "The name of the skill to activate (e.g., 'use-mcp')"
                            }
                        },
                        "required": ["name"]
                    }
                }
            }
        ]
        self.current_tools = []

    async def _activate_mcp_hook(self, manager: SkillManager, skill_name: str) -> str:
        """Hook called when a specific MCP skill (e.g., mcp-math) is activated by LLM."""
        from skills.use_mcp.mcp_client import MCPClientManager
        
        if not self.mcp_manager:
            logger.info("Initializing MCP Client Manager...")
            self.mcp_manager = MCPClientManager()
        
        # Extract server name from skill name (e.g. 'mcp-math' -> 'math')
        server_key = skill_name.replace("mcp-", "")
        
        # Find the server in config
        server_def = next((s for s in config.MCP_SERVERS if s["name"] == server_key), None)
        if not server_def:
            return f"Error: No MCP configuration found for '{server_key}'."
            
        try:
            logger.info(f"Starting specific MCP server: {server_key}...")
            await self.mcp_manager.start_server(
                name=server_def["name"],
                command=server_def["command"],
                args=server_def["args"],
            )
        except Exception as e:
            msg = f"Failed to start MCP server {server_def['name']}: {e}"
            logger.error(msg)
            return f"Error: {msg}"
                
        # Update agent's tools with ALL active MCP instances
        mcp_tools = self.mcp_manager.convert_to_openai_tools()
        
        # Rebuild current tools: base tools + new mcp tools
        self.current_tools = list(self.base_tools)
        self.current_tools.extend(mcp_tools)
        
        return f"MCP Server '{server_key}' connected successfully. {len(mcp_tools)} total MCP tools now in your toolbox."

    async def initialize(self):
        """Setup initial prompt and register skills (metadata only)."""
        base_prompt = "You are a smart and proactive AI assistant.\n\n"
        
        if self.skill_enabled:
            # Only scan and register names + descriptions. No MCP connect here!
            registry = self.skill_manager.scan_and_register()
            
            # Hook the specific MCP skills
            for skill_name in list(registry.keys()):
                if skill_name.startswith("mcp-"):
                    self.skill_manager.register_activation_hook(skill_name, self._activate_mcp_hook)
            
            # Show LLM what's available
            catalog = self.skill_manager.build_catalog_prompt()
            base_prompt += catalog
            
            # Agent starts with only the activate_skill tool
            self.current_tools = list(self.base_tools)
            
            print(f"\n  {C_GREEN}✅ Platform Ready. {len(registry)} skills registered.{C_RESET}")
            print(f"  {C_DIM}│{C_RESET} Note: MCP servers are currently disconnected. Zero tools loaded.")
            print(f"  {C_DIM}│{C_RESET} Waiting for LLM to call activate_skill().")
        else:
            base_prompt += "NOTE: The skill system is DISABLED. You do not have access to any external tools."
            print(f"\n  {C_RED}⚠ Skill System DISABLED{C_RESET}")
            self.current_tools = []
            
        self.messages.append({"role": "system", "content": base_prompt})

    async def chat(self, user_input: str) -> str:
        """Process user input through ReAct loop."""
        self.messages.append({"role": "user", "content": user_input})

        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            try:
                kwargs = {
                    "model": self.model,
                    "messages": self.messages,
                    "max_tokens": 4096,
                }

                if self.current_tools:
                    kwargs["tools"] = self.current_tools
                    kwargs["tool_choice"] = "auto"

                response = await self.openai_client.chat.completions.create(**kwargs)

            except Exception as e:
                logger.error(f"OpenRouter API error: {e}")
                return f"❌ {e}"

            message = response.choices[0].message

            if not message.tool_calls:
                self.messages.append({"role": "assistant", "content": message.content or ""})
                return message.content or "(empty response)"

            # Keep assistant's thinking in history
            self.messages.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            })

            # Process each tool call
            for tool_call in message.tool_calls:
                qualified_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                # -- Handle framework tool: activate_skill --
                if qualified_name == "activate_skill":
                    skill_name = arguments.get("name", "")
                    print_tool_call("framework", "activate_skill", arguments)
                    
                    res = await self.skill_manager.activate_skill(skill_name)
                    
                    if res["status"] in ("activated", "already_active"):
                        tool_output = f"Skill '{skill_name}' activated.\n\nINSTRUCTIONS:\n{res['content']}\n\nSIDE EFFECTS:\n{res['side_effects']}"
                        status = "success"
                    else:
                        tool_output = f"Error: {res['side_effects']}"
                        status = "error"
                        
                    print_tool_result("framework", "activate_skill", res["side_effects"], status)
                    
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_output,
                    })
                    continue

                # -- Handle MCP tools --
                if self.mcp_manager:
                    parts = qualified_name.split("__", 1)
                    server_name = parts[0] if len(parts) == 2 else "?"
                    tool_name = parts[1] if len(parts) == 2 else qualified_name

                    print_tool_call(server_name, tool_name, arguments)
                    result = await self.mcp_manager.call_tool(qualified_name, arguments)
                    
                    print_tool_result(server_name, tool_name, result["result"], result["status"])

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result["result"],
                    })
                else:
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": f"Error: MCP Manager is not initialized. Activate the use-mcp skill first.",
                    })

        return "⚠ Maximum tool call iterations reached."

    async def shutdown(self):
        if self.mcp_manager:
            stats = self.mcp_manager.get_stats()
            print(f"\n{C_DIM}{'─' * 60}{C_RESET}")
            print(f"  {C_CYAN}📊 Session Stats{C_RESET}")
            print_status("Total tool calls", str(stats["total_calls"]))
            print_status("Successful", str(stats["successful_calls"]), C_GREEN)
            await self.mcp_manager.shutdown()


async def main():
    parser = argparse.ArgumentParser(description="MCP-in-Skills POC (Lazy Loading)")
    parser.add_argument("--no-skill", action="store_true", help="Disable skills")
    args = parser.parse_args()

    # If the user has missing API key, fail fast
    if not config.OPENROUTER_API_KEY:
        print(f"{C_RED}❌ OPENROUTER_API_KEY not set in .env{C_RESET}")
        sys.exit(1)

    print_banner()

    agent = Agent(skill_enabled=not args.no_skill)
    try:
        await agent.initialize()
        print_divider()
        
        print(f"\n  {C_DIM}💡 Try asking: \"Please calculate the 10th fibonacci number\"{C_RESET}")
        print(f"  {C_DIM}   The Agent will activate the 'mcp-math' skill to mount the required tool.{C_RESET}\n")

        while True:
            try:
                user_input = input(f"{C_BOLD}{C_BLUE}You ❯ {C_RESET}").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                break

            if user_input.lower() == "log":
                if agent.mcp_manager:
                    print(json.dumps(agent.mcp_manager.get_call_log(), indent=2))
                else:
                    print("No MCP manager active.")
                continue

            print()
            response = await agent.chat(user_input)
            print(f"\n{C_GREEN}{C_BOLD}Agent ❯{C_RESET} {response}\n")

    finally:
        await agent.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
