# MCP-in-Skills POC (Lazy Loading Architecture)

This is a Proof of Concept (POC) demonstrating a highly scalable architecture for AI Agents using the **Model Context Protocol (MCP)**. 

Instead of registering all MCP tools natively to the LLM at startup (which consumes massive context tokens and causes hallucination at scale), this architecture wraps MCP servers inside a "**Skill Directory**". The Agent lazy-loads the MCP tools *only* when it explicitly decides it needs them.

## 🚀 Key Benefits
1. **Zero Context Bloat**: When idle, the LLM context only contains lightweight metadata (catalog) of available skills.
2. **Infinite Scaling**: You can have 100+ MCP Servers running. The LLM won't be overwhelmed by 1000+ tool schemas because it specifically "mounts" connections one at a time via `activate_skill`.
3. **Reasoning Guardrails**: Each skill comes with a `SKILL.md` that injects guidelines to the LLM on *how* to use the specifically mounted tools, drastically reducing errors.

## 🧠 How It Works
1. **Startup**: `SkillManager` scans the `skills/` directory and reads lightweight YAML frontmatter. No MCP servers are started.
2. **System Prompt**: The LLM receives a catalog of available skills and one base tool: `activate_skill(name)`.
3. **Execution**: The user asks a question. The LLM realizes it needs external capabilities and calls `activate_skill("mcp-math")`.
4. **Mounting**: The framework reads the full `SKILL.md`, hooks to the `MCPClientManager`, starts the specific MCP server via `stdio`, and binds the new tools specifically for this conversation string.

## 🛠 Project Structure
```text
├── agent.py                  # Main ReAct loop and tool router
├── config.py                 # OpenRouter API & MCP Server configurations
├── framework/
│   └── skill_manager.py      # Handles lazy-loading metadata and triggers activation hooks
├── mcp_servers/              # Independent MCP native servers
│   ├── server_filesystem.py  # (Read-only disk access)
│   └── server_math.py        # (Math tools)
└── skills/
    └── use_mcp/              
        ├── mcp_client.py     # Python Client to manage MCP stdio lifecycles
        ├── SKILL.md          # Base instructions for MCP routing
        ├── mcp-math/         # 1-to-1 Mapping to internal Math MCP 
        │   └── SKILL.md
        └── mcp-filesystem/   # 1-to-1 Mapping to internal Filesystem MCP
            └── SKILL.md
```

## ⚙️ Quickstart

### 1. Set Up Environment
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
*Note: Ensure to add your OpenRouter API Key in the `.env` file.*

### 2. Run the Agent
Run the main loop to see lazy-loading in action:
```bash
python agent.py
```

Try asking:
- *"Hitung fibonacci ke 10"* (Watch as it mounts the math server).
- *"Coba cek file apa aja yang ada"* (Watch as it mounts the filesystem server).

### 3. Run Integration Tests
Validates the skill registry, catalog generation, hook triggers, and the full MCP tool injection lifecycle:
```bash
python test_integration.py
```
