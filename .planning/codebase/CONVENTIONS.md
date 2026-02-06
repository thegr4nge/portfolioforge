# Conventions

## Code Style
- **Formatter:** black (line-length 88)
- **Linter:** ruff with rules: E, F, W, I, N, UP, B, A, C4, PT, SIM, ERA
- **Type checker:** mypy strict (disallow_untyped_defs, warn_return_any)
- **Ignored:** E501 (line length handled by formatter)

## Patterns

### Data Modeling
All entities use `@dataclass`:
```python
@dataclass
class Entity:
    x: int
    y: int
    char: str
    color: str
    name: str
    hp: int
```

### Color Constants
Centralized as class attributes, not module-level dicts:
```python
class C:
    RED = "\033[91m"
    GREEN = "\033[92m"
    RESET = "\033[0m"
```

### Rendering
Buffer-based: build 2D arrays, then assemble into string:
```python
buffer = [[" " for _ in range(width)] for _ in range(height)]
# ... populate buffer ...
return "\n".join("".join(row) for row in buffer)
```

### Terminal Setup/Teardown
```python
print("\033[?25l", end="")  # Hide cursor
try:
    while True: ...
finally:
    print("\033[?25h", end="")  # Show cursor
    print("\033[0m", end="")     # Reset
```

### Input Handling
Two patterns:
1. **Blocking** (dungeon.py): `tty.setraw()` + `sys.stdin.read(1)`
2. **Non-blocking** (aquarium.py): `select.select()` with timeout

## Error Handling
- Minimal — `KeyboardInterrupt` caught for clean exit
- No try/except within game logic
- No logging (print-based output only)

## Type Hints
- Present on most function signatures
- Some missing return type annotations (mypy flagged ~39 errors)
- `X | None` preferred over `Optional[X]` (ruff auto-fixed)
