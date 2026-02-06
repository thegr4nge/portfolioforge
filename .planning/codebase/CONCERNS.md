# Concerns

## Technical Debt

### TD-01: No shared utilities
Each file reimplements terminal setup/teardown, color constants, and buffer rendering. If a fourth project is added, this duplication grows.
- **Severity:** Low (3 files)
- **Impact:** Copy-paste errors when adding new projects

### TD-02: File sizes approaching limits
- `dungeon.py`: 688 lines
- `aquarium.py`: 632 lines
- Both are monolithic — all logic in one file
- **Severity:** Medium
- **Impact:** Harder to navigate, test, and extend

### TD-03: Missing return type annotations
mypy reports 39 errors, mostly missing `-> None` on void functions.
- **Severity:** Low
- **Impact:** Type checker noise, reduced IDE assistance

### TD-04: test_setup.py has intentional type error
`src/test_setup.py:16` — `x: int = "not an integer"` — appears to be a VSCode test fixture left in source.
- **Severity:** Low
- **Impact:** mypy always reports 1 error from this file

## Performance Concerns

### PERF-01: List.remove() in hot loops
Both fireworks.py and aquarium.py iterate lists and call `.remove()` during iteration:
```python
for p in self.particles[:]:
    ...
    self.particles.remove(p)  # O(n) each call
```
- **Severity:** Low (terminal rendering is the bottleneck, not list ops)
- **Impact:** Could matter with very large particle counts

### PERF-02: O(n) entity lookups
`dungeon.py` — `get_entity_at()` and `get_item_at()` scan full lists:
```python
def get_entity_at(self, x, y):
    for e in self.entities:
        if e.x == x and e.y == y:
            return e
```
- **Severity:** Low (entity counts are small, <20)
- **Impact:** Would need spatial indexing if entity counts grew significantly

## Security
No security concerns — all applications are offline, single-user, no network, no file I/O, no user input beyond keyboard.

## Fragile Areas

### Monster movement during iteration
`dungeon.py:405` — `move_monsters()` modifies entity positions while iterating the same list. Currently safe because it doesn't add/remove, but fragile if death-during-movement is added.

### Terminal state on crash
If any app crashes (unhandled exception), terminal may be left in raw mode with hidden cursor. The `finally` blocks handle `KeyboardInterrupt` but not all exceptions.
