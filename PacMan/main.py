import math
import random
import sys
from dataclasses import dataclass
from collections import deque

import pygame


# --- Display / timing -------------------------------------------------------
TILE = 28
COLS, ROWS = 31, 23
HUD_H = 105
WIDTH, HEIGHT = COLS * TILE, ROWS * TILE + HUD_H
FPS = 60

BG = (5, 7, 19)
INK = (13, 16, 35)
WHITE = (241, 245, 255)
MUTED = (132, 148, 181)
CYAN = (55, 229, 255)
BLUE = (70, 100, 255)
YELLOW = (255, 221, 49)
PINK = (255, 81, 174)

DIRS = {(1, 0): "right", (-1, 0): "left", (0, -1): "up", (0, 1): "down"}
OPPOSITE = {(1, 0): (-1, 0), (-1, 0): (1, 0), (0, -1): (0, 1), (0, 1): (0, -1)}

# # = wall, . = pellet, o = energizer, - = empty/open floor, S = player, G = ghost
LAYOUT = [
    "###############################",
    "#o.........................o..#",
    "#.###.#####.#.#.#####.###.###.#",
    "#.....#.....#.#.....#.....#...#",
    "#.###.#.###.#####.###.#.###.#.#",
    "#.....#...#...#...#...#.....#.#",
    "#.###.###.###.#.###.###.#####.#",
    "----#.#.....#...#.....#.#------",
    "#####.#.###.#####.###.#.#####.#",
    "#.........#---G---#.........#.#",
    "#.###.###.#-#####-#.###.###.#.#",
    "#o..#.....#-#GGG#-#.....#..o#.#",
    "###.#.###.#-#####-#.###.#.###.#",
    "#.....#...#-------#...#.#.....#",
    "#.#####.#####.#####.#####.###.#",
    "#.#.........#.#.........#...#.#",
    "#.#.###.###.#.#.###.###.###.#.#",
    "#...#...#.....S.....#...#.....#",
    "###.#.#.#####.#####.#.#.#.###.#",
    "#.....#.....#.#.....#.#.....#.#",
    "#.#########.#.#.#########.###.#",
    "#o...........................o#",
    "###############################",
]


def tile_center(col, row):
    return (col * TILE + TILE // 2, HUD_H + row * TILE + TILE // 2)


def glow_circle(surface, pos, radius, color, strength=120):
    """Draw a local glow; never allocate a full-screen surface per sprite."""
    pad = 16
    diameter = (radius + pad) * 2
    layer = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    centre = (diameter // 2, diameter // 2)
    for r in range(radius + 14, radius, -3):
        alpha = int(strength * (1 - (r - radius) / 16) ** 2)
        pygame.draw.circle(layer, (*color, max(alpha, 0)), centre, r)
    surface.blit(layer, (pos[0] - centre[0], pos[1] - centre[1]))


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    color: tuple
    size: float

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 20 * dt
        self.life -= dt

    def draw(self, screen):
        if self.life > 0:
            alpha = min(255, int(self.life * 260))
            s = pygame.Surface((16, 16), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, alpha), (8, 8), max(1, int(self.size * self.life)))
            screen.blit(s, (self.x - 8, self.y - 8))


class Actor:
    def __init__(self, col, row, speed):
        self.x, self.y = tile_center(col, row)
        self.start = (col, row)
        self.direction = (0, 0)
        self.next_direction = (0, 0)
        self.speed = speed

    @property
    def tile(self):
        return (round((self.x - TILE / 2) / TILE), round((self.y - HUD_H - TILE / 2) / TILE))

    def centered(self):
        cx, cy = tile_center(*self.tile)
        # Keep this tighter than the smallest per-frame movement.  The old
        # 3px threshold snapped slow ghosts back to their starting centre on
        # every frame, which made them appear trapped and caused jitter.
        return abs(self.x - cx) < 1.5 and abs(self.y - cy) < 1.5

    def reset(self):
        self.x, self.y = tile_center(*self.start)
        self.direction = self.next_direction = (0, 0)


class Player(Actor):
    def __init__(self, col, row):
        super().__init__(col, row, 142)
        self.mouth = 0

    def update(self, game, dt):
        if self.centered():
            col, row = self.tile
            self.x, self.y = tile_center(col, row)
            if self.next_direction != (0, 0) and game.open_at(col + self.next_direction[0], row + self.next_direction[1]):
                self.direction = self.next_direction
            if self.direction != (0, 0) and not game.open_at(col + self.direction[0], row + self.direction[1]):
                self.direction = (0, 0)
        self.x += self.direction[0] * self.speed * dt
        self.y += self.direction[1] * self.speed * dt
        # tunnel
        # Wrap directly to the opposite *maze tile* centre.  Using a point
        # beyond the screen edge could leave an actor outside the grid.
        if self.x < -TILE / 2: self.x = WIDTH - TILE / 2
        if self.x > WIDTH + TILE / 2: self.x = TILE / 2
        self.mouth += dt * 12

    def draw(self, screen):
        pos = (int(self.x), int(self.y))
        glow_circle(screen, pos, 14, YELLOW, 55)
        mouth = 0.17 + 0.24 * abs(math.sin(self.mouth))
        angle = {(1, 0): 0, (-1, 0): math.pi, (0, -1): -math.pi/2, (0, 1): math.pi/2}.get(self.direction, 0)
        points = [pos]
        for i in range(25):
            a = angle + mouth + (math.tau - 2 * mouth) * i / 24
            points.append((pos[0] + math.cos(a) * 12, pos[1] + math.sin(a) * 12))
        pygame.draw.polygon(screen, YELLOW, points)
        pygame.draw.circle(screen, (255, 244, 160), (pos[0] - 3, pos[1] - 5), 3)


class Ghost(Actor):
    def __init__(self, col, row, color, personality):
        super().__init__(col, row, 112)
        self.color, self.personality = color, personality
        self.scared = 0
        self.dead = False
        self.exiting = True
        self.phase = random.random() * 2

    def reset(self):
        super().reset()
        self.scared = 0
        self.dead = False
        self.exiting = True

    def update(self, game, dt):
        self.phase += dt * 8
        # Panic ghosts keep moving decisively but are deliberately catchable.
        speed = self.speed * (0.82 if self.scared else 1) * (1.5 if self.dead else 1)
        if self.centered():
            col, row = self.tile
            self.x, self.y = tile_center(col, row)
            if self.dead:
                target = (15, 11)
            elif self.exiting:
                # Pick the nearer of the two real house exits.
                target = (11 if col < 15 else 17, 8)
            elif self.scared:
                # Run toward the safest distant route instead of wandering.
                target = game.panic_target(game.player.tile)
            else:
                px, py = game.player.tile
                # Personalities give each ghost a different chasing style.
                target = (px, py)
                if self.personality == 1: target = (px + game.player.direction[0] * 4, py + game.player.direction[1] * 4)
                if self.personality == 2: target = (29 - px, 21 - py)
                if self.personality == 3 and abs(px - col) + abs(py - row) < 7: target = (1, 21)
            # Breadth-first routing prevents greedy target chasing from
            # trapping a ghost in a dead end or beside the house entrance.
            route = game.route_direction((col, row), target, block_house=not self.exiting and not self.dead)
            if route is not None:
                self.direction = route
            if self.exiting and row <= 8:
                self.exiting = False
            if self.dead and (col, row) == (15, 11):
                self.dead = False
                self.scared = 0
                self.exiting = True
        self.x += self.direction[0] * speed * dt
        self.y += self.direction[1] * speed * dt
        if self.x < -TILE / 2: self.x = WIDTH - TILE / 2
        if self.x > WIDTH + TILE / 2: self.x = TILE / 2
        self.scared = max(0, self.scared - dt)

    def draw(self, screen):
        x, y = int(self.x), int(self.y)
        if self.dead:
            pygame.draw.circle(screen, WHITE, (x - 5, y - 1), 4)
            pygame.draw.circle(screen, WHITE, (x + 5, y - 1), 4)
            pygame.draw.circle(screen, BLUE, (x - 4 + self.direction[0] * 2, y - 1 + self.direction[1] * 2), 2)
            pygame.draw.circle(screen, BLUE, (x + 6 + self.direction[0] * 2, y - 1 + self.direction[1] * 2), 2)
            return
        color = (51, 89, 230) if self.scared else self.color
        if self.scared and self.scared < 2 and int(self.scared * 8) % 2 == 0: color = WHITE
        glow_circle(screen, (x, y), 13, color, 35)
        body = [(x - 11, y + 10), (x - 11, y - 1), (x - 8, y - 8), (x - 4, y - 11), (x + 4, y - 11), (x + 8, y - 8), (x + 11, y - 1), (x + 11, y + 10)]
        pygame.draw.polygon(screen, color, body + [(x + 7, y + 7), (x + 3, y + 11), (x, y + 7), (x - 4, y + 11), (x - 8, y + 7)])
        if self.scared:
            pygame.draw.circle(screen, WHITE, (x - 4, y - 2), 2)
            pygame.draw.circle(screen, WHITE, (x + 4, y - 2), 2)
            pygame.draw.arc(screen, WHITE, (x - 6, y, 12, 8), math.pi, math.tau, 1)
        else:
            for eye_x in (x - 5, x + 5):
                pygame.draw.circle(screen, WHITE, (eye_x, y - 2), 4)
                pygame.draw.circle(screen, (19, 36, 107), (eye_x + self.direction[0] * 2, y - 2 + self.direction[1] * 2), 2)


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("PacMan Game")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("bahnschrift", 18, bold=True)
        self.big = pygame.font.SysFont("bahnschrift", 40, bold=True)
        self.grid = [list(row) for row in LAYOUT]
        self.high_score = 0
        self.state = "title"
        self.new_game()

    def new_game(self):
        self.grid = [list(row) for row in LAYOUT]
        for r, row in enumerate(self.grid):
            for c, cell in enumerate(row):
                if cell == "S": self.player = Player(c, r); self.grid[r][c] = "-"
                if cell == "G": self.grid[r][c] = "-"
        # The three central tiles above the house are the actual exit door.
        # They must be open in the collision grid as well as visually.
        for c in (14, 15, 16):
            self.grid[10][c] = "-"
        self.ghosts = [Ghost(14, 11, (255, 79, 101), 0), Ghost(15, 11, (63, 225, 255), 1), Ghost(16, 11, (255, 176, 63), 2), Ghost(15, 10, (224, 105, 255), 3)]
        self.score, self.lives, self.level = 0, 3, 1
        self.combo, self.message, self.message_timer = 0, "READY!", 1.8
        self.particles = []
        self.fruit_timer = 13
        self.fruit = None

    def open_at(self, c, r):
        if r < 0 or r >= ROWS: return False
        if c < 0 or c >= COLS: return True
        return self.grid[r][c] != "#"

    def neighbours(self, tile, block_house=False):
        """Return valid maze links, including the two-way side tunnel."""
        col, row = tile
        for direction in DIRS:
            nc, nr = col + direction[0], row + direction[1]
            if nc < 0:
                nc = COLS - 1
            elif nc >= COLS:
                nc = 0
            if not self.open_at(nc, nr):
                continue
            # Active ghosts must not choose a route back through their house.
            if block_house and 12 <= nc <= 18 and 9 <= nr <= 13:
                continue
            yield direction, (nc, nr)

    def route_direction(self, start, target, block_house=False):
        """Find the first step of a shortest valid route with breadth-first search."""
        target = (max(0, min(COLS - 1, target[0])), max(0, min(ROWS - 1, target[1])))
        queue = deque([start])
        first_step = {start: None}
        best = start
        while queue:
            current = queue.popleft()
            if (current[0] - target[0]) ** 2 + (current[1] - target[1]) ** 2 < (best[0] - target[0]) ** 2 + (best[1] - target[1]) ** 2:
                best = current
            if current == target:
                best = current
                break
            for direction, nxt in self.neighbours(current, block_house):
                if nxt not in first_step:
                    first_step[nxt] = direction if current == start else first_step[current]
                    queue.append(nxt)
        return first_step.get(best)

    def panic_target(self, player_tile):
        """Pick a distant escape destination for the energized panic state."""
        corners = [(1, 1), (29, 1), (1, 21), (29, 21), (1, 13), (29, 13)]
        return max(corners, key=lambda p: (p[0] - player_tile[0]) ** 2 + (p[1] - player_tile[1]) ** 2)

    def add_particles(self, pos, color, count=9):
        for _ in range(count):
            a, v = random.random() * math.tau, random.uniform(20, 95)
            self.particles.append(Particle(pos[0], pos[1], math.cos(a) * v, math.sin(a) * v, random.uniform(.35, .75), color, random.uniform(2, 4)))

    def reset_positions(self):
        self.player.reset()
        for ghost in self.ghosts: ghost.reset(); ghost.dead = False; ghost.scared = 0
        self.message, self.message_timer = "READY!", 1.3

    def begin(self):
        if self.state in ("title", "gameover", "win"):
            self.new_game()
        self.state = "playing"

    def update(self, dt):
        if self.state != "playing": return
        self.message_timer = max(0, self.message_timer - dt)
        self.fruit_timer -= dt
        if self.fruit_timer <= 0 and self.fruit is None:
            self.fruit, self.fruit_timer = (15, 13), 16
        self.player.update(self, dt)
        for ghost in self.ghosts: ghost.update(self, dt)
        col, row = self.player.tile
        if 0 <= row < ROWS and 0 <= col < COLS:
            value = self.grid[row][col]
            if value in ".o":
                self.grid[row][col] = "-"
                self.score += 10 if value == "." else 50
                self.add_particles(tile_center(col, row), WHITE if value == "." else CYAN, 3 if value == "." else 18)
                if value == "o":
                    self.combo = 0
                    for ghost in self.ghosts:
                        if not ghost.dead:
                            # 6.5s was too brief; panic now lasts 11.5s.
                            ghost.scared = 11.5
                            # An immediate reverse makes the panic response
                            # clear even before the next maze junction.
                            if ghost.direction != (0, 0):
                                ghost.direction = OPPOSITE[ghost.direction]
            if self.fruit == (col, row):
                self.score += 250
                self.fruit = None
                self.add_particles(tile_center(col, row), PINK, 22)
        for ghost in self.ghosts:
            if not ghost.dead and math.hypot(self.player.x - ghost.x, self.player.y - ghost.y) < 17:
                if ghost.scared:
                    ghost.dead = True
                    self.combo += 1
                    gain = 200 * (2 ** (self.combo - 1))
                    self.score += gain
                    self.message, self.message_timer = f"+{gain}", .8
                    self.add_particles((ghost.x, ghost.y), ghost.color, 24)
                else:
                    self.lives -= 1
                    self.add_particles((self.player.x, self.player.y), YELLOW, 30)
                    if self.lives <= 0:
                        self.high_score = max(self.high_score, self.score)
                        self.state = "gameover"
                    else: self.reset_positions()
                break
        if not any(cell in ".o" for row in self.grid for cell in row):
            self.level += 1
            self.score += 1000
            self.message, self.message_timer = "MAZE CLEAR +1000", 2
            self.grid = [list(row) for row in LAYOUT]
            for r, row in enumerate(self.grid):
                for c, cell in enumerate(row):
                    if cell in "SG": self.grid[r][c] = "-"
            for c in (14, 15, 16):
                self.grid[10][c] = "-"
            self.reset_positions()
        for p in self.particles: p.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]
        self.high_score = max(self.high_score, self.score)

    def draw_maze(self):
        # Subtle background grid
        for x in range(0, WIDTH, TILE): pygame.draw.line(self.screen, (9, 13, 31), (x, HUD_H), (x, HEIGHT), 1)
        for y in range(HUD_H, HEIGHT, TILE): pygame.draw.line(self.screen, (9, 13, 31), (0, y), (WIDTH, y), 1)
        for r, row in enumerate(self.grid):
            for c, cell in enumerate(row):
                x, y = c * TILE, HUD_H + r * TILE
                if cell == "#":
                    rect = pygame.Rect(x + 3, y + 3, TILE - 6, TILE - 6)
                    pygame.draw.rect(self.screen, (17, 24, 68), rect.inflate(3, 3), border_radius=7)
                    pygame.draw.rect(self.screen, (26, 35, 89), rect, border_radius=6)
                    pygame.draw.rect(self.screen, CYAN, rect, 1, border_radius=6)
                elif cell == ".":
                    pygame.draw.circle(self.screen, (255, 226, 193), tile_center(c, r), 2)
                elif cell == "o":
                    pulse = 5 + int(math.sin(pygame.time.get_ticks() * .008) * 1.5)
                    pygame.draw.circle(self.screen, (255, 249, 213), tile_center(c, r), pulse)
        # Ghost house
        house = pygame.Rect(12 * TILE, HUD_H + 9 * TILE, 7 * TILE, 4 * TILE)
        pygame.draw.rect(self.screen, (13, 17, 43), house, border_radius=8)
        pygame.draw.rect(self.screen, (116, 74, 255), house, 2, border_radius=8)
        pygame.draw.line(self.screen, PINK, (14 * TILE, HUD_H + 10 * TILE), (17 * TILE, HUD_H + 10 * TILE), 3)

    def draw_hud(self):
        pygame.draw.rect(self.screen, (10, 14, 32), (0, 0, WIDTH, HUD_H))
        pygame.draw.line(self.screen, (44, 83, 180), (0, HUD_H - 1), (WIDTH, HUD_H - 1), 2)
        title = self.font.render("PacMan", True, CYAN)
        title2 = self.font.render("Game", True, WHITE)
        self.screen.blit(title, (24, 20)); self.screen.blit(title2, (24, 42))
        labels = [("SCORE", f"{self.score:06d}", 220), ("BEST", f"{self.high_score:06d}", 405), ("LEVEL", str(self.level), 590)]
        for label, value, x in labels:
            self.screen.blit(self.font.render(label, True, MUTED), (x, 20))
            self.screen.blit(self.big.render(value, True, WHITE), (x, 38))
        for i in range(self.lives):
            pygame.draw.circle(self.screen, YELLOW, (764 + i * 28, 64), 10)
            pygame.draw.polygon(self.screen, (10, 14, 32), [(764 + i * 28, 64), (775 + i * 28, 58), (775 + i * 28, 70)])

    def draw_fruit(self):
        if self.fruit:
            x, y = tile_center(*self.fruit)
            glow_circle(self.screen, (x, y), 8, PINK, 40)
            pygame.draw.circle(self.screen, (255, 69, 119), (x - 4, y + 2), 6)
            pygame.draw.circle(self.screen, (255, 99, 143), (x + 4, y + 2), 6)
            pygame.draw.line(self.screen, (104, 232, 100), (x, y - 3), (x + 3, y - 9), 2)

    def overlay(self, title, subtitle, action):
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA); shade.fill((2, 4, 13, 190)); self.screen.blit(shade, (0, 0))
        panel = pygame.Rect(WIDTH//2 - 250, HEIGHT//2 - 105, 500, 210)
        pygame.draw.rect(self.screen, (12, 18, 47), panel, border_radius=20)
        pygame.draw.rect(self.screen, CYAN, panel, 2, border_radius=20)
        t = self.big.render(title, True, CYAN)
        self.screen.blit(t, t.get_rect(center=(WIDTH//2, panel.y + 63)))
        s = self.font.render(subtitle, True, WHITE)
        self.screen.blit(s, s.get_rect(center=(WIDTH//2, panel.y + 108)))
        a = self.font.render(action, True, YELLOW)
        self.screen.blit(a, a.get_rect(center=(WIDTH//2, panel.y + 158)))

    def draw(self):
        self.screen.fill(BG)
        self.draw_hud(); self.draw_maze(); self.draw_fruit()
        for p in self.particles: p.draw(self.screen)
        for ghost in self.ghosts: ghost.draw(self.screen)
        self.player.draw(self.screen)
        if self.message_timer > 0 and self.state == "playing":
            text = self.font.render(self.message, True, YELLOW)
            self.screen.blit(text, text.get_rect(center=(WIDTH//2, HUD_H + 12)))
        if self.state == "title": self.overlay("PacMan Game", "A fresh arcade chase — clear every light shard.", "PRESS ENTER TO START")
        elif self.state == "paused": self.overlay("PAUSED", "Take a breath. The ghosts can wait.", "PRESS P TO CONTINUE")
        elif self.state == "gameover": self.overlay("SYSTEM OVER", f"FINAL SCORE  {self.score:06d}", "PRESS ENTER TO PLAY AGAIN")
        pygame.display.flip()

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000, .04)
            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE: pygame.quit(); sys.exit()
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE): self.begin()
                    if event.key == pygame.K_r: self.new_game(); self.state = "playing"
                    if event.key == pygame.K_p and self.state in ("playing", "paused"):
                        self.state = "paused" if self.state == "playing" else "playing"
                    moves = {pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0), pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0), pygame.K_UP: (0, -1), pygame.K_w: (0, -1), pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1)}
                    if event.key in moves: self.player.next_direction = moves[event.key]
            self.update(dt); self.draw()


if __name__ == "__main__":
    Game().run()
