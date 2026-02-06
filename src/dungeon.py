#!/usr/bin/env python3
"""
DEPTHS OF SHADOW - A Mini Roguelike
Navigate procedurally generated dungeons, fight monsters, find treasure.
"""

import random
import sys
import tty
import termios
import shutil
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# === COLORS ===
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    BLACK = "\033[30m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    ORANGE = "\033[38;5;208m"
    PINK = "\033[38;5;213m"
    GRAY = "\033[90m"

    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


# === DATA CLASSES ===
class TileType(Enum):
    WALL = "#"
    FLOOR = "."
    DOOR = "+"
    STAIRS = ">"
    WATER = "~"


@dataclass
class Entity:
    x: int
    y: int
    char: str
    color: str
    name: str
    hp: int
    max_hp: int
    attack: int
    defense: int
    xp_value: int = 0


@dataclass
class Item:
    x: int
    y: int
    char: str
    color: str
    name: str
    item_type: str  # "heal", "weapon", "armor", "gold"
    value: int


@dataclass
class Room:
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    def intersects(self, other: "Room") -> bool:
        return (
            self.x <= other.x + other.width + 1
            and self.x + self.width + 1 >= other.x
            and self.y <= other.y + other.height + 1
            and self.y + self.height + 1 >= other.y
        )


@dataclass
class Player:
    x: int
    y: int
    hp: int = 30
    max_hp: int = 30
    attack: int = 5
    defense: int = 2
    level: int = 1
    xp: int = 0
    xp_to_level: int = 20
    gold: int = 0
    potions: int = 2
    weapon: str = "Fists"
    armor: str = "Clothes"

    def xp_needed(self) -> int:
        return self.xp_to_level - self.xp


# === MONSTER TEMPLATES ===
MONSTERS = {
    1: [
        ("r", C.GRAY, "Rat", 6, 2, 0, 5),
        ("g", C.GREEN, "Goblin", 10, 3, 1, 10),
        ("b", C.YELLOW, "Bat", 5, 2, 0, 5),
    ],
    2: [
        ("g", C.GREEN, "Goblin", 12, 4, 1, 12),
        ("o", C.ORANGE, "Orc", 18, 5, 2, 20),
        ("s", C.GRAY, "Skeleton", 14, 4, 1, 15),
    ],
    3: [
        ("o", C.ORANGE, "Orc Warrior", 22, 6, 3, 25),
        ("T", C.RED, "Troll", 30, 7, 3, 35),
        ("w", C.CYAN, "Wraith", 16, 8, 1, 30),
    ],
    4: [
        ("T", C.RED, "Troll Chief", 40, 9, 4, 50),
        ("D", C.MAGENTA, "Demon", 35, 10, 3, 60),
        ("V", C.RED, "Vampire", 28, 11, 2, 55),
    ],
    5: [
        ("D", C.MAGENTA, "Arch Demon", 50, 12, 5, 80),
        ("L", C.WHITE, "Lich", 40, 14, 3, 90),
        ("W", C.RED, "Dragon", 70, 15, 6, 150),
    ],
}


# === DUNGEON GENERATOR ===
class Dungeon:
    def __init__(self, width: int, height: int, floor: int):
        self.width = width
        self.height = height
        self.floor = floor
        self.tiles: list[list[TileType]] = []
        self.rooms: list[Room] = []
        self.entities: list[Entity] = []
        self.items: list[Item] = []
        self.stairs_pos: tuple[int, int] = (0, 0)
        self.generate()

    def generate(self):
        # Fill with walls
        self.tiles = [[TileType.WALL for _ in range(self.width)] for _ in range(self.height)]

        # Generate rooms
        max_rooms = 8 + self.floor
        for _ in range(50):
            if len(self.rooms) >= max_rooms:
                break

            w = random.randint(5, 10)
            h = random.randint(4, 8)
            x = random.randint(1, self.width - w - 1)
            y = random.randint(1, self.height - h - 1)

            new_room = Room(x, y, w, h)

            if not any(new_room.intersects(r) for r in self.rooms):
                self.carve_room(new_room)

                if self.rooms:
                    # Connect to previous room
                    prev_center = self.rooms[-1].center
                    new_center = new_room.center

                    if random.random() < 0.5:
                        self.carve_h_tunnel(prev_center[0], new_center[0], prev_center[1])
                        self.carve_v_tunnel(prev_center[1], new_center[1], new_center[0])
                    else:
                        self.carve_v_tunnel(prev_center[1], new_center[1], prev_center[0])
                        self.carve_h_tunnel(prev_center[0], new_center[0], new_center[1])

                self.rooms.append(new_room)

        # Place stairs in last room
        last_room = self.rooms[-1]
        self.stairs_pos = last_room.center
        self.tiles[self.stairs_pos[1]][self.stairs_pos[0]] = TileType.STAIRS

        # Add some water pools
        for _ in range(random.randint(0, 2)):
            room = random.choice(self.rooms[1:-1]) if len(self.rooms) > 2 else None
            if room:
                wx = random.randint(room.x + 1, room.x + room.width - 2)
                wy = random.randint(room.y + 1, room.y + room.height - 2)
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        if random.random() < 0.6:
                            nx, ny = wx + dx, wy + dy
                            if self.tiles[ny][nx] == TileType.FLOOR:
                                self.tiles[ny][nx] = TileType.WATER

        # Spawn monsters
        self.spawn_monsters()

        # Spawn items
        self.spawn_items()

    def carve_room(self, room: Room):
        for y in range(room.y, room.y + room.height):
            for x in range(room.x, room.x + room.width):
                self.tiles[y][x] = TileType.FLOOR

    def carve_h_tunnel(self, x1: int, x2: int, y: int):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            if 0 < y < self.height - 1 and 0 < x < self.width - 1:
                self.tiles[y][x] = TileType.FLOOR

    def carve_v_tunnel(self, y1: int, y2: int, x: int):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            if 0 < y < self.height - 1 and 0 < x < self.width - 1:
                self.tiles[y][x] = TileType.FLOOR

    def spawn_monsters(self):
        monster_level = min(self.floor, 5)
        templates = MONSTERS.get(monster_level, MONSTERS[1])

        num_monsters = 3 + self.floor * 2

        for room in self.rooms[1:]:  # Skip first room (player spawn)
            if random.random() < 0.7:
                for _ in range(random.randint(1, 2)):
                    if len(self.entities) >= num_monsters:
                        break

                    char, color, name, hp, atk, defense, xp = random.choice(templates)

                    # Random position in room
                    x = random.randint(room.x + 1, room.x + room.width - 2)
                    y = random.randint(room.y + 1, room.y + room.height - 2)

                    if not self.get_entity_at(x, y):
                        # Scale stats with floor
                        hp_bonus = (self.floor - 1) * 3
                        atk_bonus = (self.floor - 1)

                        self.entities.append(Entity(
                            x=x, y=y, char=char, color=color, name=name,
                            hp=hp + hp_bonus, max_hp=hp + hp_bonus,
                            attack=atk + atk_bonus, defense=defense,
                            xp_value=xp + self.floor * 5
                        ))

    def spawn_items(self):
        # Health potions
        for room in random.sample(self.rooms[1:], min(2, len(self.rooms) - 1)):
            if random.random() < 0.5:
                x = random.randint(room.x + 1, room.x + room.width - 2)
                y = random.randint(room.y + 1, room.y + room.height - 2)
                self.items.append(Item(x, y, "!", C.RED, "Health Potion", "heal", 15))

        # Gold
        for room in self.rooms[1:]:
            if random.random() < 0.4:
                x = random.randint(room.x + 1, room.x + room.width - 2)
                y = random.randint(room.y + 1, room.y + room.height - 2)
                gold_amount = random.randint(5, 15) * self.floor
                self.items.append(Item(x, y, "$", C.YELLOW, f"{gold_amount} Gold", "gold", gold_amount))

        # Weapons (rare)
        if random.random() < 0.3:
            room = random.choice(self.rooms[1:])
            x = random.randint(room.x + 1, room.x + room.width - 2)
            y = random.randint(room.y + 1, room.y + room.height - 2)
            weapons = [
                ("Dagger", 2), ("Sword", 4), ("Axe", 6), ("Magic Blade", 8)
            ]
            weapon = weapons[min(self.floor - 1, len(weapons) - 1)]
            self.items.append(Item(x, y, "/", C.CYAN, weapon[0], "weapon", weapon[1]))

        # Armor (rare)
        if random.random() < 0.25:
            room = random.choice(self.rooms[1:])
            x = random.randint(room.x + 1, room.x + room.width - 2)
            y = random.randint(room.y + 1, room.y + room.height - 2)
            armors = [
                ("Leather", 1), ("Chain Mail", 2), ("Plate Armor", 4), ("Dragon Scale", 6)
            ]
            armor = armors[min(self.floor - 1, len(armors) - 1)]
            self.items.append(Item(x, y, "[", C.BLUE, armor[0], "armor", armor[1]))

    def get_entity_at(self, x: int, y: int) -> Optional[Entity]:
        for e in self.entities:
            if e.x == x and e.y == y:
                return e
        return None

    def get_item_at(self, x: int, y: int) -> Optional[Item]:
        for i in self.items:
            if i.x == x and i.y == y:
                return i
        return None

    def is_walkable(self, x: int, y: int) -> bool:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return False
        return self.tiles[y][x] != TileType.WALL

    def remove_entity(self, entity: Entity):
        if entity in self.entities:
            self.entities.remove(entity)

    def remove_item(self, item: Item):
        if item in self.items:
            self.items.remove(item)


# === GAME ===
class Game:
    def __init__(self):
        self.term_width, self.term_height = shutil.get_terminal_size()
        self.map_width = min(60, self.term_width - 25)
        self.map_height = min(22, self.term_height - 8)

        self.player = Player(x=0, y=0)
        self.dungeon: Dungeon = None
        self.floor = 1
        self.messages: list[str] = []
        self.game_over = False
        self.victory = False

        self.new_floor()

    def new_floor(self):
        self.dungeon = Dungeon(self.map_width, self.map_height, self.floor)
        # Place player in first room
        start_room = self.dungeon.rooms[0]
        self.player.x, self.player.y = start_room.center
        self.add_message(f"{C.CYAN}You descend to floor {self.floor}...{C.RESET}")

    def add_message(self, msg: str):
        self.messages.append(msg)
        if len(self.messages) > 5:
            self.messages.pop(0)

    def move_player(self, dx: int, dy: int):
        new_x = self.player.x + dx
        new_y = self.player.y + dy

        # Check for monster
        entity = self.dungeon.get_entity_at(new_x, new_y)
        if entity:
            self.combat(entity)
            return

        # Check walkable
        if self.dungeon.is_walkable(new_x, new_y):
            self.player.x = new_x
            self.player.y = new_y

            # Check for items
            item = self.dungeon.get_item_at(new_x, new_y)
            if item:
                self.pickup_item(item)

            # Check for stairs
            if self.dungeon.tiles[new_y][new_x] == TileType.STAIRS:
                self.add_message(f"{C.YELLOW}Press > to descend the stairs{C.RESET}")

            # Water slows you down (flavor only)
            if self.dungeon.tiles[new_y][new_x] == TileType.WATER:
                if random.random() < 0.3:
                    self.add_message(f"{C.BLUE}You wade through the water...{C.RESET}")

            # Monsters move after player
            self.move_monsters()

    def combat(self, enemy: Entity):
        # Player attacks
        damage = max(1, self.player.attack + random.randint(-2, 2) - enemy.defense)
        enemy.hp -= damage
        self.add_message(f"{C.WHITE}You hit {enemy.name} for {C.YELLOW}{damage}{C.WHITE} damage!{C.RESET}")

        if enemy.hp <= 0:
            self.add_message(f"{C.GREEN}{enemy.name} is defeated! (+{enemy.xp_value} XP){C.RESET}")
            self.dungeon.remove_entity(enemy)
            self.gain_xp(enemy.xp_value)
        else:
            # Enemy counter-attacks
            enemy_damage = max(1, enemy.attack + random.randint(-1, 1) - self.player.defense)
            self.player.hp -= enemy_damage
            self.add_message(f"{C.RED}{enemy.name} hits you for {enemy_damage} damage!{C.RESET}")

            if self.player.hp <= 0:
                self.player.hp = 0
                self.game_over = True
                self.add_message(f"{C.RED}{C.BOLD}You have been slain!{C.RESET}")

    def move_monsters(self):
        for entity in self.dungeon.entities:
            # Simple AI: move toward player if close
            dx = self.player.x - entity.x
            dy = self.player.y - entity.y
            dist = abs(dx) + abs(dy)

            if dist <= 6:  # Detection range
                move_x, move_y = 0, 0

                if abs(dx) > abs(dy):
                    move_x = 1 if dx > 0 else -1
                elif dy != 0:
                    move_y = 1 if dy > 0 else -1

                new_x = entity.x + move_x
                new_y = entity.y + move_y

                # Attack player if adjacent
                if new_x == self.player.x and new_y == self.player.y:
                    damage = max(1, entity.attack + random.randint(-1, 1) - self.player.defense)
                    self.player.hp -= damage
                    self.add_message(f"{C.RED}{entity.name} hits you for {damage} damage!{C.RESET}")

                    if self.player.hp <= 0:
                        self.player.hp = 0
                        self.game_over = True
                        self.add_message(f"{C.RED}{C.BOLD}You have been slain!{C.RESET}")

                elif self.dungeon.is_walkable(new_x, new_y) and not self.dungeon.get_entity_at(new_x, new_y):
                    entity.x = new_x
                    entity.y = new_y

    def pickup_item(self, item: Item):
        if item.item_type == "heal":
            self.player.potions += 1
            self.add_message(f"{C.GREEN}Picked up {item.name}!{C.RESET}")
        elif item.item_type == "gold":
            self.player.gold += item.value
            self.add_message(f"{C.YELLOW}Picked up {item.value} gold!{C.RESET}")
        elif item.item_type == "weapon":
            self.player.weapon = item.name
            self.player.attack = 5 + item.value
            self.add_message(f"{C.CYAN}Equipped {item.name}! (ATK +{item.value}){C.RESET}")
        elif item.item_type == "armor":
            self.player.armor = item.name
            self.player.defense = 2 + item.value
            self.add_message(f"{C.BLUE}Equipped {item.name}! (DEF +{item.value}){C.RESET}")

        self.dungeon.remove_item(item)

    def use_potion(self):
        if self.player.potions > 0 and self.player.hp < self.player.max_hp:
            heal = min(15, self.player.max_hp - self.player.hp)
            self.player.hp += heal
            self.player.potions -= 1
            self.add_message(f"{C.GREEN}You drink a potion and heal {heal} HP!{C.RESET}")
        elif self.player.potions == 0:
            self.add_message(f"{C.GRAY}You have no potions!{C.RESET}")
        else:
            self.add_message(f"{C.GRAY}You're already at full health!{C.RESET}")

    def gain_xp(self, amount: int):
        self.player.xp += amount
        while self.player.xp >= self.player.xp_to_level:
            self.player.xp -= self.player.xp_to_level
            self.player.level += 1
            self.player.xp_to_level = int(self.player.xp_to_level * 1.5)
            self.player.max_hp += 5
            self.player.hp = self.player.max_hp
            self.player.attack += 1
            self.add_message(f"{C.MAGENTA}{C.BOLD}LEVEL UP! You are now level {self.player.level}!{C.RESET}")

    def descend(self):
        if self.dungeon.tiles[self.player.y][self.player.x] == TileType.STAIRS:
            self.floor += 1
            if self.floor > 5:
                self.victory = True
                self.game_over = True
                self.add_message(f"{C.YELLOW}{C.BOLD}You escaped the dungeon! VICTORY!{C.RESET}")
            else:
                self.new_floor()

    def render(self) -> str:
        lines = []

        # Title bar
        title = f" DEPTHS OF SHADOW - Floor {self.floor} "
        lines.append(f"{C.BOLD}{C.WHITE}{'═' * 3}{title}{'═' * (self.map_width + 20 - len(title) - 3)}{C.RESET}")

        # Map + Stats side by side
        for y in range(self.map_height):
            # Map line
            map_line = ""
            for x in range(self.map_width):
                # Player
                if x == self.player.x and y == self.player.y:
                    map_line += f"{C.BOLD}{C.YELLOW}@{C.RESET}"
                    continue

                # Entity
                entity = self.dungeon.get_entity_at(x, y)
                if entity:
                    map_line += f"{entity.color}{entity.char}{C.RESET}"
                    continue

                # Item
                item = self.dungeon.get_item_at(x, y)
                if item:
                    map_line += f"{item.color}{item.char}{C.RESET}"
                    continue

                # Tile
                tile = self.dungeon.tiles[y][x]
                if tile == TileType.WALL:
                    map_line += f"{C.GRAY}#{C.RESET}"
                elif tile == TileType.FLOOR:
                    map_line += f"{C.DIM}.{C.RESET}"
                elif tile == TileType.STAIRS:
                    map_line += f"{C.WHITE}>{C.RESET}"
                elif tile == TileType.WATER:
                    map_line += f"{C.BLUE}~{C.RESET}"
                else:
                    map_line += " "

            # Stats panel (right side)
            stat_line = ""
            if y == 0:
                stat_line = f"  {C.BOLD}{C.WHITE}[ HERO ]{C.RESET}"
            elif y == 1:
                hp_bar = self.make_bar(self.player.hp, self.player.max_hp, 10, C.RED)
                stat_line = f"  HP: {hp_bar} {self.player.hp}/{self.player.max_hp}"
            elif y == 2:
                xp_bar = self.make_bar(self.player.xp, self.player.xp_to_level, 10, C.MAGENTA)
                stat_line = f"  XP: {xp_bar} Lv.{self.player.level}"
            elif y == 3:
                stat_line = f"  {C.CYAN}ATK:{C.WHITE} {self.player.attack}  {C.BLUE}DEF:{C.WHITE} {self.player.defense}"
            elif y == 4:
                stat_line = f"  {C.YELLOW}Gold:{C.WHITE} {self.player.gold}"
            elif y == 5:
                stat_line = f"  {C.RED}Potions:{C.WHITE} {self.player.potions}"
            elif y == 7:
                stat_line = f"  {C.BOLD}{C.WHITE}[ GEAR ]{C.RESET}"
            elif y == 8:
                stat_line = f"  {C.CYAN}/{C.WHITE} {self.player.weapon}"
            elif y == 9:
                stat_line = f"  {C.BLUE}[{C.WHITE} {self.player.armor}"
            elif y == 11:
                stat_line = f"  {C.BOLD}{C.WHITE}[ CONTROLS ]{C.RESET}"
            elif y == 12:
                stat_line = f"  {C.GRAY}WASD/Arrows: Move"
            elif y == 13:
                stat_line = f"  {C.GRAY}P: Use Potion"
            elif y == 14:
                stat_line = f"  {C.GRAY}>: Descend Stairs"
            elif y == 15:
                stat_line = f"  {C.GRAY}Q: Quit"

            lines.append(f"{map_line}{stat_line}")

        # Bottom bar
        lines.append(f"{C.BOLD}{'═' * (self.map_width + 22)}{C.RESET}")

        # Messages
        for msg in self.messages[-4:]:
            lines.append(f" {msg}")

        # Pad messages area
        while len(lines) < self.map_height + 6:
            lines.append("")

        return "\n".join(lines)

    def make_bar(self, current: int, maximum: int, width: int, color: str) -> str:
        filled = int((current / maximum) * width) if maximum > 0 else 0
        empty = width - filled
        return f"{color}{'█' * filled}{C.GRAY}{'░' * empty}{C.RESET}"

    def render_game_over(self) -> str:
        lines = []
        lines.append("")
        lines.append("")
        if self.victory:
            lines.append(f"    {C.YELLOW}{C.BOLD}╔══════════════════════════════════╗{C.RESET}")
            lines.append(f"    {C.YELLOW}{C.BOLD}║        ★ VICTORY! ★              ║{C.RESET}")
            lines.append(f"    {C.YELLOW}{C.BOLD}║   You escaped the dungeon!       ║{C.RESET}")
            lines.append(f"    {C.YELLOW}{C.BOLD}╚══════════════════════════════════╝{C.RESET}")
        else:
            lines.append(f"    {C.RED}{C.BOLD}╔══════════════════════════════════╗{C.RESET}")
            lines.append(f"    {C.RED}{C.BOLD}║          GAME OVER                ║{C.RESET}")
            lines.append(f"    {C.RED}{C.BOLD}║      You have been slain...       ║{C.RESET}")
            lines.append(f"    {C.RED}{C.BOLD}╚══════════════════════════════════╝{C.RESET}")

        lines.append("")
        lines.append(f"    {C.WHITE}Final Stats:{C.RESET}")
        lines.append(f"    {C.CYAN}Level: {self.player.level}")
        lines.append(f"    {C.YELLOW}Gold: {self.player.gold}")
        lines.append(f"    {C.MAGENTA}Floor Reached: {self.floor}")
        lines.append("")
        lines.append(f"    {C.GRAY}Press R to restart, Q to quit{C.RESET}")
        lines.append("")

        return "\n".join(lines)


# === INPUT HANDLING ===
def get_key():
    """Get a single keypress."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        # Handle arrow keys (escape sequences)
        if ch == '\x1b':
            ch2 = sys.stdin.read(2)
            if ch2 == '[A':
                return 'UP'
            elif ch2 == '[B':
                return 'DOWN'
            elif ch2 == '[C':
                return 'RIGHT'
            elif ch2 == '[D':
                return 'LEFT'
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def main():
    """Main game loop."""
    game = Game()

    # Hide cursor and clear
    print("\033[?25l", end="")
    print("\033[2J", end="")

    try:
        while True:
            # Render
            print("\033[H", end="")

            if game.game_over:
                print(game.render_game_over())
            else:
                print(game.render())

            # Input
            key = get_key()

            if game.game_over:
                if key.lower() == 'r':
                    game = Game()
                elif key.lower() == 'q':
                    break
            else:
                if key.lower() == 'w' or key == 'UP':
                    game.move_player(0, -1)
                elif key.lower() == 's' or key == 'DOWN':
                    game.move_player(0, 1)
                elif key.lower() == 'a' or key == 'LEFT':
                    game.move_player(-1, 0)
                elif key.lower() == 'd' or key == 'RIGHT':
                    game.move_player(1, 0)
                elif key.lower() == 'p':
                    game.use_potion()
                elif key == '>':
                    game.descend()
                elif key.lower() == 'q':
                    break

    except KeyboardInterrupt:
        pass
    finally:
        # Show cursor and reset
        print("\033[?25h", end="")
        print("\033[0m", end="")
        print("\033[2J\033[H", end="")
        print("Thanks for playing Depths of Shadow!")


if __name__ == "__main__":
    main()
