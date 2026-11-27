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
quickstart.mdx             # 3-step setup, by sign-in
essentials/
  authentication.mdx       # sign-in, API keys, scopes, rotation
  errors.mdx               # error_type catalog + rate limits
mcp/
  overview.mdx
  setup-claude-desktop.mdx # Claude (claude.ai, desktop, mobile)
  setup-claude-code.mdx
  setup-cursor.mdx
  setup-other-assistants.mdx # ChatGPT, Gemini, Perplexity, Grok, Mistral, Codex
  media-attachments.mdx
  client-assistant.mdx     # second catalogue, for an agency's client
  tools.mdx                # auto-generated, see scripts/sync-tools.py
api-reference/
  overview.mdx
  api-keys.mdx
  metrics.mdx
  organization.mdx         # org admin endpoints
  posts.mdx
  scheduling.mdx
scripts/
  sync-tools.py            # regenerates mcp/tools.mdx from /mcp tools/list
.github/workflows/
  sync-tools.yml           # runs sync-tools.py every day
```

## Updating after a backend change

When a tool's name, inputs, or docstring changes in `magicpost/api-staging`
(`mcp_server/tools/*.py`):

```bash
MAGICPOST_PAT=mp_xxx python scripts/sync-tools.py
git diff mcp/tools.mdx
git commit -am "docs(tools): sync from MCP server"
```

The PAT only needs `mcp:v1` scope, but it must belong to an **org admin**
(an account that manages members of an organisation) whose organisation is
not limited to analytics: `tools/list` is fitted to the caller, and any other
account gets a page without the organisation tools and without the
`member_user_id` inputs. Use a dedicated key named `docs-sync` so you can
revoke it independently.

### Automatic sync

`.github/workflows/sync-tools.yml` runs the same script every day (and on
demand from the Actions tab) and commits the result to `main`, which deploys
it. It needs one repository secret, `MAGICPOST_PAT`, holding the dedicated
`docs-sync` key described above:

```bash
gh secret set MAGICPOST_PAT -R MagicPost/magicpost-docs
```

Without the secret the workflow does nothing. It refuses to publish a catalog
with fewer tools than the current one: `tools/list` is fitted to the caller, so
a shorter list usually means the key's account lost its admin role.

A new page that shows the tool count needs the `{/* tools:count */}` marker and
an entry in `COUNT_PAGES` of `scripts/sync-tools.py`.

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
