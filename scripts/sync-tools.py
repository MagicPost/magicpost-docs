#!/usr/bin/env python3
"""
Sync mcp/tools.mdx from the MagicPost MCP server's tools/list output.

Hits https://mcp.magicpost.in/mcp with a valid PAT, lists all registered
tools, then regenerates mcp/tools.mdx as a single deterministic file.

Usage:
    MAGICPOST_PAT=mp_xxx python scripts/sync-tools.py

The PAT only needs to be valid — it's not stored. Use a dedicated key
named "docs-sync" for this if you want to revoke it independently.

Run it whenever:
    - You add or rename a tool in mcp_server/tools/*.py
    - You change a tool's docstring (the doc page uses it as description)
    - You change a tool's input schema (Literal, defaults, required fields)

If the diff after running is non-empty, commit it before merging the backend
change. The CI checks this file is in sync.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

MCP_URL = os.environ.get("MAGICPOST_MCP_URL", "https://mcp.magicpost.in/mcp")
OUTPUT = Path(__file__).resolve().parent.parent / "mcp" / "tools.mdx"


def fetch_tools(pat: str) -> list[dict[str, Any]]:
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 1,
    }
    headers = {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    resp = httpx.post(MCP_URL, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise SystemExit(f"MCP server error: {data['error']}")
    return data["result"]["tools"]


def render_tool_section(tool: dict[str, Any]) -> str:
    name = tool["name"]
    description = (tool.get("description") or "").strip()
    schema = tool.get("inputSchema") or {}
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])

    rows = []
    for prop_name, prop_schema in props.items():
        ptype = prop_schema.get("type") or _enum_summary(prop_schema) or "any"
        default = prop_schema.get("default")
        default_str = "—" if prop_name in required else _format_default(default)
        desc = prop_schema.get("description") or prop_schema.get("title") or ""
        rows.append(f"| `{prop_name}` | `{ptype}` | {default_str} | {desc} |")

    if rows:
        table = "\n".join(
            ["| Input | Type | Default | Description |", "|---|---|---|---|", *rows]
        )
    else:
        table = "_No inputs._"

    return f"""## {name}

{description}

{table}
"""


def _enum_summary(prop: dict[str, Any]) -> str | None:
    if "enum" in prop:
        return " \\| ".join(f"'{v}'" for v in prop["enum"])
    return None


def _format_default(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return f"`{str(value).lower()}`"
    return f"`{value!r}`"


HEADER = """---
title: "Tools catalog"
description: "The MCP tools — inputs, outputs, examples."
icon: "wrench"
---

<Note>
  This page is auto-generated from the MCP server's `tools/list`. Run
  `scripts/sync-tools.py` after backend changes to refresh it.
</Note>

"""


def main() -> int:
    pat = os.environ.get("MAGICPOST_PAT")
    if not pat:
        print("error: MAGICPOST_PAT env var is required", file=sys.stderr)
        return 1

    tools = fetch_tools(pat)
    if not tools:
        print("error: MCP server returned no tools", file=sys.stderr)
        return 1

    sections = "\n\n---\n\n".join(render_tool_section(t) for t in tools)
    OUTPUT.write_text(HEADER + sections + "\n", encoding="utf-8")
    print(f"✅ Wrote {len(tools)} tool(s) to {OUTPUT.relative_to(OUTPUT.parent.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
