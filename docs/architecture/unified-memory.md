# Fedora Linux Setup: Shared Memory Across All 4 AI Coding Agents

---

## Phase 1 — System Prerequisites

### 1.1 Update your system first

Always do this before installing developer tools. Fedora's packages update frequently and mismatched libs cause subtle bugs.

```bash
sudo dnf upgrade --refresh -y
```

### 1.2 Install base tools

```bash
sudo dnf install -y git curl wget tar unzip ripgrep
```

**Why ripgrep?** Claude Code and Gemini CLI use `rg` (ripgrep) internally for codebase search. Without it you get "ripgrep not found" errors during sessions.

### 1.3 Install Node.js 22+ using fnm

Fedora's default dnf Node.js is usually behind. The tools require Node.js 22+. Use `fnm` (Fast Node Manager) — it installs per-user, no sudo, and lets you switch versions easily.

```bash
# Install fnm
curl -fsSL https://fnm.vercel.app/install | bash

# Reload your shell to activate fnm
source ~/.bashrc   # or ~/.zshrc if you use zsh

# Install Node.js 22 LTS
fnm install 22
fnm use 22
fnm default 22

# Verify
node --version   # should show v22.x.x
npm --version
```

**Why fnm over nvm?** fnm is written in Rust, starts ~40x faster, and is Fedora-friendly with no shell bloat.

### 1.4 Verify git is configured

The pre-commit hook we create later requires git to know who you are.

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git config --global init.defaultBranch main
```

---

## Phase 2 — Install All Four Tools

### 2.1 Claude Code

```bash
npm install -g @anthropic-ai/claude-code

# Verify
claude --version
```

**Authentication:** Claude Code uses your Anthropic account. On first run, type `claude` and it will open a browser login. Alternatively, set an API key:

```bash
# Add to ~/.bashrc (or ~/.zshrc)
echo 'export ANTHROPIC_API_KEY="sk-ant-your-key-here"' >> ~/.bashrc
source ~/.bashrc
```

Get your API key at: https://console.anthropic.com/

### 2.2 GitHub Copilot CLI

```bash
npm install -g @github/copilot

# Verify
copilot --version
```

**Authentication:** Run `copilot`, then type `/login` and follow the browser prompts. You need a GitHub Copilot subscription (Pro, Pro+, Business, or Enterprise).

**Alternative install via GitHub CLI:**

```bash
# Install gh first
sudo dnf install -y gh

# Then use gh to install/run Copilot CLI
gh copilot   # prompts to install automatically on first run
```

### 2.3 Gemini CLI

```bash
npm install -g @google/gemini-cli

# Verify
gemini --version
```

**Authentication:** Run `gemini` and it will walk you through Google account sign-in. Free tier gives 1,000 requests/day with Gemini 2.5 Pro — the most generous free tier of any tool here.

### 2.4 OpenAI Codex CLI

```bash
npm install -g @openai/codex

# Verify
codex --version
```

**Authentication:** On first run, Codex prompts you to sign in with your ChatGPT account, or set an API key:

```bash
echo 'export OPENAI_API_KEY="sk-your-key-here"' >> ~/.bashrc
source ~/.bashrc
```

**Note:** As of April 2026, Codex CLI is free for ChatGPT Free and Go users "for a limited time." Have a backup plan (Gemini CLI free tier) if OpenAI ends the free period.

### 2.5 Store all your API keys cleanly

Instead of scattering exports in ~/.bashrc, create a dedicated secrets file:

```bash
# Create a secrets file — never commit this
touch ~/.ai-keys
chmod 600 ~/.ai-keys   # only you can read it

# Edit it
nano ~/.ai-keys
```

Paste this into `~/.ai-keys`:

```bash
# AI Coding Agent API Keys
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
export OPENAI_API_KEY="sk-your-key-here"
# Gemini uses browser OAuth — no key needed for free tier
# GitHub Copilot uses browser OAuth — no key needed
```

Then load it from `~/.bashrc`:

```bash
echo 'source ~/.ai-keys' >> ~/.bashrc
source ~/.bashrc
```

---

## Phase 3 — Create Your Project Structure

Do this once per project. Navigate to your project's root directory first.

```bash
cd ~/your-project   # replace with your actual project path
```

### 3.1 Create all the directories

```bash
mkdir -p docs
mkdir -p .github
mkdir -p .gemini
mkdir -p .claude/rules
```

**Why each directory:**
- `docs/` — holds PROGRESS.md, HANDOFF.md, SKILLS.md (shared across all agents)
- `.github/` — Copilot looks here for copilot-instructions.md
- `.gemini/` — holds Gemini's settings.json config
- `.claude/rules/` — path-scoped rules for Claude Code

### 3.2 Create AGENTS.md — The Master File

This is the single source of truth. Everything else will point here.

```bash
cat > AGENTS.md << 'EOF'
# [Your Project Name] — Agent Context

> This file is the master instruction file for all AI coding agents.
> It is read natively by: GitHub Copilot, OpenAI Codex.
> It is referenced by: CLAUDE.md (Claude Code), GEMINI.md (Gemini CLI).

---

## Stack
- Language: [e.g. TypeScript / Python / Go]
- Framework: [e.g. Next.js 15 / FastAPI / Gin]
- Package manager: [e.g. pnpm / uv / go mod]
- Database: [e.g. PostgreSQL via Drizzle ORM]
- Runtime: [e.g. Node.js 22 / Python 3.12]

## Commands
- Install: `[e.g. pnpm install]`
- Dev server: `[e.g. pnpm dev]`
- Run tests: `[e.g. pnpm test]`
- Lint: `[e.g. pnpm lint]`
- Build: `[e.g. pnpm build]`
- Type check: `[e.g. pnpm typecheck]`

## Architecture
- Core logic: `src/lib/`
- API routes: `src/api/` — REST conventions
- Tests: `__tests__/` next to the source file they test
- Do NOT touch: `src/legacy/` — frozen, do not refactor

## Code Conventions
- Use functional components — no class components
- Prefer named exports over default exports
- All async functions must handle errors explicitly — never swallow exceptions
- Never use `any` — prefer `unknown` with a type guard
- No `console.log` in committed code

## Git Conventions
- Branch names: `feat/<ticket>-short-description`
- Always run tests and lint before committing
- Commit message format: `type(scope): short description`

## Constraints — Read These Before Acting
- Never change database schema without a migration
- Never break API contracts defined in `docs/API-CONTRACTS.md`
- Do not install new dependencies without asking the user first
- Never delete files — ask first if something seems unused

## Current Work
Before starting any task, read:
- `docs/PROGRESS.md` — current task checklist
- `docs/HANDOFF.md` — context from the previous agent session (if switching)

EOF
```

Edit AGENTS.md now and fill in your real project details. Every line you fill in saves you from re-explaining things every session.

### 3.3 Create PROGRESS.md template

```bash
cat > docs/PROGRESS.md << 'EOF'
# PROGRESS.md — [Feature Name]
Created: [date] | Current Agent: [agent name]

## Goal
[One sentence: what are we building in this work session?]

## Completed ✅
- [x] Example: Set up database schema

## In Progress 🔄
- [ ] Example: Writing API route handler

## Pending ⏳
- [ ] Example: Frontend component
- [ ] Example: Connect frontend to API
- [ ] Example: Write tests

## Decisions Made
<!-- Record WHY decisions were made so the next agent doesn't undo them -->
- [Decision]: [Reason]

## Files Changed This Session
- `path/to/file.ts` — [what changed]

EOF
```

### 3.4 Create HANDOFF.md template

```bash
cat > docs/HANDOFF.md << 'EOF'
# HANDOFF.md
Last written by: [agent name] | Date: [date]

> If you are a new agent picking up this work, read this file FIRST,
> then read PROGRESS.md, then read AGENTS.md before doing anything.

## What We Were Doing
[Describe the exact task in progress when the session ended]

## Last File Being Edited
`path/to/file.ts` — line [N], [what was being changed]

## The Next Step
[Exact first action the next agent should take]

## Context Not Obvious From Code
[Things you discovered this session that aren't written down anywhere else]

## Gotchas / Warnings
[Anything that will bite the next agent if they don't know about it]

## State of Tests
- Tests passing: [yes/no]
- Known failing test: [name and why it's expected to fail]

EOF
```

### 3.5 Create SKILLS.md for reusable workflows

```bash
cat > docs/SKILLS.md << 'EOF'
# SKILLS.md — Reusable Agent Workflows

## How to add a new API endpoint
1. Create route handler in `src/api/[name].ts`
2. Add Zod schema for request/response validation
3. Register route in `src/api/index.ts`
4. Write test in `__tests__/api/[name].test.ts`
5. Update `docs/API-CONTRACTS.md`

## How to add a new database table
1. Add schema definition in `src/db/schema.ts`
2. Generate migration: `[migration command]`
3. Review the generated migration file before applying
4. Apply: `[apply command]`
5. Update types if needed

## How to run a safe refactor
1. Make sure all tests pass first: `[test command]`
2. Make the change in small steps
3. Run tests after each step
4. Never rename public API surface without checking callers

EOF
```

---

## Phase 4 — Link Everything Together

### 4.1 Create symlinks for Claude Code and Gemini CLI

Symlinks make `CLAUDE.md` and `GEMINI.md` physically identical to `AGENTS.md`. Any edit to `AGENTS.md` is instantly reflected everywhere.

```bash
# Create CLAUDE.md as a symlink to AGENTS.md
ln -sf AGENTS.md CLAUDE.md

# Create GEMINI.md as a symlink to AGENTS.md
ln -sf AGENTS.md GEMINI.md

# Create Copilot's file as a symlink (optional — Copilot reads AGENTS.md natively,
# but this is good for tools that only look in .github/)
ln -sf ../AGENTS.md .github/copilot-instructions.md

# Verify the symlinks are correct
ls -la CLAUDE.md GEMINI.md .github/copilot-instructions.md
```

You should see output like:
```
CLAUDE.md -> AGENTS.md
GEMINI.md -> AGENTS.md
.github/copilot-instructions.md -> ../AGENTS.md
```

### 4.2 Configure Gemini to also load AGENTS.md directly

Even though GEMINI.md is a symlink to AGENTS.md, Gemini's `settings.json` lets you explicitly tell it to also look for other filenames — useful insurance:

```bash
cat > .gemini/settings.json << 'EOF'
{
  "context": {
    "fileName": ["GEMINI.md", "CLAUDE.md", "AGENTS.md"],
    "includeDirectories": ["./src", "./docs"]
  }
}
EOF
```

**Why includeDirectories?** This tells Gemini to also scan `src/` and `docs/` for context files, so it can see your SKILLS.md and ARCHITECTURE.md without you referencing them manually every session.

### 4.3 Configure CLAUDE.md to explicitly load AGENTS.md

Since Claude Code reads CLAUDE.md (which is now a symlink = AGENTS.md), it already gets the content. But add these lines to the TOP of AGENTS.md so Claude also pulls in the docs files automatically:

```bash
# Open AGENTS.md and add these lines right after the title:
nano AGENTS.md
```

Add at the top (after the title, before ## Stack):

```markdown
## Auto-load for Claude Code
Before starting any task, read these files for full context:
- @docs/SKILLS.md
- @docs/PROGRESS.md  
- @docs/HANDOFF.md (only if it contains today's date or recent content)
```

The `@filename` syntax is Claude Code's file reference system — it loads those files into context automatically.

---

## Phase 5 — Set Up the Git Pre-commit Hook

The symlink approach works great, but if symlinks ever break (e.g., after copying the repo to a different machine, or on a Windows CI runner), having a hook that re-creates them is your safety net.

### 5.1 Create the sync script

```bash
cat > sync-agent-files.sh << 'EOF'
#!/bin/bash
# sync-agent-files.sh
# Ensures all AI agent instruction files point to AGENTS.md
# Run manually after editing AGENTS.md, or it runs automatically via git hook

set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"

echo "🔄 Syncing agent instruction files..."

# Re-create symlinks (force-overwrite if they exist)
ln -sf AGENTS.md CLAUDE.md
ln -sf AGENTS.md GEMINI.md
mkdir -p .github
ln -sf ../AGENTS.md .github/copilot-instructions.md

# Verify
echo "✅ Symlinks verified:"
ls -la CLAUDE.md GEMINI.md .github/copilot-instructions.md

echo "Done. All agent files point to AGENTS.md"
EOF

chmod +x sync-agent-files.sh
```

### 5.2 Install the pre-commit hook

```bash
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Pre-commit hook: keep all agent files in sync with AGENTS.md

# Only run if AGENTS.md is staged
if git diff --cached --name-only | grep -q "AGENTS.md"; then
    echo "AGENTS.md changed — re-syncing agent instruction files..."
    ./sync-agent-files.sh
    # Stage the symlinks too so they're included in the commit
    git add CLAUDE.md GEMINI.md .github/copilot-instructions.md
fi
EOF

chmod +x .git/hooks/pre-commit
```

**Why this matters:** Whenever you edit and commit AGENTS.md, the hook automatically re-creates all symlinks and stages them. You can't accidentally commit a broken state.

---

## Phase 6 — Configure .gitignore

Some files should be committed; others shouldn't.

```bash
cat >> .gitignore << 'EOF'

# AI Agent Files — personal/local only
CLAUDE.local.md
.claude/settings.local.json

# API keys — NEVER commit
.ai-keys
*.env
.env*
!.env.example

# Agent auto-memory (machine-local, changes constantly)
.claude/projects/

EOF
```

**Files TO commit** (add these explicitly if .gitignore is aggressive):

```bash
# Make sure these are tracked
git add AGENTS.md CLAUDE.md GEMINI.md
git add .github/copilot-instructions.md
git add .gemini/settings.json
git add .claude/rules/
git add docs/PROGRESS.md docs/HANDOFF.md docs/SKILLS.md
git add sync-agent-files.sh
```

---

## Phase 7 — Verify Everything Works

### 7.1 Test Claude Code

```bash
cd ~/your-project
claude
```

Inside Claude, type:
```
What files are you loading for context in this session?
```

Claude should mention CLAUDE.md (and by extension AGENTS.md content).

### 7.2 Test Gemini CLI

```bash
gemini
```

Inside Gemini, type:
```
/memory show
```

This lists all files Gemini has loaded. You should see GEMINI.md and any files from your `includeDirectories`.

### 7.3 Test Copilot CLI

```bash
copilot
```

Inside Copilot, type:
```
What project instructions are you working with?
```

Copilot reads AGENTS.md natively, so it should describe your project correctly.

### 7.4 Test Codex CLI

```bash
codex
```

Codex reads AGENTS.md natively from your project root. Ask it:
```
Summarize the project context you have access to.
```

### 7.5 Check the symlinks are intact after any git operation

```bash
ls -la CLAUDE.md GEMINI.md .github/copilot-instructions.md
# All three should show -> AGENTS.md or -> ../AGENTS.md
```

If any are broken, just re-run:
```bash
./sync-agent-files.sh
```

---

## Phase 8 — The Handoff Workflow (Switching Agents)

### When quota is getting low (do this proactively):

Paste this prompt into whichever agent you're using:

```
My quota is running low. Please update docs/PROGRESS.md with what we completed
today (tick the boxes), then write docs/HANDOFF.md with:
1. Exactly what we were working on when we stop
2. The last file and line number being edited
3. What the next step is — be specific
4. Any context or decisions made this session that aren't in the code
5. Whether tests are passing and any known expected failures
```

### When starting a new agent:

```
New session. Before doing anything else:
1. Read AGENTS.md for project rules
2. Read docs/PROGRESS.md for current task status  
3. Read docs/HANDOFF.md for where we left off

Then tell me: what do you understand about where we are,
and what will you do first?
```

### Switching to each specific tool:

**To Claude Code:**
```bash
cd ~/your-project && claude
```
Then paste the new session prompt above.

**To Gemini CLI:**
```bash
cd ~/your-project && gemini
```
Gemini auto-loads the files via settings.json. Paste the new session prompt.

**To Copilot CLI:**
```bash
cd ~/your-project && copilot
```
Note: with Copilot CLI you can also switch models mid-session with `/model` — useful if one model's quota is lower than another's.

**To Codex CLI:**
```bash
cd ~/your-project && codex
```

---

## Quick Reference — Daily Commands

```bash
# Start any agent in your project
cd ~/your-project

claude          # Claude Code
gemini          # Gemini CLI
copilot         # GitHub Copilot CLI
codex           # OpenAI Codex CLI

# Check symlinks are healthy
ls -la CLAUDE.md GEMINI.md .github/copilot-instructions.md

# Re-sync if broken
./sync-agent-files.sh

# Update all tools
npm update -g @anthropic-ai/claude-code @google/gemini-cli @github/copilot @openai/codex

# Check Node.js version
node --version   # should be 22+

# Switch Node version if needed
fnm use 22
```

---

## Troubleshooting

**"command not found: claude" after install**
```bash
# fnm installs npm binaries to a specific path — make sure it's in PATH
fnm use 22
which claude   # should return a path
# If not, add this to ~/.bashrc:
export PATH="$HOME/.local/share/fnm/node-versions/v22.x.x/installation/bin:$PATH"
```

**Symlinks broken after cloning repo on new machine**
```bash
./sync-agent-files.sh
```

**Gemini not loading AGENTS.md**
```bash
# Verify settings.json
cat .gemini/settings.json
# Run /memory show inside gemini to see what's loaded
```

**Claude Code not reading @docs/PROGRESS.md**
```bash
# Make sure the @ reference is in AGENTS.md (which CLAUDE.md points to)
head -20 AGENTS.md
# The @docs/PROGRESS.md line must be in there
```

**"ripgrep not found" error in any tool**
```bash
sudo dnf install -y ripgrep
rg --version   # should work now
```

**Node.js too old after Fedora system update**
```bash
fnm use 22   # switch back to your installed version
# Or update to latest LTS:
fnm install 22 --force
```
