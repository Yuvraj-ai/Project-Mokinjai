# CLI Agent Full Setup Guide

This document records the exact setup applied to this Codex environment on
2026-05-07. It is intended as a private, local reference for reproducing the
same agent stack in Codex or adapting it to other coding CLI tools.

Security note: this file contains live API keys and bearer tokens. Keep it out
of git, do not paste it into public chats, and keep file permissions restricted
to the local user.

## 1. Final Capability Stack

The configured stack has three layers:

1. Codex plugins and built-in skills.
2. User-installed local skills from `claudegod`.
3. MCP servers for docs, memory, filesystem access, browser testing, and live
   web search/research.

## 2. Prerequisites

Install or verify these local runtimes:

```bash
node --version
npx --version
uvx --version
python3 --version
codex --version
```

The machine used for this setup had:

```text
node: v25.9.0
npx: /usr/bin/npx
uvx: /home/imyuvi/.local/bin/uvx
python3: Python 3.14.4
```

Codex MCP configuration lives at:

```text
/home/imyuvi/.codex/config.toml
```

User skills live at:

```text
/home/imyuvi/.codex/skills/
```

## 3. Enabled Codex Plugins

These plugins were enabled in `config.toml`:

```toml
[plugins."superpowers@openai-curated"]
enabled = true

[plugins."build-web-apps@openai-curated"]
enabled = true

[plugins."temporal@openai-curated"]
enabled = true
```

Plugin purpose:

- `superpowers@openai-curated`: planning, debugging, TDD, verification, branch
  completion, subagent workflows.
- `build-web-apps@openai-curated`: frontend app building, browser testing,
  React/Next.js, shadcn, Stripe, Supabase/Postgres guidance.
- `temporal@openai-curated`: Temporal workflow, activity, worker, and durable
  execution development.

## 4. Memory Settings

Codex memory was enabled:

```toml
[features]
memories = true

[memories]
generate_memories = true
use_memories = true
```

The local memory directory is:

```text
/home/imyuvi/.codex/memories/
```

## 5. MCP Servers Added

The following MCP servers were configured.

| MCP | Purpose | Auth |
| --- | --- | --- |
| `context7` | Live library documentation | No key required |
| `basic-memory` | Local persistent markdown memory | No key required |
| `filesystem` | Structured local file access | No key required |
| `fetch` | Fetch and parse URLs | No key required |
| `playwright` | Browser automation and E2E testing | No key required |
| `tavily` | Web search and extraction | `TAVILY_API_KEY` |
| `exa` | Web search, code context, crawling, research | `EXA_API_KEY` |
| `jina` | Reader/search/fetch tools via Jina MCP | Bearer token |
| `linkup` | Web search and page fetch | Bearer token |
| `duckduckgo` | No-key fallback web search | No key required |
| `sourcegraph` | Sourcegraph MCP endpoint | No key configured |

## 6. API Keys Used

These are the exact credentials provided during setup.

```bash
export TAVILY_API_KEY="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"
export EXA_API_KEY="fbadb4ec-8107-4491-9267-45da01c3187d"
export JINA_API_KEY="jina_042c7cf489404fe6acc150ef0290720cEYQILIfaDhtu-9FGX6Czp2cVN9He"
export LINKUP_API_KEY="fb0580bd-dd31-4660-aee9-ab750ad37406"
```

Tavily, Exa, Jina, and Linkup all require these credentials for the configured
authenticated tools.

## 7. Exact Codex Configuration

Place this in:

```text
/home/imyuvi/.codex/config.toml
```

Full configuration:

```toml
model = "gpt-5.5"
model_reasoning_effort = "high"

[projects."/run/media/imyuvi/New Volume/randomFolio/digital-consciousness"]
trust_level = "trusted"

[projects."/run/media/imyuvi/New Volume/mokinjay project"]
trust_level = "trusted"

[projects."/home/imyuvi"]
trust_level = "trusted"

[features]
memories = true

[memories]
generate_memories = true
use_memories = true

[plugins."superpowers@openai-curated"]
enabled = true

[plugins."build-web-apps@openai-curated"]
enabled = true

[plugins."temporal@openai-curated"]
enabled = true

[mcp_servers.context7]
url = "https://mcp.context7.com/mcp"

[mcp_servers.basic-memory]
command = "uvx"
args = ["basic-memory", "mcp"]

[mcp_servers.filesystem]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-filesystem", "/home/imyuvi"]

[mcp_servers.fetch]
command = "uvx"
args = ["mcp-server-fetch"]

[mcp_servers.playwright]
command = "npx"
args = ["@playwright/mcp@latest", "--headless"]

[mcp_servers.tavily]
command = "npx"
args = ["-y", "tavily-mcp@latest"]
enabled = true

[mcp_servers.tavily.env]
TAVILY_API_KEY = "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"

[mcp_servers.exa]
command = "npx"
args = ["-y", "exa-mcp-server", "tools=web_search_exa,web_search_advanced_exa,get_code_context_exa,crawling_exa,company_research_exa,people_search_exa,deep_researcher_start,deep_researcher_check"]
enabled = true

[mcp_servers.exa.env]
EXA_API_KEY = "fbadb4ec-8107-4491-9267-45da01c3187d"

[mcp_servers.jina]
url = "https://mcp.jina.ai/v1"
enabled = true

[mcp_servers.jina.http_headers]
Authorization = "Bearer jina_042c7cf489404fe6acc150ef0290720cEYQILIfaDhtu-9FGX6Czp2cVN9He"

[mcp_servers.linkup]
url = "https://mcp.linkup.so/mcp"
enabled = true

[mcp_servers.linkup.http_headers]
Authorization = "Bearer fb0580bd-dd31-4660-aee9-ab750ad37406"

[mcp_servers.duckduckgo]
command = "npx"
args = ["-y", "duckduckgo-mcp-server"]
enabled = true

[mcp_servers.sourcegraph]
url = "https://sourcegraph.com/.api/mcp"
enabled = true

[tui.model_availability_nux]
"gpt-5.5" = 1
```

Lock down the config file:

```bash
chmod 600 /home/imyuvi/.codex/config.toml
```

## 8. MCP Setup Commands

The direct `codex mcp add` command failed in this environment because Codex
could not persist its temporary config file inside the sandbox:

```text
failed to persist config.toml at /home/imyuvi/.codex/config.toml
Read-only file system
```

The working approach was to patch `/home/imyuvi/.codex/config.toml` directly.

For a normal unrestricted terminal, these commands are the rough equivalents.
Use direct TOML editing if any command cannot persist.

```bash
codex mcp add context7 --url https://mcp.context7.com/mcp

codex mcp add basic-memory -- uvx basic-memory mcp

codex mcp add filesystem -- npx -y @modelcontextprotocol/server-filesystem /home/imyuvi

codex mcp add fetch -- uvx mcp-server-fetch

codex mcp add playwright -- npx @playwright/mcp@latest --headless

codex mcp add tavily \
  --env TAVILY_API_KEY="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" \
  -- npx -y tavily-mcp@latest

codex mcp add exa \
  --env EXA_API_KEY="fbadb4ec-8107-4491-9267-45da01c3187d" \
  -- npx -y exa-mcp-server \
  "tools=web_search_exa,web_search_advanced_exa,get_code_context_exa,crawling_exa,company_research_exa,people_search_exa,deep_researcher_start,deep_researcher_check"

codex mcp add duckduckgo -- npx -y duckduckgo-mcp-server

codex mcp add sourcegraph --url "https://sourcegraph.com/.api/mcp"
```

For Jina and Linkup, the exact setup used static bearer headers in TOML:

```toml
[mcp_servers.jina]
url = "https://mcp.jina.ai/v1"
enabled = true

[mcp_servers.jina.http_headers]
Authorization = "Bearer jina_042c7cf489404fe6acc150ef0290720cEYQILIfaDhtu-9FGX6Czp2cVN9He"

[mcp_servers.linkup]
url = "https://mcp.linkup.so/mcp"
enabled = true

[mcp_servers.linkup.http_headers]
Authorization = "Bearer fb0580bd-dd31-4660-aee9-ab750ad37406"
```

Alternative environment-variable style for Jina and Linkup:

```toml
[mcp_servers.jina]
url = "https://mcp.jina.ai/v1"
env_http_headers = { "Authorization" = "JINA_AUTH_HEADER" }

[mcp_servers.linkup]
url = "https://mcp.linkup.so/mcp"
bearer_token_env_var = "LINKUP_API_KEY"
```

Then:

```bash
export JINA_AUTH_HEADER="Bearer jina_042c7cf489404fe6acc150ef0290720cEYQILIfaDhtu-9FGX6Czp2cVN9He"
export LINKUP_API_KEY="fb0580bd-dd31-4660-aee9-ab750ad37406"
```

## 9. Verification

Run:

```bash
codex mcp list
```

Expected configured servers:

```text
basic-memory
duckduckgo
exa
fetch
filesystem
playwright
tavily
context7
jina
linkup
sourcegraph
```

Expected behavior:

- `tavily` shows `TAVILY_API_KEY=*****`.
- `exa` shows `EXA_API_KEY=*****`.
- `jina` shows bearer-token auth.
- `linkup` shows bearer-token auth.
- All servers show `enabled`.

Important: MCP servers added to `config.toml` are loaded when Codex starts.
If they do not appear in the active tool registry, restart Codex.

## 10. User Skills Installed

Local source directory:

```text
/home/imyuvi/Downloads/claudegod/skills/
```

Destination directory:

```text
/home/imyuvi/.codex/skills/
```

Installed skills:

```text
god-audit
god-cicd
god-execute
god-fix
god-plan
god-qa
god-release
```

Exact copy command used:

```bash
cp -a \
  /home/imyuvi/Downloads/claudegod/skills/god-audit \
  /home/imyuvi/Downloads/claudegod/skills/god-cicd \
  /home/imyuvi/Downloads/claudegod/skills/god-execute \
  /home/imyuvi/Downloads/claudegod/skills/god-fix \
  /home/imyuvi/Downloads/claudegod/skills/god-plan \
  /home/imyuvi/Downloads/claudegod/skills/god-qa \
  /home/imyuvi/Downloads/claudegod/skills/god-release \
  /home/imyuvi/.codex/skills/
```

Verify:

```bash
find /home/imyuvi/.codex/skills -maxdepth 2 -name SKILL.md -print
```

Expected output:

```text
/home/imyuvi/.codex/skills/god-audit/SKILL.md
/home/imyuvi/.codex/skills/god-cicd/SKILL.md
/home/imyuvi/.codex/skills/god-execute/SKILL.md
/home/imyuvi/.codex/skills/god-fix/SKILL.md
/home/imyuvi/.codex/skills/god-plan/SKILL.md
/home/imyuvi/.codex/skills/god-qa/SKILL.md
/home/imyuvi/.codex/skills/god-release/SKILL.md
```

Note: `god-release` appeared to be a placeholder skill at install time, but it
was copied because it was present in the source directory.

Restart Codex to pick up newly installed skills.

## 11. How to Adapt This to Claude Desktop

Claude Desktop usually uses JSON config at one of these locations:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux paths vary by distribution/package.

Example MCP JSON equivalent:

```json
{
  "mcpServers": {
    "context7": {
      "url": "https://mcp.context7.com/mcp"
    },
    "basic-memory": {
      "command": "uvx",
      "args": ["basic-memory", "mcp"]
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/imyuvi"]
    },
    "fetch": {
      "command": "uvx",
      "args": ["mcp-server-fetch"]
    },
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest", "--headless"]
    },
    "tavily": {
      "command": "npx",
      "args": ["-y", "tavily-mcp@latest"],
      "env": {
        "TAVILY_API_KEY": "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"
      }
    },
    "exa": {
      "command": "npx",
      "args": [
        "-y",
        "exa-mcp-server",
        "tools=web_search_exa,web_search_advanced_exa,get_code_context_exa,crawling_exa,company_research_exa,people_search_exa,deep_researcher_start,deep_researcher_check"
      ],
      "env": {
        "EXA_API_KEY": "fbadb4ec-8107-4491-9267-45da01c3187d"
      }
    },
    "jina": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://mcp.jina.ai/v1",
        "--header",
        "Authorization: Bearer jina_042c7cf489404fe6acc150ef0290720cEYQILIfaDhtu-9FGX6Czp2cVN9He"
      ]
    },
    "linkup": {
      "command": "npx",
      "args": [
        "-y",
        "linkup-mcp-server",
        "apiKey=fb0580bd-dd31-4660-aee9-ab750ad37406"
      ]
    },
    "duckduckgo": {
      "command": "npx",
      "args": ["-y", "duckduckgo-mcp-server"]
    }
  }
}
```

Sourcegraph can be added as a remote MCP if the client supports HTTP MCP:

```json
{
  "sourcegraph": {
    "url": "https://sourcegraph.com/.api/mcp"
  }
}
```

If the client only supports stdio, use `mcp-remote`:

```json
{
  "sourcegraph": {
    "command": "npx",
    "args": ["-y", "mcp-remote", "https://sourcegraph.com/.api/mcp"]
  }
}
```

## 12. How to Adapt This to Cursor or VS Code MCP Config

Cursor and VS Code typically accept an `mcpServers` or `servers` JSON object.
Use the same server commands from the Claude Desktop section.

HTTP MCP entries generally look like:

```json
{
  "mcpServers": {
    "context7": {
      "url": "https://mcp.context7.com/mcp"
    },
    "jina": {
      "url": "https://mcp.jina.ai/v1",
      "headers": {
        "Authorization": "Bearer jina_042c7cf489404fe6acc150ef0290720cEYQILIfaDhtu-9FGX6Czp2cVN9He"
      }
    },
    "linkup": {
      "url": "https://mcp.linkup.so/mcp",
      "headers": {
        "Authorization": "Bearer fb0580bd-dd31-4660-aee9-ab750ad37406"
      }
    }
  }
}
```

Stdio entries generally look like:

```json
{
  "mcpServers": {
    "tavily": {
      "command": "npx",
      "args": ["-y", "tavily-mcp@latest"],
      "env": {
        "TAVILY_API_KEY": "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"
      }
    },
    "exa": {
      "command": "npx",
      "args": [
        "-y",
        "exa-mcp-server",
        "tools=web_search_exa,web_search_advanced_exa,get_code_context_exa,crawling_exa,company_research_exa,people_search_exa,deep_researcher_start,deep_researcher_check"
      ],
      "env": {
        "EXA_API_KEY": "fbadb4ec-8107-4491-9267-45da01c3187d"
      }
    },
    "duckduckgo": {
      "command": "npx",
      "args": ["-y", "duckduckgo-mcp-server"]
    }
  }
}
```

## 13. Recommended Agent Usage Pattern

Use MCPs by job:

- Library docs: `context7`.
- Project memory: Codex memory plus `basic-memory`.
- Local repo navigation: native shell, `filesystem`, and `rg`.
- Current web research: `tavily`, `exa`, `linkup`, `jina`, then
  `duckduckgo` as fallback.
- Code examples and package/API usage: `exa` code-context plus `context7`.
- Browser UI/E2E verification: `playwright`.
- Direct URL extraction: `fetch`, `jina`, or `linkup-fetch`.
- Large code intelligence: `sourcegraph` if available/authenticated.

## 14. Troubleshooting

### MCPs show in config but not in active tools

Restart the CLI agent. Most MCP clients load MCP servers at startup.

### `codex mcp add` cannot write config

Edit `/home/imyuvi/.codex/config.toml` manually. This happened in the sandboxed
session because Codex could not create its temporary config file.

### `npx` MCP server fails

Check Node:

```bash
node --version
npx --version
```

Most current MCP npm packages require Node 18+ or Node 20+.

### `uvx` MCP server fails

Check:

```bash
uvx --version
python3 --version
```

Then try running the server command directly:

```bash
uvx basic-memory mcp
uvx mcp-server-fetch
```

### Search MCP auth fails

Check key formatting:

- Tavily keys should start with `tvly-`.
- Jina keys should start with `jina_`.
- Linkup key should be the UUID-style token from the Linkup dashboard.
- Exa key should match the dashboard key.

### Skills do not appear

Verify the skill layout:

```text
/home/imyuvi/.codex/skills/<skill-name>/SKILL.md
```

Then restart Codex.

## 15. Source References

Useful references checked during setup:

- Context7: `https://context7.com/docs/installation`
- Basic Memory: `https://docs.basicmemory.com/start-here/quickstart-local`
- Tavily MCP: `https://docs.tavily.com/documentation/mcp`
- Exa MCP: `https://docs.exa.ai/reference/exa-mcp`
- Exa coding-agent guide: `https://docs.exa.ai/reference/search-api-guide-for-coding-agents`
- Jina MCP: `https://github.com/jina-ai/MCP`
- Linkup MCP: `https://docs.linkup.so/pages/integrations/mcp/mcp`
- Playwright MCP: `https://playwright.dev/mcp/installation`
- Codex MCP config reference: `https://developers.openai.com/codex/config-reference`

## 16. One-Shot Rebuild Checklist

On a fresh machine:

1. Install Codex.
2. Install Node.js and confirm `node`/`npx`.
3. Install `uv` and confirm `uvx`.
4. Create `/home/imyuvi/.codex/config.toml`.
5. Paste the TOML from section 7.
6. Run `chmod 600 /home/imyuvi/.codex/config.toml`.
7. Copy local skills from `/home/imyuvi/Downloads/claudegod/skills/` into
   `/home/imyuvi/.codex/skills/`.
8. Run `codex mcp list`.
9. Restart Codex.
10. Ask the agent to list active skills and MCPs.

