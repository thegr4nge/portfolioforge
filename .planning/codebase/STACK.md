# Stack

## Language & Runtime
- **Python 3.12.3** — primary language
- **CPython** — standard runtime
- **WSL2** (Ubuntu on Windows) — development environment

## Dependencies

### Production (stdlib only)
All three terminal applications use **only Python standard library**:
- `dataclasses` — structured data
- `shutil` — terminal size detection
- `random` — procedural generation, physics
- `math` — trigonometry for particle systems
- `time` — frame timing
- `sys`, `tty`, `termios`, `select` — raw terminal input

### Installed (available but unused by current code)
- `numpy`, `pandas` — numerical/data analysis
- `matplotlib`, `plotext` — charting (GUI and terminal)
- `yfinance` — Yahoo Finance market data
- `scikit-learn` — machine learning
- `rich`, `typer` — CLI framework
- `httpx` — async HTTP client
- `beautifulsoup4` — HTML parsing

### Dev Tools
- `pytest 9.0.2` + `pytest-cov 7.0.0` — testing
- `ruff` — linting (configured in pyproject.toml)
- `black` — formatting
- `mypy` — type checking (strict mode)

## Configuration
- `pyproject.toml` — central config for ruff, pytest, mypy, black
- `.vscode/settings.json` — Python interpreter, test paths
- `.gitignore` — comprehensive Python gitignore
- No requirements.txt — deps managed via pip directly

## Build & Run
- No build step — run scripts directly: `python src/fireworks.py`
- Venv: `source .venv/bin/activate`
- Tests: `pytest` (testpaths configured to `tests/`)
