import math
import os
import random
import sys

import pygame as pg


WIDTH = 405
HEIGHT = 720
FPS = 60

TITLE = "Blade Spin"
BG_TOP = (24, 31, 45)
BG_BOTTOM = (55, 72, 91)
WHITE = (244, 247, 251)
MUTED = (166, 181, 198)
RED = (238, 75, 86)
GOLD = (255, 199, 56)
WOOD_DARK = (103, 61, 36)
WOOD_MID = (143, 89, 49)
WOOD_LIGHT = (190, 124, 65)

TARGET_CENTER = (WIDTH // 2, 215)
TARGET_RADIUS = 86
IMPACT_WORLD_ANGLE = 90
KNIFE_TIP_RADIUS = TARGET_RADIUS - 8
KNIFE_START_Y = HEIGHT - 82
KNIFE_HIT_Y = TARGET_CENTER[1] + KNIFE_TIP_RADIUS
KNIFE_SPEED = 80
COLLISION_ANGLE = 9
APPLE_HIT_ANGLE = 13


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def angle_diff(a, b):
    return abs((a - b + 180) % 360 - 180)


class Game:
    def __init__(self):
        pg.init()
        try:
            self.screen = pg.display.set_mode((WIDTH, HEIGHT), pg.DOUBLEBUF, vsync=1)
        except Exception:
            self.screen = pg.display.set_mode((WIDTH, HEIGHT))
        pg.display.set_caption(TITLE)
        self.clock = pg.time.Clock()
        self.font_name = pg.font.match_font("Segoe UI", "arial")
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.highscore = self.load_highscore()
        self.background = self.make_background()
        self.font_cache = {}
        self.running = True
        self.reset()

    def load_highscore(self):
        path = os.path.join(self.base_dir, "highscore.txt")
        try:
            with open(path, "r") as f:
                return int(f.read().strip() or 0)
        except (OSError, ValueError):
            return 0

    def save_highscore(self):
        if self.score <= self.highscore:
            return
        self.highscore = self.score
        try:
            with open(os.path.join(self.base_dir, "highscore.txt"), "w") as f:
                f.write(str(self.highscore))
        except OSError:
            pass

    def make_background(self):
        surface = pg.Surface((WIDTH, HEIGHT)).convert()
        for y in range(HEIGHT):
            t = y / HEIGHT
            color = (
                int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t),
                int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t),
                int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t),
            )
            pg.draw.line(surface, color, (0, y), (WIDTH, y))
        for y in range(80, HEIGHT, 110):
            pg.draw.line(surface, (255, 255, 255, 10), (0, y), (WIDTH, y + 45), 1)
        return surface

    def reset(self):
        self.score = 0
        self.stage = 1
        self.state = "playing"
        self.gameover_reason = ""
        self.flash = 0
        self.shake = 0
        self.apple_pop_timer = 0
        self.apple_pop_pos = None
        self.message_timer = 0
        self.start_stage()

    def start_stage(self):
        self.target_angle = random.randint(0, 359)
        self.spin_speed = random.choice([-1, 1]) * (1.25 + self.stage * 0.18)
        self.spin_timer = random.randint(70, 130)
        self.spin_mode = 1
        self.stuck_blades = []
        self.apples = []
        self.knives_left = clamp(5 + self.stage, 6, 12)
        self.throwing = False
        self.knife_y = KNIFE_START_Y
        self.state = "playing"
        self.message_timer = 55

        starter_count = clamp((self.stage + 1) // 2, 1, 6)
        for i in range(starter_count):
            self.stuck_blades.append((i * (360 / starter_count) + random.randint(-9, 9)) % 360)
        self.place_apples()

    def place_apples(self):
        apple_count = clamp(1 + self.stage // 3, 1, 4)
        attempts = 0
        while len(self.apples) < apple_count and attempts < 120:
            attempts += 1
            angle = random.randint(0, 359)
            if any(angle_diff(angle, blade) < COLLISION_ANGLE + APPLE_HIT_ANGLE + 8 for blade in self.stuck_blades):
                continue
            if any(angle_diff(angle, apple) < APPLE_HIT_ANGLE * 2 + 8 for apple in self.apples):
                continue
            self.apples.append(angle)

    def font(self, size, bold=False):
        key = (size, bold)
        if key not in self.font_cache:
            f = pg.font.Font(self.font_name, size)
            f.set_bold(bold)
            self.font_cache[key] = f
        return self.font_cache[key]

    def text(self, label, size, color, center, bold=False):
        surface = self.font(size, bold).render(label, True, color)
        rect = surface.get_rect(center=center)
        self.screen.blit(surface, rect)

    def throw(self):
        if self.state == "ready":
            self.reset()
            return
        if self.state == "gameover":
            self.reset()
            return
        if self.state != "playing" or self.throwing or self.knives_left <= 0:
            return
        self.throwing = True
        self.knife_y = KNIFE_START_Y

    def update(self):
        if self.flash > 0:
            self.flash -= 1
        if self.shake > 0:
            self.shake -= 1
        if self.apple_pop_timer > 0:
            self.apple_pop_timer -= 1
        if self.message_timer > 0:
            self.message_timer -= 1

        if self.state != "playing":
            return

        self.spin_timer -= 1
        if self.spin_timer <= 0:
            self.spin_timer = random.randint(55, 145)
            if random.random() < 0.55:
                self.spin_mode *= -1
            speed = 1.0 + self.stage * 0.18 + random.random() * 0.65
            self.spin_speed = self.spin_mode * speed

        self.target_angle = (self.target_angle + self.spin_speed) % 360

        if self.throwing:
            self.knife_y -= KNIFE_SPEED
            if self.knife_y <= KNIFE_HIT_Y:
                self.resolve_hit()

    def resolve_hit(self):
        impact_angle = (IMPACT_WORLD_ANGLE - self.target_angle) % 360
        for blade_angle in self.stuck_blades:
            if angle_diff(impact_angle, blade_angle) < COLLISION_ANGLE:
                self.state = "gameover"
                self.gameover_reason = "BLADE CRASH"
                self.throwing = False
                self.flash = 18
                self.shake = 20
                self.save_highscore()
                return

        for apple_angle in self.apples[:]:
            if angle_diff(impact_angle, apple_angle) < APPLE_HIT_ANGLE:
                self.apples.remove(apple_angle)
                self.score += 4 + self.stage
                self.apple_pop_timer = 18
                world = (self.target_angle + apple_angle) % 360
                a = math.radians(world)
                self.apple_pop_pos = (
                    TARGET_CENTER[0] + math.cos(a) * (TARGET_RADIUS + 12),
                    TARGET_CENTER[1] + math.sin(a) * (TARGET_RADIUS + 12),
                )
                break

        self.stuck_blades.append(impact_angle)
        self.throwing = False
        self.knives_left -= 1
        self.score += 1
        self.flash = 5

        if self.knives_left == 0 and self.apples:
            self.state = "gameover"
            self.gameover_reason = "APPLE MISSED"
            self.flash = 18
            self.shake = 14
            self.save_highscore()
            return

        if self.knives_left == 0:
            self.score += self.stage * 2
            self.stage += 1
            self.save_highscore()
            self.start_stage()

    def draw_knife(self, tip, angle_deg, scale=1.0, alpha=255):
        angle = math.radians(angle_deg)
        ux = math.cos(angle)
        uy = math.sin(angle)
        px = -uy
        py = ux
        length = 96 * scale
        blade_len = 62 * scale
        handle_len = length - blade_len
        blade_width = 8 * scale
        handle_width = 6 * scale

        tx, ty = tip
        shoulder = (tx - ux * blade_len, ty - uy * blade_len)
        spine_mid = (tx - ux * blade_len * 0.42 + px * blade_width * 0.42, ty - uy * blade_len * 0.42 + py * blade_width * 0.42)
        edge_mid = (tx - ux * blade_len * 0.55 - px * blade_width * 0.85, ty - uy * blade_len * 0.55 - py * blade_width * 0.85)
        base = (tx - ux * blade_len, ty - uy * blade_len)
        handle_end = (base[0] - ux * handle_len, base[1] - uy * handle_len)
        blade = [
            (tx, ty),
            spine_mid,
            (shoulder[0] + px * blade_width * 0.62, shoulder[1] + py * blade_width * 0.62),
            (shoulder[0] - px * blade_width * 0.72, shoulder[1] - py * blade_width * 0.72),
            edge_mid,
        ]
        handle_rect = [
            (base[0] + px * handle_width, base[1] + py * handle_width),
            (handle_end[0] + px * handle_width * 1.05, handle_end[1] + py * handle_width * 1.05),
            (handle_end[0] - px * handle_width * 1.05, handle_end[1] - py * handle_width * 1.05),
            (base[0] - px * handle_width, base[1] - py * handle_width),
        ]
        guard = [
            (base[0] + px * blade_width * 1.25 + ux * 2 * scale, base[1] + py * blade_width * 1.25 + uy * 2 * scale),
            (base[0] - px * blade_width * 1.25 + ux * 2 * scale, base[1] - py * blade_width * 1.25 + uy * 2 * scale),
            (base[0] - px * blade_width * 1.25 - ux * 5 * scale, base[1] - py * blade_width * 1.25 - uy * 5 * scale),
            (base[0] + px * blade_width * 1.25 - ux * 5 * scale, base[1] + py * blade_width * 1.25 - uy * 5 * scale),
        ]

        if alpha < 255:
            blade_color = (183, 194, 203)
            shade_color = (100, 115, 128)
            shine_color = (228, 234, 239)
            handle_color = (44, 42, 40)
            guard_color = (150, 126, 82)
            pommel_color = (190, 159, 91)
        else:
            blade_color = (224, 232, 238)
            shade_color = (118, 138, 153)
            shine_color = (255, 255, 255)
            handle_color = (36, 34, 32)
            guard_color = (188, 156, 94)
            pommel_color = (231, 184, 84)

        pg.draw.polygon(self.screen, blade_color, blade)
        pg.draw.polygon(self.screen, shade_color, [blade[0], blade[3], blade[4]])
        pg.draw.line(self.screen, shine_color, (tx - ux * 9 * scale + px * 1.6 * scale, ty - uy * 9 * scale + py * 1.6 * scale), (base[0] + px * 3 * scale, base[1] + py * 3 * scale), max(1, int(2 * scale)))
        pg.draw.polygon(self.screen, guard_color, guard)
        pg.draw.polygon(self.screen, handle_color, handle_rect)
        for offset in (0.35, 0.72):
            rivet = (base[0] - ux * handle_len * offset, base[1] - uy * handle_len * offset)
            pg.draw.circle(self.screen, (202, 205, 204), (int(rivet[0]), int(rivet[1])), max(1, int(2.2 * scale)))
        pg.draw.circle(self.screen, pommel_color, (int(handle_end[0]), int(handle_end[1])), int(5 * scale))

    def draw_target(self):
        cx, cy = TARGET_CENTER
        pg.draw.circle(self.screen, (10, 14, 22), (cx, cy + 10), TARGET_RADIUS + 6)
        pg.draw.circle(self.screen, WOOD_DARK, TARGET_CENTER, TARGET_RADIUS)
        pg.draw.circle(self.screen, WOOD_MID, TARGET_CENTER, TARGET_RADIUS - 12)
        pg.draw.circle(self.screen, WOOD_LIGHT, TARGET_CENTER, TARGET_RADIUS - 35)
        pg.draw.circle(self.screen, (123, 73, 39), TARGET_CENTER, TARGET_RADIUS, 5)

        for offset in range(0, 360, 35):
            a = math.radians(self.target_angle + offset)
            inner = TARGET_RADIUS * 0.18
            outer = TARGET_RADIUS * 0.92
            start = (cx + math.cos(a) * inner, cy + math.sin(a) * inner)
            end = (cx + math.cos(a) * outer, cy + math.sin(a) * outer)
            pg.draw.line(self.screen, (119, 70, 38), start, end, 3)

        pg.draw.circle(self.screen, (91, 52, 31), TARGET_CENTER, 19)
        pg.draw.circle(self.screen, (219, 148, 80), TARGET_CENTER, 10)

    def draw_apple(self, anchor, world_angle):
        a = math.radians(world_angle)
        ux = math.cos(a)
        uy = math.sin(a)
        tx = -uy
        ty = ux

        body_radius = 14
        cx = anchor[0] + ux * (body_radius - 1)
        cy = anchor[1] + uy * (body_radius - 1)
        ix = int(cx)
        iy = int(cy)

        outline = (83, 15, 24)
        red_dark = (166, 23, 35)
        red = (226, 30, 45)
        red_light = (255, 89, 85)
        stem = (72, 45, 22)
        leaf_dark = (30, 104, 51)
        leaf_light = (83, 184, 84)

        left_lobe = (int(cx - tx * 4 - ux * 1), int(cy - ty * 4 - uy * 1))
        right_lobe = (int(cx + tx * 4 - ux * 1), int(cy + ty * 4 - uy * 1))
        bottom_lobe = (int(cx - ux * 2), int(cy - uy * 2))
        shine = (int(cx - tx * 5 + ux * 4), int(cy - ty * 5 + uy * 4))

        pg.draw.circle(self.screen, outline, left_lobe, body_radius)
        pg.draw.circle(self.screen, outline, right_lobe, body_radius)
        pg.draw.circle(self.screen, outline, bottom_lobe, body_radius - 1)
        pg.draw.circle(self.screen, red_dark, left_lobe, body_radius - 2)
        pg.draw.circle(self.screen, red, right_lobe, body_radius - 2)
        pg.draw.circle(self.screen, red, bottom_lobe, body_radius - 3)
        pg.draw.circle(self.screen, red_light, shine, 4)
        pg.draw.circle(self.screen, (255, 174, 165), (int(shine[0] + ux * 2), int(shine[1] + uy * 2)), 2)

        notch = (cx + ux * 9, cy + uy * 9)
        stem_base = (notch[0] + ux * 2, notch[1] + uy * 2)
        stem_tip = (notch[0] + ux * 13, notch[1] + uy * 13)
        pg.draw.line(self.screen, stem, stem_base, stem_tip, 4)

        leaf_root = (stem_tip[0] - ux * 2, stem_tip[1] - uy * 2)
        leaf = [
            (leaf_root[0], leaf_root[1]),
            (leaf_root[0] + tx * 11 + ux * 2, leaf_root[1] + ty * 11 + uy * 2),
            (leaf_root[0] + tx * 15 + ux * 9, leaf_root[1] + ty * 15 + uy * 9),
            (leaf_root[0] + tx * 4 + ux * 12, leaf_root[1] + ty * 4 + uy * 12),
        ]
        pg.draw.polygon(self.screen, leaf_dark, leaf)
        leaf_hi = [
            (leaf_root[0] + tx * 3 + ux * 2, leaf_root[1] + ty * 3 + uy * 2),
            (leaf_root[0] + tx * 10 + ux * 5, leaf_root[1] + ty * 10 + uy * 5),
            (leaf_root[0] + tx * 6 + ux * 8, leaf_root[1] + ty * 6 + uy * 8),
        ]
        pg.draw.polygon(self.screen, leaf_light, leaf_hi)

    def draw_apples(self):
        cx, cy = TARGET_CENTER
        for local_angle in self.apples:
            world = (self.target_angle + local_angle) % 360
            a = math.radians(world)
            anchor = (
                cx + math.cos(a) * (TARGET_RADIUS - 2),
                cy + math.sin(a) * (TARGET_RADIUS - 2),
            )
            self.draw_apple(anchor, world)

    def draw_apple_pop(self):
        if self.apple_pop_timer <= 0 or not self.apple_pop_pos:
            return
        x, y = self.apple_pop_pos
        radius = 22 - self.apple_pop_timer // 2
        for offset in range(0, 360, 60):
            a = math.radians(offset)
            end = (x + math.cos(a) * radius, y + math.sin(a) * radius)
            pg.draw.line(self.screen, (255, 92, 84), (x, y), end, 3)
        self.text("+APPLE", 15, GOLD, (int(x), int(y - 28)), True)

    def draw_stuck_blades(self):
        cx, cy = TARGET_CENTER
        for local_angle in self.stuck_blades:
            world = (self.target_angle + local_angle) % 360
            a = math.radians(world)
            tip = (
                cx + math.cos(a) * KNIFE_TIP_RADIUS,
                cy + math.sin(a) * KNIFE_TIP_RADIUS,
            )
            self.draw_knife(tip, world + 180, 0.86)

    def draw_hud(self):
        self.text(f"STAGE {self.stage}", 22, WHITE, (WIDTH // 2, 38), True)
        self.text(f"SCORE {self.score}", 17, MUTED, (WIDTH // 2, 66), True)
        self.text(f"BEST {self.highscore}", 15, MUTED, (WIDTH // 2, 90), False)

        start_x = WIDTH // 2 - (self.knives_left - 1) * 13
        for i in range(self.knives_left):
            y = HEIGHT - 38
            x = start_x + i * 26
            pg.draw.rect(self.screen, WHITE, (x - 3, y - 34, 6, 28), border_radius=3)
            pg.draw.polygon(self.screen, WHITE, [(x, y - 46), (x - 7, y - 33), (x + 7, y - 33)])
            pg.draw.circle(self.screen, GOLD, (x, y - 2), 5)

    def draw_messages(self):
        if self.state == "ready":
            self.text(TITLE.upper(), 40, WHITE, (WIDTH // 2, 390), True)
            self.text("SPACE / CLICK", 19, GOLD, (WIDTH // 2, 435), True)
        elif self.state == "gameover":
            self.text(self.gameover_reason or "GAME OVER", 34, RED, (WIDTH // 2, 390), True)
            self.text("SPACE / CLICK", 19, GOLD, (WIDTH // 2, 435), True)
        elif self.message_timer > 0:
            alpha_color = GOLD if self.message_timer > 14 else MUTED
            self.text(f"STAGE {self.stage}", 28, alpha_color, (WIDTH // 2, 405), True)

    def draw(self):
        offset = (0, 0)
        if self.shake:
            offset = (random.randint(-7, 7), random.randint(-7, 7))

        self.screen.blit(self.background, offset)
        self.draw_target()
        self.draw_apples()
        self.draw_stuck_blades()
        self.draw_apple_pop()

        if self.throwing:
            self.draw_knife((WIDTH // 2, self.knife_y), -90, 1.0)
        elif self.state == "playing":
            self.draw_knife((WIDTH // 2, KNIFE_START_Y), -90, 1.0, 210)

        self.draw_hud()
        self.draw_messages()

        if self.flash > 0:
            overlay = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
            color = (255, 255, 255, self.flash * 10) if self.state == "playing" else (238, 75, 86, self.flash * 9)
            overlay.fill(color)
            self.screen.blit(overlay, (0, 0))

        pg.display.flip()

    def events(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.running = False
            elif event.type == pg.KEYDOWN:
                if event.key in (pg.K_SPACE, pg.K_RETURN, pg.K_UP, pg.K_w):
                    self.throw()
                elif event.key == pg.K_ESCAPE:
                    self.running = False
            elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                self.throw()

    def run(self):
        while self.running:
            self.clock.tick(FPS)
            self.events()
            self.update()
            self.draw()
        self.save_highscore()


if __name__ == "__main__":
    game = Game()
    game.run()
    pg.quit()
    sys.exit()
