---
name: mcp-filesystem
version: 1.0.0
description: Skill MCP spesifik untuk menyediakan akses Read-Only pada filesystem lokal project.
tags: [mcp, file, folder, disk, read]
---

# Sub-Skill: mcp-filesystem

Skill ini mengamankan koneksi ke MCP Server Filesystem. Begitu skill ini diaktifkan, kamu akan mendapatkan tools dengan prefix `filesystem__`.

## Tools yang Tersedia:
- `filesystem__list_directory`: Melihat daftar file & folder.
- `filesystem__read_file`: Membaca isi text dari suatu file (max 500 baris).
- `filesystem__file_info`: Mendapatkan info metadata suatu file.

Pastikan kamu mengecek daftar file dulu dengan `list_directory` jika bingung nama filenya apa.
