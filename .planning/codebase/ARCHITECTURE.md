# Architecture

## Pattern
**Standalone scripts with game-loop architecture.** Each project is a single file containing:
1. Constants/config (colors, templates)
2. Data classes (game entities)
3. Core engine class (state management, physics/logic, rendering)
4. Input handling (raw terminal)
5. Main loop (update → render → input → repeat)

## Entry Points
- `src/fireworks.py` — `main()` at line 199
- `src/dungeon.py` — `main()` at line 634
- `src/aquarium.py` — `main()` at line 588

## Data Flow

### Fireworks
```
Firework.spawn_rocket() → Firework.update() [physics] → Firework.render() [buffer → string]
                                ↓
                        Firework.explode() [rocket → particles]
```

### Dungeon (most complex)
```
Game.__init__() → Dungeon.generate() [rooms → tunnels → monsters → items]
     ↓
main loop: get_key() → Game.move_player() → Game.combat()/pickup_item()
                                ↓
                        Game.move_monsters() [simple AI: chase if within 6 tiles]
                                ↓
                        Game.render() [map + stats panel + messages]
```

### Aquarium
```
Aquarium.__init__() → setup_environment() [seaweed, coral, decorations]
     ↓                spawn_initial_fish()
main loop: Aquarium.update() [fish movement, bubbles, food chasing]
                ↓
           Aquarium.render() [layered: bg → decorations → seaweed → bubbles → food → fish]
```

## Key Abstractions
- `@dataclass` for all entities (Particle, Entity, Item, Room, Fish, Bubble, etc.)
- Color constants as class attributes (C.RED, C.BLUE, etc.)
- Buffer-based rendering: 2D char array + color array → assembled string
- No inheritance — flat class hierarchies

## Layering
No formal layers. Each file is self-contained. No shared code between projects.
The `src/__init__.py` and `tests/__init__.py` are placeholder files with only comments.
