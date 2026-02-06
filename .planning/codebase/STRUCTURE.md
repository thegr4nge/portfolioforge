# Structure

## Directory Layout
```
~/uni-projects/
├── .claude/
│   └── commands/           # Project-level Claude commands
│       ├── debug.md
│       ├── feature-spec.md
│       ├── new-project.md
│       ├── refactor.md
│       ├── review.md
│       └── test-gen.md
├── .planning/
│   └── codebase/           # This codebase map
├── .venv/                  # Python 3.12 virtual environment
├── .vscode/
│   └── settings.json       # Python path, test config
├── CLAUDE.md               # Project-level Claude config
├── claude-code-audit.md    # Environment audit report
├── pyproject.toml          # ruff, pytest, mypy, black config
├── .gitignore
├── src/
│   ├── __init__.py         # Placeholder
│   ├── fireworks.py        # 247 lines — particle fireworks animation
│   ├── dungeon.py          # 688 lines — roguelike game
│   ├── aquarium.py         # 632 lines — interactive aquarium
│   └── test_setup.py       # 17 lines — VSCode test fixture (has intentional type error)
└── tests/
    ├── __init__.py          # Placeholder
    └── test_dungeon.py      # 40 tests for dungeon game logic
```

## Key Locations
| What | Where |
|------|-------|
| Source code | `src/` |
| Tests | `tests/` |
| Project config | `pyproject.toml` |
| Linter config | `pyproject.toml` [tool.ruff] |
| Type checker config | `pyproject.toml` [tool.mypy] |

## Naming Conventions
- Files: `snake_case.py`
- Tests: `tests/test_<module>.py`
- Classes: `PascalCase` (Firework, Dungeon, Game, Aquarium)
- Functions: `snake_case` (spawn_rocket, move_player)
- Constants: `UPPER_CASE` (COLORS, MONSTERS, FISH_TYPES)
- Color class: single letter `C` with class attributes
