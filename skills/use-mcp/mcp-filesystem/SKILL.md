---
name: mcp-filesystem
version: 1.0.0
description: Specific MCP skill providing Read-Only access to the local project filesystem.
tags: [mcp, file, folder, disk, read]
---

# Sub-Skill: mcp-filesystem

This skill establishes a secure connection to the Filesystem MCP Server. Once activated, you will receive tools prefixed with `filesystem__`.

## Available Tools:
- `filesystem__list_directory`: View the contents of a directory.
- `filesystem__read_file`: Read the text contents of a file (max 500 lines).
- `filesystem__file_info`: Retrieve metadata information for a specific file.

It is highly recommended to use `list_directory` first to verify exact file paths before attempting to read them.
