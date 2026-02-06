#!/usr/bin/env python3
"""
Terminal Fireworks Show
A mesmerizing particle-based fireworks display in your terminal.
Press Ctrl+C to exit.
"""

import random
import shutil
import sys
import time
from dataclasses import dataclass
from math import cos, sin, pi


# Terminal colors (ANSI)
COLORS = [
    "\033[91m",  # Red
    "\033[93m",  # Yellow
    "\033[92m",  # Green
    "\033[96m",  # Cyan
    "\033[94m",  # Blue
    "\033[95m",  # Magenta
    "\033[97m",  # White
    "\033[38;5;208m",  # Orange
    "\033[38;5;213m",  # Pink
    "\033[38;5;226m",  # Bright Yellow
]
RESET = "\033[0m"
SPARKLE_CHARS = ["*", ".", "+", "x", "o", "°", "·", "★", "✦", "✧", "❋", "✺"]


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    color: str
    char: str
    life: float
    max_life: float
    trail: list


class Firework:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.particles: list[Particle] = []
        self.rockets: list[Particle] = []
        self.gravity = 0.05
        self.spawn_rocket()

    def spawn_rocket(self):
        """Launch a new rocket from the bottom."""
        x = random.randint(int(self.width * 0.2), int(self.width * 0.8))
        rocket = Particle(
            x=float(x),
            y=float(self.height - 1),
            vx=random.uniform(-0.3, 0.3),
            vy=random.uniform(-1.8, -1.2),
            color=random.choice(COLORS),
            char="│",
            life=random.randint(15, 25),
            max_life=30,
            trail=[],
        )
        self.rockets.append(rocket)

    def explode(self, x: float, y: float, color: str):
        """Create explosion particles at the given position."""
        num_particles = random.randint(30, 60)
        explosion_color = color if random.random() > 0.3 else random.choice(COLORS)

        # Different explosion patterns
        pattern = random.choice(["circle", "star", "double", "spiral"])

        for i in range(num_particles):
            if pattern == "circle":
                angle = (2 * pi * i) / num_particles + random.uniform(-0.2, 0.2)
                speed = random.uniform(0.5, 1.5)
            elif pattern == "star":
                angle = (2 * pi * i) / num_particles
                speed = 1.2 if i % 5 == 0 else 0.6
            elif pattern == "double":
                angle = (2 * pi * i) / num_particles
                speed = random.choice([0.6, 1.3])
            else:  # spiral
                angle = (4 * pi * i) / num_particles
                speed = 0.3 + (i / num_particles) * 1.2

            vx = cos(angle) * speed * random.uniform(0.8, 1.2)
            vy = sin(angle) * speed * random.uniform(0.8, 1.2) * 0.6

            particle = Particle(
                x=x,
                y=y,
                vx=vx,
                vy=vy,
                color=explosion_color if random.random() > 0.2 else random.choice(COLORS),
                char=random.choice(SPARKLE_CHARS),
                life=random.uniform(20, 40),
                max_life=40,
                trail=[(x, y)] * 3,
            )
            self.particles.append(particle)

    def update(self):
        """Update all particles and rockets."""
        # Update rockets
        for rocket in self.rockets[:]:
            rocket.y += rocket.vy
            rocket.x += rocket.vx
            rocket.vy += self.gravity * 0.5
            rocket.life -= 1

            if rocket.life <= 0 or rocket.vy >= 0:
                self.explode(rocket.x, rocket.y, rocket.color)
                self.rockets.remove(rocket)

        # Update explosion particles
        for p in self.particles[:]:
            # Store trail
            p.trail.append((p.x, p.y))
            if len(p.trail) > 4:
                p.trail.pop(0)

            p.x += p.vx
            p.y += p.vy
            p.vy += self.gravity
            p.vx *= 0.98  # Air resistance
            p.life -= 1

            if p.life <= 0 or p.y >= self.height or p.x < 0 or p.x >= self.width:
                self.particles.remove(p)

        # Random chance to spawn new rocket
        if random.random() < 0.08:
            self.spawn_rocket()

    def render(self) -> str:
        """Render the current frame to a string."""
        # Create empty buffer
        buffer = [[" " for _ in range(self.width)] for _ in range(self.height)]
        color_buffer = [["" for _ in range(self.width)] for _ in range(self.height)]

        # Draw particle trails (faded)
        for p in self.particles:
            for i, (tx, ty) in enumerate(p.trail[:-1]):
                ix, iy = int(tx), int(ty)
                if 0 <= ix < self.width and 0 <= iy < self.height:
                    fade_char = "·" if i < len(p.trail) // 2 else "."
                    if buffer[iy][ix] == " ":
                        buffer[iy][ix] = fade_char
                        color_buffer[iy][ix] = f"\033[2m{p.color}"  # Dim

        # Draw particles
        for p in self.particles:
            ix, iy = int(p.x), int(p.y)
            if 0 <= ix < self.width and 0 <= iy < self.height:
                brightness = p.life / p.max_life
                if brightness > 0.6:
                    char = p.char
                elif brightness > 0.3:
                    char = random.choice(["·", ".", "*"])
                else:
                    char = "."
                buffer[iy][ix] = char
                color_buffer[iy][ix] = p.color

        # Draw rockets
        for rocket in self.rockets:
            ix, iy = int(rocket.x), int(rocket.y)
            if 0 <= ix < self.width and 0 <= iy < self.height:
                buffer[iy][ix] = rocket.char
                color_buffer[iy][ix] = rocket.color
            # Rocket trail
            for i in range(1, 4):
                ty = int(rocket.y) + i
                if 0 <= ty < self.height and 0 <= ix < self.width:
                    buffer[ty][ix] = ":" if i == 1 else "."
                    color_buffer[ty][ix] = "\033[93m"  # Yellow trail

        # Build output string
        lines = []
        for y in range(self.height):
            line = ""
            for x in range(self.width):
                if color_buffer[y][x]:
                    line += f"{color_buffer[y][x]}{buffer[y][x]}{RESET}"
                else:
                    line += buffer[y][x]
            lines.append(line)

        return "\n".join(lines)


def main():
    """Run the fireworks show."""
    # Get terminal size
    size = shutil.get_terminal_size()
    width = size.columns
    height = size.lines - 2  # Leave room for message

    # Hide cursor and clear screen
    print("\033[?25l", end="")  # Hide cursor
    print("\033[2J", end="")    # Clear screen

    firework = Firework(width, height)

    # Title
    title = "✨ FIREWORKS SHOW ✨ - Press Ctrl+C to exit"

    try:
        frame = 0
        while True:
            # Move cursor to top
            print("\033[H", end="")

            # Render and display
            output = firework.render()
            print(output)

            # Center the title
            padding = (width - len(title)) // 2
            print(f"\033[97m{' ' * padding}{title}{RESET}", end="", flush=True)

            # Update physics
            firework.update()

            # Frame timing (~30 FPS)
            time.sleep(0.033)
            frame += 1

    except KeyboardInterrupt:
        pass
    finally:
        # Show cursor and reset
        print("\033[?25h", end="")  # Show cursor
        print("\033[0m", end="")    # Reset colors
        print("\n\n🎆 Thanks for watching! 🎆\n")


if __name__ == "__main__":
    main()
