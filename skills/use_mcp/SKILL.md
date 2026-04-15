---
name: use-mcp
version: 1.0.0
description: >
  Master skill for the Model Context Protocol (MCP).
  This acts as the primary registry and base guidelines for interacting with sub-skills (mcp-math, mcp-filesystem, etc).
tags: [mcp, tools, integration, core]
---

# Master Skill: use-mcp

This skill provides foundational instructions on how to interact with external tools via the MCP architecture.

**IMPORTANT:** This skill *does not provide direct tools*. To access tools, you must activate the specific sub-skills individually.

## Workflow
1. If you need calculations, call `activate_skill("mcp-math")`.
2. If you need to read local files, call `activate_skill("mcp-filesystem")`.
3. Once the sub-skill is activated, the new tools will be dynamically injected into your context.

Always use the most relevant sub-skill to conserve context tokens and maintain memory efficiency. Avoid activating skills unless their explicitly stated capabilities are needed.
