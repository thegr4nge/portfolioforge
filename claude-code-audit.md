# Claude Code Self-Audit Report
**Date:** 2026-02-06
**Project:** ~/uni-projects (University coding projects)
**Overall Score: 4/10**

---

## PHASE 1: ENVIRONMENT INVENTORY

### 1.1 Model & Version
| Item | Status |
|------|--------|
| Claude Code version | 2.1.33 (current) |
| Default model (global) | `sonnet` (set in settings.json) |
| Current session model | `opus-4-6` (override via --dangerously-skip-permissions) |
| Adaptive thinking | Not explicitly configured |

**Note:** Global settings default to Sonnet. You're on Opus for this session only. For complex coding tasks, Opus is better but costs more.

### 1.2 CLAUDE.md Assessment
| Item | Status |
|------|--------|
| Global ~/.claude/CLAUDE.md | EXISTS - cybersecurity-focused config (~3,900 tokens) |
| Project-level CLAUDE.md | MISSING |

**Global CLAUDE.md audit:**
- Coding standards: YES (Python conventions, code quality rules)
- Architectural decisions: NO (generic, not project-specific)
- Known pitfalls: NO
- PR/commit conventions: NO
- Testing requirements: YES (TDD, verification checklist)
- Token count: ~3,900 - slightly over ideal range but content is high-signal
- **Issue:** Workspace restriction says "Work within `~/cybersec-workspace/` only" - conflicts with working in ~/uni-projects
- **Issue:** Venv path hardcoded to cybersec-workspace

### 1.3 MCP Servers
| Server | Status | Notes |
|--------|--------|-------|
| osint-wrapper | CONNECTED | Cybersec-specific |
| playwright | CONNECTED | Browser automation |
| context7 | CONNECTED | Library docs |
| memory | CONNECTED | Knowledge graph |
| GitHub MCP | MISSING | No gh auth either |
| Sequential Thinking | MISSING | |
| Filesystem MCP | MISSING | Not needed (built-in tools cover this) |
| Database MCP | N/A | No database in project |
| Docker MCP | MISSING | Docker is available though |

### 1.4 Custom Commands
**Global (~/.claude/commands/):** 14 commands exist, all cybersec/OSINT focused:
- build-tool, case, enrich, investigate, ioc, netanalyze, osint-profile, recon, secreview, timeline, vulnscan
- Plus `gsd/` and `intel/` subdirectories

**Project-level:** NONE - no `.claude/commands/` directory in uni-projects

**Missing for uni workflow:**
- No test generation command
- No code review command
- No assignment/feature scaffolding command
- No debug workflow command

### 1.5 Plugins
- Plugin directory exists at `~/.claude/plugins/` but contents not inspected in detail
- No project-level plugins

### 1.6 Hooks & Automation
| Hook | Status |
|------|--------|
| PreToolUse: Bash audit logging | ACTIVE - logs to ~/cybersec-workspace/.security-logs/ |
| PostToolUse: Python syntax check | ACTIVE - runs py_compile on .py writes |
| SessionStart: GSD update check | ACTIVE |
| Status line | ACTIVE (custom JS) |
| Pre-commit hooks (git) | NOT APPLICABLE - not a git repo |
| CI/CD | NONE |

### 1.7 Git & Workflow
| Item | Status |
|------|--------|
| Git repo | **NO** - uni-projects is NOT a git repo |
| gh CLI | Not authenticated |
| Branching strategy | N/A |
| Git worktree | N/A |

**This is the biggest issue.** No version control on university code.

### 1.8 Project Structure
```
~/uni-projects/
├── .gitignore          # Exists but no git repo!
├── .venv/              # Python 3.12.3, ~130 packages
├── .vscode/            # Configured for Python + Cursorpyright
├── pyproject.toml      # ruff + pytest + mypy + black configured
├── src/
│   ├── __init__.py     # Just a comment
│   ├── aquarium.py     # Terminal aquarium animation (632 lines)
│   ├── dungeon.py      # Roguelike game (688 lines)
│   ├── fireworks.py    # Terminal fireworks (247 lines)
│   └── test_setup.py   # Broken test file (type error on line 16)
└── tests/
    └── __init__.py     # Empty - NO TESTS
```

**Tech stack:** Pure Python 3.12, terminal animations, no external dependencies beyond stdlib
**Linting:** ruff, black, mypy all configured in pyproject.toml
**Tests:** pytest configured but 0 tests exist
**Known bug:** `test_setup.py:16` has intentional type error (`x: int = "not an integer"`)

---

## PHASE 2: GAP ANALYSIS

### 🔴 CRITICAL

**1. No Git Repository**
- **What:** ~/uni-projects has a .gitignore but `git init` was never run
- **Impact:** No version history, no undo, no backup. One bad edit = lost work
- **Fix:** Quick (2 min)

**2. No Project-Level CLAUDE.md**
- **What:** No project-specific instructions for Claude Code
- **Impact:** Claude doesn't know this is a uni project, uses cybersec defaults (wrong workspace path, wrong venv)
- **Fix:** Quick (5 min)

**3. Global CLAUDE.md Conflicts**
- **What:** Says "Work within `~/cybersec-workspace/` only" and venv path points there
- **Impact:** Technically violating own rules working in ~/uni-projects
- **Fix:** Quick - add project-level override

### 🟡 HIGH IMPACT

**4. Zero Tests**
- **What:** pytest configured, tests/ directory exists, but no test files
- **Impact:** No confidence code works correctly, no regression safety
- **Fix:** Medium (tests for these terminal apps would be unit tests on game logic, not rendering)

**5. No GitHub CLI / Remote**
- **What:** gh not authenticated, no remote repository
- **Impact:** No backup, no collaboration, can't submit assignments via GitHub if required
- **Fix:** Medium (need GitHub account setup)

**6. No Project-Level Custom Commands**
- **What:** All custom commands are cybersec-focused, none for uni work
- **Impact:** Missing workflows for: test generation, code review, assignment scaffolding
- **Fix:** Quick (5 min per command)

**7. Missing Sequential Thinking MCP**
- **What:** Not installed
- **Impact:** Complex multi-step reasoning (algorithm design, debugging) less structured
- **Fix:** Quick (1 command)

### 🟢 NICE TO HAVE

**8. No MEMORY.md Content**
- **What:** Auto-memory file at ~/.claude/projects/-home-hntr/memory/ is empty
- **Impact:** Claude doesn't learn from previous sessions in this workspace
- **Fix:** Ongoing (builds naturally)

**9. Source Files Are Large**
- **What:** aquarium.py (632 lines) and dungeon.py (688 lines) approach limits
- **Impact:** Not a problem yet, but worth noting for future additions
- **Fix:** Only if refactoring is needed

**10. test_setup.py Has Intentional Bug**
- **What:** Type error on line 16, appears to be a VSCode test fixture
- **Impact:** mypy will flag it, confusing
- **Fix:** Quick (delete or fix)

---

## PHASE 3: OPTIMISATION PLAN

### Immediate Actions (this session, <5 min each)

- [ ] **1. Init git repo** — `git init && git add -A && git commit -m "Initial commit"`
- [ ] **2. Create project CLAUDE.md** — Uni-specific config overriding cybersec defaults
- [ ] **3. Install Sequential Thinking MCP** — `claude mcp add sequential-thinking -- npx -y @modelcontextprotocol/server-sequential-thinking`
- [ ] **4. Create project .claude/commands/** — Starter commands for uni workflow

### Short-Term (next session, <30 min)

- [ ] **5. Write tests** — Unit tests for dungeon.py game logic (combat, XP, movement)
- [ ] **6. Setup GitHub remote** — `gh auth login` + create private repo
- [ ] **7. Fix test_setup.py** — Remove intentional type error or delete file
- [ ] **8. Run linters** — `ruff check src/` and `mypy src/` to baseline code quality

### Ongoing Practices

- [ ] **9. Commit after each coding session** — Build git history
- [ ] **10. Update MEMORY.md** — Record patterns and learnings
- [ ] **11. Write tests for new code** — Adopt TDD for new assignments
- [ ] **12. Use plan mode** — For non-trivial features, plan before coding

---

## PHASE 4: PROJECT CLAUDE.md (Draft)

See below for the recommended `~/uni-projects/CLAUDE.md` content.

---

## PHASE 5: CUSTOM COMMANDS

See below for recommended project-level commands.

---

## PHASE 6: MCP INSTALLATION COMMANDS

```bash
# Sequential Thinking — structured problem solving
claude mcp add sequential-thinking -- npx -y @modelcontextprotocol/server-sequential-thinking

# GitHub MCP — requires personal access token
# First: gh auth login (or create token at github.com/settings/tokens)
# Then:
# claude mcp add-json github '{"command":"npx","args":["-y","@modelcontextprotocol/server-github"],"env":{"GITHUB_PERSONAL_ACCESS_TOKEN":"YOUR_TOKEN"}}'
```

**Already installed and working:**
- context7 (library docs)
- memory (knowledge graph)
- playwright (browser automation)
- osint-wrapper (cybersec — not needed for uni but no harm)

**Not recommended for this project:**
- Database MCP (no DB usage)
- Docker MCP (overkill for terminal Python apps)
- Filesystem MCP (built-in tools sufficient)

---

## PHASE 7: SUMMARY

### Current Setup Score: 4/10
- Good: Python tooling configured (ruff, pytest, mypy, black), MCP servers for docs/memory, solid global CLAUDE.md
- Bad: No git, no tests, no project CLAUDE.md, workspace path conflicts, no custom commands for uni work

### Top 3 Highest-Impact Changes
1. **Init git** — 2 minutes, massive safety net for all your code
2. **Create project CLAUDE.md** — 5 minutes, makes Claude actually useful for uni work instead of defaulting to cybersec mode
3. **Write basic tests for dungeon.py** — 20 minutes, dungeon has the most testable logic (combat math, XP leveling, room generation)

### Before/After Capabilities
| Capability | Before | After |
|------------|--------|-------|
| Version control | NONE | Full git history |
| Claude context | Cybersec defaults | Uni-project aware |
| Test safety | Zero coverage | Core logic tested |
| Workflow commands | Cybersec only | Uni-relevant commands |
| Code recovery | Impossible | git checkout |
