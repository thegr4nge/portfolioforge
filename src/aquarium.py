#!/usr/bin/env python3
"""
DEEP BLUE AQUARIUM
A beautiful, detailed aquarium for your terminal.
"""

import random
import select
import shutil
import sys
import termios
import time
import tty
from dataclasses import dataclass
from math import pi, sin


# === COLORS ===
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Water gradient
    WATER_1 = "\033[48;5;17m"   # Deep blue bg
    WATER_2 = "\033[48;5;18m"
    WATER_3 = "\033[48;5;19m"
    WATER_4 = "\033[48;5;20m"   # Lighter blue bg

    # Fish colors
    ORANGE = "\033[38;5;208m"
    GOLD = "\033[38;5;220m"
    BRIGHT_GOLD = "\033[38;5;226m"
    RED = "\033[38;5;196m"
    CRIMSON = "\033[38;5;160m"
    BLUE = "\033[38;5;39m"
    LIGHT_BLUE = "\033[38;5;117m"
    CYAN = "\033[38;5;51m"
    MAGENTA = "\033[38;5;201m"
    PURPLE = "\033[38;5;129m"
    GREEN = "\033[38;5;46m"
    LIME = "\033[38;5;118m"
    PINK = "\033[38;5;213m"
    HOT_PINK = "\033[38;5;199m"
    YELLOW = "\033[38;5;226m"
    WHITE = "\033[38;5;255m"
    SILVER = "\033[38;5;250m"
    GRAY = "\033[38;5;245m"

    # Environment
    SAND_LIGHT = "\033[38;5;223m"
    SAND = "\033[38;5;180m"
    SAND_DARK = "\033[38;5;137m"
    SEAWEED_DARK = "\033[38;5;22m"
    SEAWEED = "\033[38;5;28m"
    SEAWEED_LIGHT = "\033[38;5;40m"
    CORAL_PINK = "\033[38;5;205m"
    CORAL_RED = "\033[38;5;196m"
    CORAL_ORANGE = "\033[38;5;208m"
    CORAL_PURPLE = "\033[38;5;134m"
    ROCK = "\033[38;5;240m"
    ROCK_LIGHT = "\033[38;5;245m"
    BUBBLE = "\033[38;5;159m"
    BUBBLE_SHINE = "\033[38;5;231m"
    TREASURE = "\033[38;5;178m"
    SHELL_PINK = "\033[38;5;218m"
    STARFISH = "\033[38;5;209m"


# Fish templates: (right-facing, left-facing, colors, name, speed)
FISH_TYPES = [
    # Tiny fish
    ("><>", "<><", [C.SILVER], "Minnow", 0.6),
    ("°>", "<°", [C.LIGHT_BLUE], "Tiny", 0.7),

    # Small colorful fish
    ("><(°>", "<°)><", [C.ORANGE, C.WHITE], "Clownfish", 0.45),
    (">°))'>", "<'((°<", [C.CYAN], "Neon Tetra", 0.5),
    ("><))°>", "<°((<><", [C.HOT_PINK], "Pink Danio", 0.5),
    (">=<>", "<>=<", [C.YELLOW, C.ORANGE], "Guppy", 0.55),
    (">°>=>", "<=<°<", [C.LIME], "Green Barb", 0.5),

    # Medium fish
    (">°))))'>>", "<<'((((°<", [C.BLUE, C.YELLOW], "Angelfish", 0.3),
    ("><(((°>", "<°)))><", [C.GOLD, C.ORANGE], "Goldfish", 0.35),
    (">=)))°>", "<°(((=<", [C.PURPLE, C.PINK], "Betta", 0.25),
    (">°})))>", "<(((}°<", [C.CRIMSON], "Discus", 0.3),

    # Large fish
    ("><((((°>", "<°))))><", [C.SILVER, C.BLUE], "Koi", 0.2),
    (">=<((((°>=>", "<=<°))))>=<", [C.GRAY, C.WHITE], "Carp", 0.18),

    # Special
    (">°))))))))>>", "<<((((((((°<", [C.GRAY, C.SILVER], "Shark", 0.15),
]


@dataclass
class Fish:
    x: float
    y: float
    fish_type: int
    direction: int  # 1 = right, -1 = left
    speed: float
    wobble_offset: float
    vertical_speed: float = 0
    target_y: float | None = None

    @property
    def template(self):
        return FISH_TYPES[self.fish_type]

    @property
    def sprite(self) -> str:
        if self.direction > 0:
            return self.template[0]
        return self.template[1]

    @property
    def colors(self) -> list:
        return self.template[2]

    @property
    def width(self) -> int:
        return len(self.template[0])


@dataclass
class Bubble:
    x: float
    y: float
    speed: float
    size: int  # 0=tiny, 1=small, 2=medium
    wobble_offset: float


@dataclass
class FoodParticle:
    x: float
    y: float
    speed: float


@dataclass
class Seaweed:
    x: int
    height: int
    phase: float
    style: int  # 0=wavy, 1=broad leaf


@dataclass
class Coral:
    x: int
    y: int
    style: int
    color: str


@dataclass
class Decoration:
    x: int
    y: int
    dtype: str  # "rock", "shell", "star", "chest"


class Aquarium:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.water_height = height - 4

        self.fish: list[Fish] = []
        self.bubbles: list[Bubble] = []
        self.food: list[FoodParticle] = []
        self.seaweed: list[Seaweed] = []
        self.corals: list[Coral] = []
        self.decorations: list[Decoration] = []

        self.time = 0
        self.frame = 0

        self.setup_environment()
        self.spawn_initial_fish(6)

    def setup_environment(self):
        # Seaweed clusters
        num_seaweed = self.width // 12
        for i in range(num_seaweed):
            base_x = random.randint(3, self.width - 4)
            # Cluster of 2-3 seaweed
            for j in range(random.randint(1, 3)):
                x = base_x + j * 2
                if x < self.width - 2:
                    height = random.randint(5, min(10, self.water_height - 2))
                    style = random.randint(0, 1)
                    self.seaweed.append(Seaweed(x, height, random.uniform(0, 2*pi), style))

        # Coral formations
        num_coral = self.width // 15
        for _ in range(num_coral):
            x = random.randint(2, self.width - 8)
            y = self.water_height
            style = random.randint(0, 2)
            colors = [C.CORAL_PINK, C.CORAL_RED, C.CORAL_ORANGE, C.CORAL_PURPLE]
            self.corals.append(Coral(x, y, style, random.choice(colors)))

        # Decorations
        # Rocks
        for _ in range(random.randint(2, 4)):
            x = random.randint(1, self.width - 6)
            self.decorations.append(Decoration(x, self.water_height, "rock"))

        # Shells
        for _ in range(random.randint(2, 3)):
            x = random.randint(1, self.width - 3)
            self.decorations.append(Decoration(x, self.height - 3, "shell"))

        # Starfish
        for _ in range(random.randint(1, 2)):
            x = random.randint(1, self.width - 3)
            self.decorations.append(Decoration(x, self.height - 3, "star"))

        # Treasure chest
        if self.width > 40:
            x = random.randint(self.width // 2, self.width - 12)
            self.decorations.append(Decoration(x, self.water_height - 1, "chest"))

    def spawn_initial_fish(self, count: int):
        for _ in range(count):
            self.add_fish()

    def add_fish(self):
        fish_type = random.randint(0, len(FISH_TYPES) - 1)
        template = FISH_TYPES[fish_type]

        direction = random.choice([-1, 1])
        x = -len(template[0]) if direction > 0 else self.width + 5
        y = random.uniform(2, self.water_height - 3)

        base_speed = template[4]
        speed = base_speed * random.uniform(0.9, 1.1)

        self.fish.append(Fish(
            x=x, y=y,
            fish_type=fish_type,
            direction=direction,
            speed=speed,
            wobble_offset=random.uniform(0, 2*pi)
        ))

    def remove_fish(self):
        if len(self.fish) > 1:
            self.fish.pop(random.randint(0, len(self.fish) - 1))

    def feed(self):
        for _ in range(random.randint(8, 15)):
            self.food.append(FoodParticle(
                x=random.uniform(5, self.width - 5),
                y=1,
                speed=random.uniform(0.08, 0.15)
            ))

    def spawn_bubble(self):
        # Spawn from seaweed or random
        if self.seaweed and random.random() < 0.7:
            sw = random.choice(self.seaweed)
            x = sw.x
        else:
            x = random.randint(3, self.width - 3)

        self.bubbles.append(Bubble(
            x=float(x),
            y=float(self.water_height - 1),
            speed=random.uniform(0.15, 0.35),
            size=random.choices([0, 1, 2], weights=[5, 3, 1])[0],
            wobble_offset=random.uniform(0, 2*pi)
        ))

    def update(self):
        self.time += 0.1
        self.frame += 1

        # Update fish
        for fish in self.fish[:]:
            # Horizontal movement
            fish.x += fish.direction * fish.speed

            # Smooth vertical wobble
            wobble = sin(self.time * 2 + fish.wobble_offset) * 0.08

            # Chase food
            if self.food:
                nearest = min(self.food, key=lambda f: abs(f.x - fish.x) + abs(f.y - fish.y))
                dist = abs(nearest.x - fish.x) + abs(nearest.y - fish.y)
                if dist < 12:
                    fish.target_y = nearest.y
                    # Turn toward food
                    if nearest.x < fish.x and fish.direction > 0:
                        fish.direction = -1
                    elif nearest.x > fish.x and fish.direction < 0:
                        fish.direction = 1

            # Move toward target
            if fish.target_y is not None:
                diff = fish.target_y - fish.y
                fish.y += diff * 0.08
                if abs(diff) < 0.3:
                    fish.target_y = None
            else:
                fish.y += wobble
                if random.random() < 0.01:
                    fish.target_y = random.uniform(2, self.water_height - 3)

            # Boundaries
            fish.y = max(1, min(self.water_height - 2, fish.y))

            # Wrap/turn
            if fish.direction > 0 and fish.x > self.width + 5:
                fish.direction = -1
                fish.y = random.uniform(2, self.water_height - 3)
            elif fish.direction < 0 and fish.x < -fish.width - 5:
                fish.direction = 1
                fish.y = random.uniform(2, self.water_height - 3)

        # Update bubbles
        for bubble in self.bubbles[:]:
            bubble.y -= bubble.speed
            bubble.x += sin(self.time * 3 + bubble.wobble_offset) * 0.12
            if bubble.y < 0:
                self.bubbles.remove(bubble)

        # Spawn bubbles
        if random.random() < 0.08:
            self.spawn_bubble()

        # Update food
        for food in self.food[:]:
            food.y += food.speed
            food.x += sin(self.time * 0.5 + food.x * 0.1) * 0.03

            # Eaten by fish
            for fish in self.fish:
                if abs(fish.x + fish.width/2 - food.x) < fish.width/2 + 1 and abs(fish.y - food.y) < 1.5:
                    if food in self.food:
                        self.food.remove(food)
                    break
            else:
                if food.y >= self.water_height - 1:
                    if food in self.food:
                        self.food.remove(food)

    def get_water_bg(self, y: int) -> str:
        """Get water background color based on depth."""
        ratio = y / self.water_height
        if ratio < 0.25:
            return C.WATER_4
        elif ratio < 0.5:
            return C.WATER_3
        elif ratio < 0.75:
            return C.WATER_2
        return C.WATER_1

    def render(self) -> str:
        # Create buffers
        buffer = [[" " for _ in range(self.width)] for _ in range(self.height)]
        fg_color = [["" for _ in range(self.width)] for _ in range(self.height)]
        bg_color = [["" for _ in range(self.width)] for _ in range(self.height)]

        # Water background with gradient
        for y in range(self.water_height):
            bg = self.get_water_bg(y)
            for x in range(self.width):
                bg_color[y][x] = bg
                # Subtle caustics/light rays
                if (x + y + int(self.time * 2)) % 12 == 0 and y < self.water_height // 2:
                    buffer[y][x] = "░"
                    fg_color[y][x] = C.LIGHT_BLUE

        # Sand layers
        for y in range(self.water_height, self.height):
            for x in range(self.width):
                depth = y - self.water_height
                if depth == 0:
                    buffer[y][x] = "▓"
                    fg_color[y][x] = C.SAND_LIGHT
                elif depth == 1:
                    buffer[y][x] = "▒"
                    fg_color[y][x] = C.SAND
                else:
                    buffer[y][x] = "░"
                    fg_color[y][x] = C.SAND_DARK

        # Draw decorations (back layer)
        for dec in self.decorations:
            if dec.dtype == "rock":
                # Rock formation
                rock = [
                    "  ite  ",
                    " XiiteX ",
                    "XiititeX",
                ]
                for dy, row in enumerate(rock):
                    y = dec.y - len(rock) + dy + 1
                    for dx, ch in enumerate(row):
                        x = dec.x + dx
                        if 0 <= x < self.width and 0 <= y < self.height and ch != " ":
                            if ch in "Xx":
                                buffer[y][x] = "█"
                                fg_color[y][x] = C.ROCK
                            elif ch == "i":
                                buffer[y][x] = "▓"
                                fg_color[y][x] = C.ROCK
                            elif ch in "te":
                                buffer[y][x] = "▒"
                                fg_color[y][x] = C.ROCK_LIGHT

            elif dec.dtype == "chest":
                chest = [
                    " ▄███▄ ",
                    "█$███$█",
                    "▀▀▀▀▀▀▀",
                ]
                for dy, row in enumerate(chest):
                    y = dec.y - len(chest) + dy + 2
                    for dx, ch in enumerate(row):
                        x = dec.x + dx
                        if 0 <= x < self.width and 0 <= y < self.height and ch != " ":
                            buffer[y][x] = ch
                            fg_color[y][x] = C.TREASURE if ch == "$" else C.SAND_DARK

            elif dec.dtype == "shell":
                x, y = dec.x, dec.y
                if 0 <= x < self.width - 2 and 0 <= y < self.height:
                    buffer[y][x] = "("
                    buffer[y][x+1] = "@"
                    buffer[y][x+2] = ")"
                    fg_color[y][x] = fg_color[y][x+1] = fg_color[y][x+2] = C.SHELL_PINK

            elif dec.dtype == "star":
                x, y = dec.x, dec.y
                if 0 <= x < self.width and 0 <= y < self.height:
                    buffer[y][x] = "✦"
                    fg_color[y][x] = C.STARFISH

        # Draw coral
        for coral in self.corals:
            if coral.style == 0:  # Branching
                shapes = [
                    "  Y  ",
                    " YYY ",
                    "  Y  ",
                ]
            elif coral.style == 1:  # Brain coral
                shapes = [
                    " ╭─╮ ",
                    "╭┴─┴╮",
                    "╰───╯",
                ]
            else:  # Fan coral
                shapes = [
                    " \\|/ ",
                    " )│( ",
                    "  │  ",
                ]

            for dy, row in enumerate(shapes):
                y = coral.y - len(shapes) + dy
                for dx, ch in enumerate(row):
                    x = coral.x + dx
                    if 0 <= x < self.width and 0 <= y < self.height and ch != " ":
                        buffer[y][x] = ch
                        fg_color[y][x] = coral.color

        # Draw seaweed
        for sw in self.seaweed:
            wave = sin(self.time * 1.2 + sw.phase)
            for i in range(sw.height):
                y = self.water_height - 1 - i
                sway = wave * (i / sw.height) * 1.5
                x = sw.x + int(sway)

                if 0 <= x < self.width and 0 <= y < self.height:
                    # Color gradient
                    if i < sw.height * 0.3:
                        color = C.SEAWEED_DARK
                    elif i < sw.height * 0.7:
                        color = C.SEAWEED
                    else:
                        color = C.SEAWEED_LIGHT

                    if sw.style == 0:  # Wavy
                        chars = [")", "(", "}", "{"]
                        buffer[y][x] = chars[int(self.time + i) % 4]
                    else:  # Broad leaf
                        buffer[y][x] = "|" if i % 3 != 0 else "}"

                    fg_color[y][x] = color

        # Draw bubbles
        for bubble in self.bubbles:
            x, y = int(bubble.x), int(bubble.y)
            if 0 <= x < self.width and 0 <= y < self.water_height:
                if bubble.size == 0:
                    buffer[y][x] = "·"
                elif bubble.size == 1:
                    buffer[y][x] = "°"
                else:
                    buffer[y][x] = "○"
                fg_color[y][x] = C.BUBBLE_SHINE if bubble.size == 2 else C.BUBBLE

        # Draw food
        for food in self.food:
            x, y = int(food.x), int(food.y)
            if 0 <= x < self.width and 0 <= y < self.water_height:
                buffer[y][x] = "•"
                fg_color[y][x] = C.BRIGHT_GOLD

        # Draw fish (front layer)
        for fish in sorted(self.fish, key=lambda f: len(f.sprite)):
            sprite = fish.sprite
            colors = fish.colors
            y = int(fish.y)

            for i, char in enumerate(sprite):
                x = int(fish.x) + i
                if 0 <= x < self.width and 0 <= y < self.water_height:
                    buffer[y][x] = char
                    # Alternate colors for pattern
                    color_idx = (i // 2) % len(colors)
                    fg_color[y][x] = colors[color_idx]

        # Build output
        lines = []

        # Top border
        lines.append(f"{C.BLUE}╔{'═' * (self.width)}╗{C.RESET}")

        # Title bar
        title = "  ><(((°>  DEEP BLUE AQUARIUM  <°)))><  "
        pad = (self.width - len(title)) // 2
        title_line = f"{C.BLUE}║{C.RESET}{' ' * pad}{C.BOLD}{C.CYAN}{title}{C.RESET}{' ' * (self.width - pad - len(title))}{C.BLUE}║{C.RESET}"
        lines.append(title_line)
        lines.append(f"{C.BLUE}╠{'═' * (self.width)}╣{C.RESET}")

        # Render main area
        for y in range(self.height):
            line = f"{C.BLUE}║{C.RESET}"
            for x in range(self.width):
                bg = bg_color[y][x] if bg_color[y][x] else ""
                fg = fg_color[y][x] if fg_color[y][x] else ""
                char = buffer[y][x]
                line += f"{bg}{fg}{char}{C.RESET}"
            line += f"{C.BLUE}║{C.RESET}"
            lines.append(line)

        # Bottom border
        lines.append(f"{C.BLUE}╚{'═' * (self.width)}╝{C.RESET}")

        # Status bar
        fish_count = len(self.fish)
        status = f" {C.CYAN}Fish:{C.WHITE} {fish_count}  {C.GRAY}│  [F]eed  [+]Add  [-]Remove  [Q]uit{C.RESET}"
        lines.append(status)

        return "\n".join(lines)


def get_key_nonblocking() -> str | None:
    """Non-blocking key read."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        rlist, _, _ = select.select([sys.stdin], [], [], 0.01)
        if rlist:
            ch = sys.stdin.read(1)
            # Handle escape sequences for special keys
            if ch == '\x1b':
                sys.stdin.read(2)  # consume rest of escape sequence
                return None
            return ch
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main():
    size = shutil.get_terminal_size()
    width = min(size.columns - 4, 90)
    height = min(size.lines - 8, 25)

    aquarium = Aquarium(width, height)

    # Setup terminal
    print("\033[?25l", end="")  # Hide cursor
    print("\033[2J", end="")     # Clear screen

    try:
        while True:
            print("\033[H", end="")  # Home cursor
            print(aquarium.render(), flush=True)

            aquarium.update()

            # Check input
            key = get_key_nonblocking()
            if key:
                k = key.lower()
                if k == 'q':
                    break
                elif k == 'f':
                    aquarium.feed()
                elif key in ['+', '=']:
                    aquarium.add_fish()
                elif key in ['-', '_']:
                    aquarium.remove_fish()

            time.sleep(0.04)  # ~25 FPS

    except KeyboardInterrupt:
        pass
    finally:
        print("\033[?25h", end="")  # Show cursor
        print("\033[0m", end="")     # Reset colors
        print("\033[2J\033[H", end="")
        print("Thanks for visiting the aquarium! 🐠")


if __name__ == "__main__":
    main()
