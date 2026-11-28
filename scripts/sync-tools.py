#!/usr/bin/env python3
"""
Sync mcp/tools.mdx from the MagicPost MCP server's tools/list output.

Hits https://mcp.magicpost.in/mcp with a valid PAT, lists all registered
tools, then regenerates mcp/tools.mdx as a single deterministic file.

Usage:
    MAGICPOST_PAT=mp_xxx python scripts/sync-tools.py
    python scripts/sync-tools.py --from tools.json   # local backend, before deploy

`tools.json` is the `tools` array of tools/list as an org admin, dumped from
the backend repo: `PYTHONPATH=. python scripts/dump_mcp_tools.py tools.json`.

The PAT only needs to be valid — it's not stored — but it must belong to an
org admin whose organisation is not limited to analytics: tools/list is
fitted to the caller (mcp_server/catalogue.py), and any other account gets a
page without the organisation tools and the `member_user_id` inputs. Use a
dedicated key named "docs-sync" for this if you want to revoke it independently.

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
import re
import sys
from pathlib import Path
from typing import Any

import httpx

MCP_URL = os.environ.get("MAGICPOST_MCP_URL", "https://mcp.magicpost.in/mcp")
ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "mcp" / "tools.mdx"
OVERVIEW = ROOT / "mcp" / "overview.mdx"
INTRO = ROOT / "introduction.mdx"

# ponytail: name→category map is the ONLY thing to touch when a tool is added.
# tools/list carries no category, so we group by name here (mirrors the backend
# mcp_server/tools/*.py files). An unmapped tool lands in "Other" + a warning —
# never silently dropped. The order of keys is the display order.
CATEGORIES: dict[str, list[str]] = {
    "Generation & styles": [
        "generate_post", "list_templates", "list_my_writing_styles",
        "find_writing_style_profile", "add_writing_style_profile",
        "get_generation_settings", "manage_generation_settings",
    ],
    "Posts": [
        "list_my_posts", "get_post", "create_or_update_post",
        "attach_media_to_post", "prepare_post_media_upload",
        "complete_post_media_upload", "update_post_media", "remove_post_media",
        "create_media_drop_link", "attach_html_slides", "score_post",
        "delete_post", "duplicate_post", "list_labels", "manage_labels", "import_linkedin_post",
        "search_mentions", "list_recent_mentions",
    ],
    "Scheduling & calendar": [
        "schedule_post", "cancel_scheduled_post", "publish_post_now",
        "schedule_post_comment", "delete_post_comment",
        "get_calendar", "manage_calendar_idea", "get_recommended_posting_times",
    ],
    "Post discussion & approval": ["list_post_discussion", "manage_post_discussion"],
    "Ideas": [
        "add_idea_to_notebook", "list_notebook_ideas", "get_notebook_idea",
        "manage_notebook_idea", "manage_idea_attachment", "manage_notebook_columns",
        "get_idea_generator", "manage_idea_sources", "generate_ideas",
        "manage_generated_idea", "update_idea_generator_settings",
    ],
    "Media library & collections": [
        "list_media_library", "get_media_library_overview", "manage_media_folder",
        "manage_media_asset", "attach_library_media_to_post",
        "list_collections", "manage_collection",
    ],
    "Comments & engagement": [
        "list_received_comments", "sync_received_comments", "reply_to_comment",
        "engage_with_post", "list_engagement_queue", "cancel_queued_engagement",
        "get_engagement_feed", "get_engagement_activity", "manage_engagement_feed",
        "list_engagement_lists", "manage_engagement_list",
        "manage_engagement_gesture", "list_comment_bookmarks", "manage_comment_bookmarks",
        "get_engagement_recommendations",
    ],
    "Analytics & insights": [
        "list_linkedin_post_metrics", "get_metrics_summary",
        "get_metrics_freshness", "refresh_my_posts",
        "get_insights", "manage_audience_analysis",
    ],
    "Inspiration": ["search_inspiration_posts"],
    "Leads & CRM": [
        "list_leads", "get_lead", "list_icps", "get_leads_summary",
        "get_detection_status", "detect_leads", "update_lead",
        "suggest_icps", "create_icp", "update_icp", "get_icp", "manage_icp",
        "score_icp_leads", "manage_icp_leads", "preview_icp_audience",
        "list_lead_exclusions", "manage_lead_exclusions", "get_lead_credit_history",
        "list_crm_connections", "manage_crm_connections", "send_leads_to_crm",
    ],
    "Org / team": [
        "list_org_members", "get_org_metrics_summary", "list_org_member_posts",
        "get_org_member_post", "create_member_post", "schedule_member_post",
        "add_member_idea_to_notebook", "list_org_leads", "list_org_icps",
        "get_team_activity", "list_org_groups", "manage_org_group",
    ],
}


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


# A `code span` (one or more backticks ... matching backticks). Anything
# inside is verbatim source, so MDX never interprets `<` or `{` there.
_CODE_SPAN = re.compile(r"`+[^`]*`+")


def escape_mdx(text: str) -> str:
    """Make a backend docstring safe to embed verbatim in an MDX page.

    Outside code spans, MDX treats `<` as the start of a JSX tag and `{` as
    the start of a JS expression. A raw docstring like "posts about <topic>"
    or "subset of {a, b}" therefore either fails to build (unclosed tag) or
    crashes the page at hydration (undefined identifiers). Backslash-escape
    those three characters in the prose parts while leaving intentional code
    spans untouched.
    """
    out: list[str] = []
    last = 0
    for match in _CODE_SPAN.finditer(text):
        out.append(_escape_plain(text[last : match.start()]))
        out.append(match.group(0))  # keep the code span verbatim
        last = match.end()
    out.append(_escape_plain(text[last:]))
    return "".join(out)


def _escape_plain(segment: str) -> str:
    return segment.replace("<", "\\<").replace("{", "\\{").replace("}", "\\}")


def render_tool_section(tool: dict[str, Any]) -> str:
    name = tool["name"]
    description = escape_mdx((tool.get("description") or "").strip())
    schema = tool.get("inputSchema") or {}
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])

    rows = []
    for prop_name, prop_schema in props.items():
        ptype = _schema_type(prop_schema)
        default = prop_schema.get("default")
        default_str = "—" if prop_name in required else _format_default(default)
        # The server no longer serves Pydantic's generated `title` (dropped
        # from tools/list to lighten the catalogue, mcp_server/catalogue.py):
        # rebuild it the way Pydantic did, so an undocumented input keeps a label.
        desc = (
            prop_schema.get("description")
            or prop_schema.get("title")
            or prop_name.replace("_", " ").title()
        )
        desc = escape_mdx(desc).replace("|", "\\|").replace("\n", " ")
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


def _schema_type(prop: dict[str, Any]) -> str:
    direct = prop.get("type")
    if direct:
        return direct
    enum = _enum_summary(prop)
    if enum:
        return enum
    reference = _reference_name(prop)
    if reference:
        return reference
    variants = prop.get("anyOf")
    if isinstance(variants, list):
        rendered = [_schema_type(item) for item in variants if isinstance(item, dict)]
        if rendered:
            return " \\| ".join(dict.fromkeys(rendered))
    return "any"


def _enum_summary(prop: dict[str, Any]) -> str | None:
    if "enum" in prop:
        return " \\| ".join(f"'{v}'" for v in prop["enum"])
    return None


def _reference_name(prop: dict[str, Any]) -> str | None:
    reference = prop.get("$ref")
    if not isinstance(reference, str):
        return None
    return reference.rsplit("/", 1)[-1]


def _format_default(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return f"`{str(value).lower()}`"
    return f"`{value!r}`"


def purpose(tool: dict[str, Any]) -> str:
    """One-line purpose for the overview table: the first sentence of the
    docstring's opening paragraph (docstrings are hard-wrapped, so we join the
    paragraph before cutting at the first sentence)."""
    desc = (tool.get("description") or "").strip()
    para: list[str] = []
    for line in desc.splitlines():
        if not line.strip():
            break
        para.append(line.strip())
    text = " ".join(para)
    if ". " in text:
        text = text.split(". ", 1)[0] + "."
    return escape_mdx(text).replace("|", "\\|")


def build_overview_table(tools: list[dict[str, Any]]) -> str:
    by_name = {t["name"]: t for t in tools}
    seen: set[str] = set()
    blocks: list[str] = []
    for label, names in CATEGORIES.items():
        rows = []
        for name in names:
            tool = by_name.get(name)
            if not tool:  # removed backend-side → legitimately drops from docs
                continue
            seen.add(name)
            rows.append(f"| `{name}` | {purpose(tool)} |")
        if rows:
            blocks.append(f"#### {label}\n\n| Tool | Purpose |\n|---|---|\n" + "\n".join(rows))
    leftover = [t for t in tools if t["name"] not in seen]
    if leftover:
        names = ", ".join(t["name"] for t in leftover)
        print(f"⚠️  {len(leftover)} unmapped tool(s) → 'Other'; add to CATEGORIES: {names}",
              file=sys.stderr)
        rows = [f"| `{t['name']}` | {purpose(t)} |" for t in leftover]
        blocks.append("#### Other\n\n| Tool | Purpose |\n|---|---|\n" + "\n".join(rows))
    return "\n\n".join(blocks)


def patch_markers(path: Path, tag: str, inner: str) -> None:
    """Replace every `{/* tag */}…{/* /tag */}` region in an MDX file with
    `inner`, markers kept intact so the next run matches again."""
    txt = path.read_text(encoding="utf-8")
    open_t, close_t = f"{{/* {tag} */}}", f"{{/* /{tag} */}}"
    pat = re.compile(re.escape(open_t) + r".*?" + re.escape(close_t), re.S)
    if not pat.search(txt):
        raise SystemExit(f"marker '{tag}' not found in {path.name}")
    # lambda replacement → backslashes in `inner` are kept literal (no \1 etc.)
    path.write_text(pat.sub(lambda _m: open_t + inner + close_t, txt), encoding="utf-8")


# Pages with a `{/* tools:count */}` marker that must track the tool count.
COUNT_PAGES = [
    INTRO,
    OVERVIEW,
    ROOT / "mcp" / "setup-cursor.mdx",
    ROOT / "mcp" / "setup-claude-desktop.mdx",
    ROOT / "mcp" / "setup-other-assistants.mdx",
    ROOT / "mcp" / "client-assistant.mdx",
]


def sync_overview(tools: list[dict[str, Any]]) -> None:
    count = str(len(tools))
    for page in COUNT_PAGES:
        patch_markers(page, "tools:count", count)
    patch_markers(OVERVIEW, "tools:table", "\n\n" + build_overview_table(tools) + "\n\n")
    print(f"✅ Patched {len(COUNT_PAGES)} page(s) + overview table (count={count})")


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
    # `--from <file>`: a tools/list result already dumped (the `tools` array),
    # e.g. from a local backend before it is deployed, as an org admin.
    if len(sys.argv) == 3 and sys.argv[1] == "--from":
        tools = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    else:
        pat = os.environ.get("MAGICPOST_PAT")
        if not pat:
            print("error: MAGICPOST_PAT env var (or --from <tools.json>) is required", file=sys.stderr)
            return 1
        tools = fetch_tools(pat)
    if not tools:
        print("error: MCP server returned no tools", file=sys.stderr)
        return 1

    sections = "\n\n---\n\n".join(render_tool_section(t) for t in tools)
    OUTPUT.write_text(HEADER + sections + "\n", encoding="utf-8")
    print(f"✅ Wrote {len(tools)} tool(s) to {OUTPUT.relative_to(OUTPUT.parent.parent)}")

    sync_overview(tools)
    return 0


if __name__ == "__main__":
    sys.exit(main())
