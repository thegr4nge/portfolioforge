# Testing

## Framework
- **pytest 9.0.2** with pytest-cov 7.0.0
- Config in `pyproject.toml`: testpaths=["tests"], addopts="-v --tb=short"
- Run: `pytest` from project root

## Current Coverage
- `tests/test_dungeon.py` — **40 tests, all passing** (0.18s)
- No tests for fireworks.py or aquarium.py
- No tests for test_setup.py (it's a VSCode fixture)

## Test Structure
```python
class TestRoom:           # 5 tests — Room geometry
class TestPlayer:         # 2 tests — Player stats
class TestDungeonGeneration:  # 12 tests — Map generation, entities, items
class TestGameLogic:      # 21 tests — Combat, XP, potions, items, stairs, victory
```

## Test Patterns

### Fixture via `__new__`
Game.__init__ depends on terminal size, so tests bypass it:
```python
def _make_game(self) -> Game:
    game = Game.__new__(Game)
    game.term_width = 80
    game.map_width = 55
    # ... set all attributes manually
    return game
```

### Direct state manipulation
Tests set up exact conditions then assert outcomes:
```python
game.player.hp = 10
game.player.potions = 1
game.use_potion()
assert game.player.hp == 25
```

### Randomness
Dungeon generation is random — tests verify structural properties (rooms exist, stairs placed) not exact layouts.

## Gaps
- No tests for rendering logic (intentional — terminal output not meaningfully testable)
- No tests for fireworks.py or aquarium.py game logic
- No integration tests
- No coverage reporting configured (pytest-cov installed but not in addopts)
