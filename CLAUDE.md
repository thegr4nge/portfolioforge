# Uni Projects - Claude Code Config

## Project Context
University coding projects. Terminal-based Python applications (games, animations, simulations).
This is a learning environment — code should be clean and well-structured but doesn't need production-grade hardening.

## Workspace Override
Work in `~/uni-projects/` (not cybersec-workspace).
Virtual env: `source ~/uni-projects/.venv/bin/activate`

## Tech Stack
- Python 3.12 (pure stdlib for terminal apps)
- pytest for testing
- ruff for linting, black for formatting, mypy for types
- ANSI escape codes for terminal rendering

## Code Conventions
- Follow existing patterns in the codebase (dataclasses, type hints, ANSI color constants)
- Terminal apps: separate game logic from rendering where possible
- Keep files under 700 lines — split if growing beyond that
- Type hints on all functions (mypy strict mode enabled)

## Testing
- Run: `cd ~/uni-projects && source .venv/bin/activate && pytest`
- Lint: `ruff check src/`
- Types: `mypy src/`
- Focus tests on logic (combat math, state transitions) not terminal rendering

## Current Projects
- `src/fireworks.py` — Particle-based fireworks animation
- `src/dungeon.py` — Roguelike game (Depths of Shadow)
- `src/aquarium.py` — Interactive terminal aquarium
- `src/test_setup.py` — VSCode setup test (can be ignored)

## Known Issues
- test_setup.py:16 has intentional type error for IDE testing
- No tests written yet — priority for dungeon.py game logic
- Not yet a git repo — needs initialising
