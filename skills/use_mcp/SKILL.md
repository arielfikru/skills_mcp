---
name: use-mcp
version: 1.0.0
description: >
  Skill Master untuk menggunakan Model Context Protocol (MCP).
  Ini adalah panduan utama tentang cara menggunakan sub-skill MCP (mcp-math, mcp-filesystem, dll).
tags: [mcp, tools, integration, core]
---

# Master Skill: use-mcp

Skill ini memberikan instruksi dasar tentang cara kamu berinteraksi dengan tools eksternal via arsitektur MCP.

**PENTING:** Skill ini *tidak memberikan tools langsung*. Untuk mendapatkan tools, kamu harus memanggil (activate) sub-skill secara individual.

## Cara Kerja
1. Jika kamu perlu kalkulasi, panggil `activate_skill("mcp-math")`.
2. Jika kamu perlu membaca file, panggil `activate_skill("mcp-filesystem")`.
3. Setelah sub-skill aktif, tools baru akan masuk ke sistemmu.

Selalu gunakan sub-skill yang paling relevan saja untuk menghemat token dan menjaga efisiensi memory.
