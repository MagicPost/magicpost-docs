# MagicPost developer docs

Public documentation for the MagicPost REST API and MCP server. Served by
[Mintlify](https://mintlify.com) at **https://dev.magicpost.in** (target).

## Local preview

```bash
npm i -g mint
mint dev
# → http://localhost:3000
```

## Project layout

```
docs.json                  # Mintlify config (navigation, theme, domain)
introduction.mdx           # landing
quickstart.mdx             # 3-step setup
essentials/
  authentication.mdx       # PATs, scopes, rotation
  errors.mdx               # error_type catalog + rate limits
mcp/
  overview.mdx
  setup-claude-desktop.mdx
  setup-cursor.mdx
  tools.mdx                # auto-generated, see scripts/sync-tools.py
api-reference/
  overview.mdx
  api-keys.mdx
  metrics.mdx
  posts.mdx
  scheduling.mdx
scripts/
  sync-tools.py            # regenerates mcp/tools.mdx from /mcp tools/list
```

## Updating after a backend change

When a tool's name, inputs, or docstring changes in `magicpost/api-staging`
(`mcp_server/tools/*.py`):

```bash
MAGICPOST_PAT=mp_xxx python scripts/sync-tools.py
git diff mcp/tools.mdx
git commit -am "docs(tools): sync from MCP server"
```

The PAT only needs `mcp:v1` scope. Use a dedicated key named `docs-sync` so
you can revoke it independently.

When a REST endpoint changes (path, params, response shape), edit the
matching `api-reference/<group>.mdx` by hand — these are written manually for
now (an OpenAPI integration is planned).

## Deploy

Connected to Mintlify via GitHub. Pushes to `main` deploy to production
(`dev.magicpost.in`). PR previews are auto-built and linked in the PR.

## Custom domain

CNAME `dev.magicpost.in` → `cname.vercel-dns.com` (Mintlify uses Vercel).
Configured in Cloudflare → DNS, **DNS only** mode (no proxy, to avoid
double SSL termination).
