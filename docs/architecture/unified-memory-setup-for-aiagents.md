# SETUP_UNIFIED_MEMORY.md
## Unified AI Agent Memory System — Fedora Linux

> **Instructions for the AI agent reading this file:**
> You are being asked to set up a unified memory system across multiple AI coding agents
> (Claude Code, GitHub Copilot CLI, Gemini CLI, OpenAI Codex CLI) on this Fedora Linux machine.
> Execute every step in order. After each shell command block, verify it succeeded before moving on.
> If a step fails, diagnose and fix it before continuing — do not skip steps.
> When you finish, report a summary of everything that was done and anything that needs manual action.

---

## AGENT EXECUTION RULES

- Run all commands as the current non-root user unless explicitly told to use `sudo`
- The project root for this setup is the directory where this file lives
- If a command fails, try to fix the cause rather than skipping it
- For every file you create, confirm it exists afterward with `ls -la`
- For every symlink you create, confirm it resolves correctly with `ls -la`
- Do not install anything globally without verifying it is not already installed
- At the end of every phase, print a short status summary before moving to the next

---

## PHASE 1 — Detect Environment

Run these checks first. Use the results to make decisions in later phases.

```bash
# Check OS
cat /etc/os-release | grep -E "^NAME|^VERSION"

# Check current user (should NOT be root)
whoami

# Check home directory
echo $HOME

# Check current shell
echo $SHELL

# Determine shell config file — use the result throughout this setup
if [ -f "$HOME/.zshrc" ]; then
  echo "SHELL_RC=$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
  echo "SHELL_RC=$HOME/.bashrc"
else
  echo "SHELL_RC=$HOME/.profile"
fi

# Check if Node.js is installed and what version
node --version 2>/dev/null || echo "Node.js NOT installed"

# Check if npm is installed
npm --version 2>/dev/null || echo "npm NOT installed"

# Check if fnm is installed
fnm --version 2>/dev/null || echo "fnm NOT installed"

# Check if git is installed and configured
git --version
git config --global user.name 2>/dev/null || echo "git user.name not set"
git config --global user.email 2>/dev/null || echo "git user.email not set"

# Check if we're inside a git repo already
git rev-parse --show-toplevel 2>/dev/null || echo "NOT in a git repo"

# Check which AI tools are already installed
claude --version 2>/dev/null || echo "Claude Code: NOT installed"
copilot --version 2>/dev/null || echo "GitHub Copilot CLI: NOT installed"
gemini --version 2>/dev/null || echo "Gemini CLI: NOT installed"
codex --version 2>/dev/null || echo "OpenAI Codex CLI: NOT installed"

# Check for ripgrep
rg --version 2>/dev/null || echo "ripgrep: NOT installed"
```

**Decision point for the agent:** Based on the output above, skip any installation step for tools that are already at the correct version. Node.js must be version 22 or higher — if it is lower, install fnm and use it to get Node 22 regardless of the existing installation.

---

## PHASE 2 — System Package Installation

### 2.1 Update system and install base packages

```bash
sudo dnf upgrade --refresh -y

sudo dnf install -y \
  git \
  curl \
  wget \
  tar \
  unzip \
  ripgrep

# Verify ripgrep installed
rg --version
```

### 2.2 Install fnm (Fast Node Manager) if Node 22+ is not present

Only run this block if `node --version` in Phase 1 returned nothing or a version below v22.

```bash
# Install fnm for the current user (no sudo needed)
curl -fsSL https://fnm.vercel.app/install | bash

# Detect shell rc file and source fnm into it
SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then SHELL_RC="$HOME/.bashrc"
else SHELL_RC="$HOME/.profile"
fi

# fnm install script adds itself to the rc file, but source it now for this session
export PATH="$HOME/.local/share/fnm:$PATH"
eval "$(fnm env --use-on-cd 2>/dev/null)"

# Install Node.js 22 LTS
fnm install 22
fnm use 22
fnm default 22

# Verify
node --version   # Must show v22.x.x or higher
npm --version
```

### 2.3 Add fnm to shell startup if not already there

```bash
SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then SHELL_RC="$HOME/.bashrc"
else SHELL_RC="$HOME/.profile"
fi

# Check if fnm eval is already in the shell rc
if ! grep -q "fnm env" "$SHELL_RC"; then
  echo '' >> "$SHELL_RC"
  echo '# fnm (Fast Node Manager)' >> "$SHELL_RC"
  echo 'export PATH="$HOME/.local/share/fnm:$PATH"' >> "$SHELL_RC"
  echo 'eval "$(fnm env --use-on-cd)"' >> "$SHELL_RC"
  echo "Added fnm to $SHELL_RC"
else
  echo "fnm already configured in $SHELL_RC — skipping"
fi
```

---

## PHASE 3 — Install AI Coding CLI Tools

Skip any tool that is already installed (detected in Phase 1). For each tool, verify the install succeeded before moving to the next.

### 3.1 Claude Code

```bash
# Skip if already installed
if ! command -v claude &>/dev/null; then
  npm install -g @anthropic-ai/claude-code
fi
claude --version
```

### 3.2 GitHub Copilot CLI

```bash
# Skip if already installed
if ! command -v copilot &>/dev/null; then
  npm install -g @github/copilot
fi
copilot --version
```

### 3.3 Gemini CLI

```bash
# Skip if already installed
if ! command -v gemini &>/dev/null; then
  npm install -g @google/gemini-cli
fi
gemini --version
```

### 3.4 OpenAI Codex CLI

```bash
# Skip if already installed
if ! command -v codex &>/dev/null; then
  npm install -g @openai/codex
fi
codex --version
```

### 3.5 Verify all four tools are present

```bash
echo "=== AI Tool Version Check ==="
claude --version   && echo "✅ Claude Code OK"   || echo "❌ Claude Code MISSING"
copilot --version  && echo "✅ Copilot CLI OK"   || echo "❌ Copilot CLI MISSING"
gemini --version   && echo "✅ Gemini CLI OK"    || echo "❌ Gemini CLI MISSING"
codex --version    && echo "✅ Codex CLI OK"     || echo "❌ Codex CLI MISSING"
```

If any tool shows MISSING, do not proceed. Diagnose and fix before continuing.

---

## PHASE 4 — Configure git (if not already configured)

```bash
# Only set if not already configured
if [ -z "$(git config --global user.name 2>/dev/null)" ]; then
  # Ask the user for their name and email
  echo "⚠️  git user.name is not set."
  echo "Please tell me your full name and email so I can configure git."
  echo "I will pause here and wait for your input before continuing."
  # Agent: ask the user for their name and email, then run:
  # git config --global user.name "Their Name"
  # git config --global user.email "their@email.com"
fi

git config --global init.defaultBranch main
git config --global core.editor nano

# Verify
git config --global user.name
git config --global user.email
```

---

## PHASE 5 — Initialize git repo if needed

```bash
# Check if we're in a git repo; if not, initialize one
if ! git rev-parse --show-toplevel &>/dev/null; then
  echo "Not in a git repo. Initializing..."
  git init
  git add .gitignore 2>/dev/null || true
  echo "Git repo initialized at: $(pwd)"
else
  echo "Already in git repo: $(git rev-parse --show-toplevel)"
fi
```

---

## PHASE 6 — Create Project Directory Structure

```bash
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"
echo "Working in: $PROJECT_ROOT"

# Create all required directories
mkdir -p docs
mkdir -p .github
mkdir -p .gemini
mkdir -p .claude/rules

echo "=== Directory structure created ==="
ls -la
```

---

## PHASE 7 — Create Core Memory Files

### 7.1 Create AGENTS.md (the master source-of-truth file)

**Agent instruction:** Before creating this file, look at the project directory. Check for any existing `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `README.md`, or similar files to detect the actual tech stack. Fill in the Stack section with what you find. If you cannot determine a value, use `[FILL IN]` as the placeholder and tell the user what to update.

```bash
cat > AGENTS.md << 'AGENTS_EOF'
# [PROJECT NAME] — Agent Context File
> **For the agent reading this:** This is the master instruction file.
> Read docs/PROGRESS.md and docs/HANDOFF.md before starting any task.

---

## Auto-Load (Claude Code)
Before starting any task, load these files:
- @docs/SKILLS.md
- @docs/PROGRESS.md
- @docs/HANDOFF.md

---

## Stack
- Language: [FILL IN — e.g. TypeScript / Python / Go / Rust]
- Framework: [FILL IN — e.g. Next.js 15 / FastAPI / Gin]
- Package manager: [FILL IN — e.g. pnpm / npm / uv / pip / cargo]
- Database: [FILL IN — e.g. PostgreSQL / SQLite / MongoDB]
- Runtime: [FILL IN — e.g. Node.js 22 / Python 3.12]

## Commands
- Install dependencies: `[FILL IN]`
- Start dev server:     `[FILL IN]`
- Run tests:            `[FILL IN]`
- Lint:                 `[FILL IN]`
- Build:                `[FILL IN]`
- Type check:           `[FILL IN — or remove if not applicable]`

## Architecture
- [FILL IN — describe where core logic lives]
- [FILL IN — describe where API/routes live]
- [FILL IN — describe where tests live]
- Do NOT touch: [FILL IN — any frozen/legacy directories]

## Code Conventions
- [FILL IN — e.g. Use functional components, no class components]
- [FILL IN — e.g. Named exports preferred over default exports]
- All async functions must handle errors — never silently swallow exceptions
- No debug print statements (console.log / print) in committed code
- [FILL IN — any naming conventions]

## Git Conventions
- Branch names: `feat/<ticket>-short-description` or `fix/<ticket>-short-description`
- Always run tests and lint before committing
- Commit message format: `type(scope): short description`

## Hard Constraints — Read Before Acting
- Never modify the database schema without a migration file
- Never break public API contracts — check docs/API-CONTRACTS.md first
- Do not add new dependencies without asking the user first
- Do not delete files — ask first if something seems unused
- [FILL IN — any project-specific constraints]

## Current Session
Read docs/PROGRESS.md for current task status.
Read docs/HANDOFF.md if picking up from a previous agent session.
AGENTS_EOF

echo "✅ AGENTS.md created"
cat AGENTS.md | wc -l
```

### 7.2 Create docs/PROGRESS.md

```bash
cat > docs/PROGRESS.md << 'PROGRESS_EOF'
# PROGRESS.md
Last updated: [DATE] | Active agent: [AGENT NAME]

## Current Goal
[One sentence describing the current task or feature being built]

## Completed ✅
<!-- Agent: tick boxes with [x] as tasks are done -->
- [ ] Example placeholder — replace with real tasks

## In Progress 🔄
- [ ] [Current task being worked on]

## Pending ⏳
- [ ] [Next task]
- [ ] [Task after that]

## Decisions Made This Session
<!-- Record WHY decisions were made — prevents future agents from undoing them -->
| Decision | Reason |
|----------|--------|
| [e.g. Used nanoid over UUID] | [e.g. Smaller output, URL-safe by default] |

## Files Modified This Session
| File | What Changed |
|------|-------------|
| [path/to/file] | [brief description] |

PROGRESS_EOF

echo "✅ docs/PROGRESS.md created"
```

### 7.3 Create docs/HANDOFF.md

```bash
cat > docs/HANDOFF.md << 'HANDOFF_EOF'
# HANDOFF.md
> Read this file FIRST if you are a new agent picking up existing work.
> Then read PROGRESS.md, then AGENTS.md.

Last written by: [AGENT NAME]
Date: [DATE]
Status: [FRESH START / IN PROGRESS / BLOCKED]

---

## What We Were Doing
[Describe the exact task in progress when the last session ended]

## Last File Being Edited
File: `[path/to/file]`
Line: [N]
What was happening: [description of the in-progress change]

## Exact Next Step
[Be specific — e.g. "Fix the mock at __tests__/api/users.test.ts:47, then run tests"]

## Context Not in the Code
[Things discovered this session that aren't written anywhere in the codebase]

## Gotchas / Warnings
[Anything that will cause problems if the next agent doesn't know about it]

## Test Status
- All tests passing: [YES / NO]
- Known expected failures: [list them and why they're expected]
- Command to run tests: `[FILL IN]`

HANDOFF_EOF

echo "✅ docs/HANDOFF.md created"
```

### 7.4 Create docs/SKILLS.md

```bash
cat > docs/SKILLS.md << 'SKILLS_EOF'
# SKILLS.md — Reusable Agent Workflows

> This file describes how to perform common tasks in this project.
> Update this file whenever a new pattern or workflow is established.

## Adding a New Feature
1. Create a feature branch: `git checkout -b feat/<name>`
2. [FILL IN project-specific steps]
3. Write tests before or alongside the feature code
4. Run the full test suite before committing
5. Open a PR / commit to main (whichever applies)

## Adding a New API Endpoint
1. [FILL IN — e.g. Create handler in src/api/]
2. [FILL IN — e.g. Add request/response validation schema]
3. [FILL IN — e.g. Register route in src/api/index.ts]
4. Write test in the appropriate test directory
5. Update docs/API-CONTRACTS.md

## Database Changes
1. NEVER modify existing migration files
2. Create a new migration file for every schema change
3. Run: `[FILL IN migration command]`
4. Review the generated SQL before applying
5. Apply: `[FILL IN apply command]`

## Running a Safe Refactor
1. Confirm all tests pass first: `[FILL IN test command]`
2. Make changes in small, verifiable steps
3. Run tests after each step
4. Never rename public API surface without checking all callers

## Debugging a Failing Test
1. Read the full error message — do not skim
2. Run only the failing test in isolation: `[FILL IN]`
3. Check if the test environment differs from production (env vars, mocks)
4. Fix the root cause — do not suppress the error

SKILLS_EOF

echo "✅ docs/SKILLS.md created"
```

### 7.5 Create docs/API-CONTRACTS.md placeholder

```bash
cat > docs/API-CONTRACTS.md << 'API_EOF'
# API-CONTRACTS.md
> Document all public API endpoints here.
> Agents must not break any contract listed in this file without explicit user approval.

## Endpoints

### [METHOD] /[path]
- Request: `[describe or paste schema]`
- Response: `[describe or paste schema]`
- Notes: [any constraints]

API_EOF

echo "✅ docs/API-CONTRACTS.md created"
```

---

## PHASE 8 — Create Symlinks

Symlinks make CLAUDE.md, GEMINI.md, and copilot-instructions.md all point to the same AGENTS.md file. One edit to AGENTS.md updates all tools.

```bash
cd "$(git rev-parse --show-toplevel)"

# Create CLAUDE.md → AGENTS.md
ln -sf AGENTS.md CLAUDE.md
echo "Symlink CLAUDE.md → AGENTS.md"

# Create GEMINI.md → AGENTS.md
ln -sf AGENTS.md GEMINI.md
echo "Symlink GEMINI.md → AGENTS.md"

# Create .github/copilot-instructions.md → AGENTS.md
# Note: must use relative path that works from inside .github/
ln -sf ../AGENTS.md .github/copilot-instructions.md
echo "Symlink .github/copilot-instructions.md → ../AGENTS.md"

# Verify all three symlinks resolve correctly
echo ""
echo "=== Symlink verification ==="
ls -la CLAUDE.md GEMINI.md .github/copilot-instructions.md

# Confirm each file has content (symlink is not broken)
echo ""
echo "=== Content check (first line of each) ==="
head -1 CLAUDE.md
head -1 GEMINI.md
head -1 .github/copilot-instructions.md
```

All three `head -1` outputs must be identical (the title line from AGENTS.md). If any shows an error, the symlink is broken — fix it before continuing.

---

## PHASE 9 — Configure Gemini CLI

```bash
cat > .gemini/settings.json << 'GEMINI_EOF'
{
  "context": {
    "fileName": ["GEMINI.md", "CLAUDE.md", "AGENTS.md"],
    "includeDirectories": ["./src", "./docs", "./lib", "./app"]
  }
}
GEMINI_EOF

echo "✅ .gemini/settings.json created"
cat .gemini/settings.json
```

**Note for the agent:** The `includeDirectories` list tells Gemini to scan those directories for context files. If this project does not have a `src/` directory, adjust the list to match the actual source directory structure you discovered in Phase 7.1.

---

## PHASE 10 — Create the Sync Script

This script re-creates all symlinks. Run it if symlinks break (e.g. after copying the repo).

```bash
cat > sync-agent-files.sh << 'SYNC_EOF'
#!/bin/bash
# sync-agent-files.sh
# Re-creates all AI agent instruction file symlinks
# Run this if symlinks break, or after cloning the repo on a new machine
# Safe to run multiple times — uses -sf to force-overwrite

set -e

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
cd "$PROJECT_ROOT"

echo "🔄 Syncing AI agent instruction files..."

# Re-create symlinks
ln -sf AGENTS.md CLAUDE.md
ln -sf AGENTS.md GEMINI.md
mkdir -p .github
ln -sf ../AGENTS.md .github/copilot-instructions.md

# Verify
echo ""
echo "✅ Symlinks verified:"
ls -la CLAUDE.md GEMINI.md .github/copilot-instructions.md

echo ""
echo "✅ All agent files point to AGENTS.md"
SYNC_EOF

chmod +x sync-agent-files.sh
echo "✅ sync-agent-files.sh created and made executable"
```

---

## PHASE 11 — Create the Handoff Script

This script prompts the current agent to write a proper HANDOFF.md before quota runs out.

```bash
cat > save-session.sh << 'SAVE_EOF'
#!/bin/bash
# save-session.sh
# Run this (or tell your agent to run it) when quota is running low.
# It prints the handoff prompt to paste into your current AI agent.

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║           HANDOFF PROMPT — paste this into your AI agent        ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "My quota is running low. Before we stop:"
echo "1. Update docs/PROGRESS.md — tick off completed tasks with [x],"
echo "   add any tasks discovered this session to the Pending list."
echo "2. Write docs/HANDOFF.md with:"
echo "   - Exactly what we were working on"
echo "   - The last file and line number being edited"
echo "   - The exact next step for the replacement agent"
echo "   - Any context or decisions made this session not obvious from the code"
echo "   - Current test status (passing/failing and why)"
echo "3. Confirm both files are saved, then tell me you're done."
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║        NEW SESSION PROMPT — paste this into the next agent      ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "New session. Before doing anything:"
echo "1. Read AGENTS.md for project rules and conventions"
echo "2. Read docs/PROGRESS.md for current task status"
echo "3. Read docs/HANDOFF.md for exactly where we left off"
echo "Tell me what you understand about our current state,"
echo "and what you will do first. Do not start coding until I confirm."
echo ""
SAVE_EOF

chmod +x save-session.sh
echo "✅ save-session.sh created and made executable"
```

---

## PHASE 12 — Install git Hooks

### 12.1 Pre-commit hook — keep symlinks in sync

```bash
mkdir -p .git/hooks

cat > .git/hooks/pre-commit << 'HOOK_EOF'
#!/bin/bash
# Pre-commit hook: re-sync AI agent files if AGENTS.md was modified

if git diff --cached --name-only | grep -q "^AGENTS.md$"; then
  echo "📝 AGENTS.md changed — re-syncing agent instruction files..."
  
  ln -sf AGENTS.md CLAUDE.md
  ln -sf AGENTS.md GEMINI.md
  mkdir -p .github
  ln -sf ../AGENTS.md .github/copilot-instructions.md
  
  git add CLAUDE.md GEMINI.md .github/copilot-instructions.md
  echo "✅ Agent files synced and staged"
fi
HOOK_EOF

chmod +x .git/hooks/pre-commit
echo "✅ pre-commit hook installed"
```

### 12.2 Prepare-commit-msg hook — remind agent to update PROGRESS.md

```bash
cat > .git/hooks/prepare-commit-msg << 'MSG_HOOK_EOF'
#!/bin/bash
# Appends a reminder to check PROGRESS.md to commit message template

COMMIT_MSG_FILE=$1
COMMIT_SOURCE=$2

# Only add reminder for regular commits (not merges, amends, etc.)
if [ -z "$COMMIT_SOURCE" ]; then
  echo "" >> "$COMMIT_MSG_FILE"
  echo "# Reminder: Did you update docs/PROGRESS.md?" >> "$COMMIT_MSG_FILE"
  echo "# Did you update docs/HANDOFF.md if quota is low?" >> "$COMMIT_MSG_FILE"
fi
MSG_HOOK_EOF

chmod +x .git/hooks/prepare-commit-msg
echo "✅ prepare-commit-msg hook installed"
```

---

## PHASE 13 — Configure .gitignore

```bash
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
GITIGNORE="$PROJECT_ROOT/.gitignore"

# Create if it doesn't exist
touch "$GITIGNORE"

# Add AI agent section if not already present
if ! grep -q "AI Agent Files" "$GITIGNORE"; then
  cat >> "$GITIGNORE" << 'GITIGNORE_EOF'

# ─── AI Agent Files ──────────────────────────────────────────────────────────

# Personal Claude overrides — machine-local, never share
CLAUDE.local.md
.claude/settings.local.json
.claude/projects/

# API keys — NEVER commit these
.ai-keys
*.env
.env.*
!.env.example

# Gemini auto-generated cache
.gemini/cache/

# ─────────────────────────────────────────────────────────────────────────────
GITIGNORE_EOF
  echo "✅ .gitignore updated with AI agent entries"
else
  echo "✅ .gitignore already has AI agent entries — skipping"
fi
```

---

## PHASE 14 — Stage and Commit Everything

```bash
cd "$(git rev-parse --show-toplevel)"

# Stage all the files we just created
git add \
  AGENTS.md \
  CLAUDE.md \
  GEMINI.md \
  docs/PROGRESS.md \
  docs/HANDOFF.md \
  docs/SKILLS.md \
  docs/API-CONTRACTS.md \
  .github/copilot-instructions.md \
  .gemini/settings.json \
  sync-agent-files.sh \
  save-session.sh \
  .gitignore

# Show what will be committed
git status

# Commit
git commit -m "chore: set up unified AI agent memory system

- Add AGENTS.md as single source of truth for all agents
- Symlink CLAUDE.md, GEMINI.md, and copilot-instructions.md to AGENTS.md
- Add docs/PROGRESS.md for task tracking
- Add docs/HANDOFF.md for agent handoff context
- Add docs/SKILLS.md for reusable workflows
- Configure .gemini/settings.json for multi-file context
- Install pre-commit hook to keep symlinks in sync
- Add sync-agent-files.sh for symlink recovery
- Add save-session.sh with handoff prompt helper"
```

---

## PHASE 15 — Final Verification

Run this complete check. Every item must pass before reporting success.

```bash
cd "$(git rev-parse --show-toplevel)"

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                    FINAL VERIFICATION                           ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

PASS=0
FAIL=0

check() {
  if eval "$2" &>/dev/null; then
    echo "  ✅ $1"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $1"
    FAIL=$((FAIL + 1))
  fi
}

echo "── Tools ──────────────────────────────────────────────────────────"
check "Node.js 22+" "node --version | grep -E 'v2[2-9]|v[3-9][0-9]'"
check "Claude Code installed" "command -v claude"
check "Copilot CLI installed" "command -v copilot"
check "Gemini CLI installed" "command -v gemini"
check "Codex CLI installed" "command -v codex"
check "ripgrep installed" "command -v rg"
check "git installed" "command -v git"

echo ""
echo "── Core Files ─────────────────────────────────────────────────────"
check "AGENTS.md exists" "[ -f AGENTS.md ]"
check "CLAUDE.md exists (symlink)" "[ -L CLAUDE.md ]"
check "GEMINI.md exists (symlink)" "[ -L GEMINI.md ]"
check ".github/copilot-instructions.md exists (symlink)" "[ -L .github/copilot-instructions.md ]"
check "docs/PROGRESS.md exists" "[ -f docs/PROGRESS.md ]"
check "docs/HANDOFF.md exists" "[ -f docs/HANDOFF.md ]"
check "docs/SKILLS.md exists" "[ -f docs/SKILLS.md ]"
check ".gemini/settings.json exists" "[ -f .gemini/settings.json ]"

echo ""
echo "── Symlink Integrity ──────────────────────────────────────────────"
check "CLAUDE.md resolves to AGENTS.md content" "diff CLAUDE.md AGENTS.md"
check "GEMINI.md resolves to AGENTS.md content" "diff GEMINI.md AGENTS.md"
check "copilot-instructions.md resolves to AGENTS.md content" "diff .github/copilot-instructions.md AGENTS.md"

echo ""
echo "── Scripts ────────────────────────────────────────────────────────"
check "sync-agent-files.sh is executable" "[ -x sync-agent-files.sh ]"
check "save-session.sh is executable" "[ -x save-session.sh ]"

echo ""
echo "── git Hooks ──────────────────────────────────────────────────────"
check "pre-commit hook installed" "[ -x .git/hooks/pre-commit ]"
check "prepare-commit-msg hook installed" "[ -x .git/hooks/prepare-commit-msg ]"

echo ""
echo "── git Status ─────────────────────────────────────────────────────"
check "working tree is clean (everything committed)" "git diff --quiet && git diff --cached --quiet"

echo ""
echo "══════════════════════════════════════════════════════════════════"
echo "  Results: $PASS passed, $FAIL failed"
echo "══════════════════════════════════════════════════════════════════"

if [ "$FAIL" -eq 0 ]; then
  echo ""
  echo "  🎉 Setup complete! All checks passed."
  echo ""
  echo "  NEXT STEPS FOR THE USER:"
  echo "  1. Edit AGENTS.md and fill in all [FILL IN] placeholders"
  echo "     with your real project stack, commands, and constraints."
  echo "  2. Authenticate each tool (one-time, interactive):"
  echo "     • Claude Code:  claude   → browser login"
  echo "     • Copilot CLI:  copilot  → type /login"
  echo "     • Gemini CLI:   gemini   → browser login"
  echo "     • Codex CLI:    codex    → browser login or set OPENAI_API_KEY"
  echo "  3. Run ./save-session.sh to get handoff prompts when switching agents."
  echo "  4. When quota runs low, paste the HANDOFF PROMPT into the current agent."
  echo "     When starting fresh, paste the NEW SESSION PROMPT into the next agent."
else
  echo ""
  echo "  ⚠️  $FAIL check(s) failed. Fix them before using the system."
fi
```

---

## AGENT COMPLETION REPORT

After running all phases, provide the user with a report in this format:

```
## Setup Complete ✅

### What was installed:
- [list tools installed, or "already present" for existing ones]

### What was created:
- [list all files and directories created]

### What needs manual action:
- Edit AGENTS.md and replace all [FILL IN] placeholders
- Authenticate each CLI tool by running it once (one-time browser login)
- [any other items specific to what was found on this machine]

### How to switch agents when quota fills:
1. Run: ./save-session.sh
2. Copy the HANDOFF PROMPT — paste it into your current agent
3. Wait for agent to update docs/PROGRESS.md and docs/HANDOFF.md
4. Open the next agent in the same directory
5. Paste the NEW SESSION PROMPT

### File map:
AGENTS.md                           ← Edit this. All other config derives from it.
CLAUDE.md                           → symlink to AGENTS.md
GEMINI.md                           → symlink to AGENTS.md
.github/copilot-instructions.md     → symlink to AGENTS.md
docs/PROGRESS.md                    ← Task tracking (agent updates this)
docs/HANDOFF.md                     ← Session handoff (agent writes this)
docs/SKILLS.md                      ← Reusable workflows (you add to this)
.gemini/settings.json               ← Gemini multi-file config
sync-agent-files.sh                 ← Run if symlinks break
save-session.sh                     ← Run to get handoff prompts
```
