import pygame as pg
import random
import math
from settings import *

vec = pg.math.Vector2


class BackgroundCloud(pg.sprite.Sprite):
    def __init__(self, game, x, y):
        super().__init__()
        self.game = game
        self.scale = random.uniform(0.6, 1.2)
        self.width = int(80 * self.scale)
        self.height = int(45 * self.scale)
        self.speed = random.uniform(0.3, 0.8)
        self.image = pg.Surface((self.width, self.height), pg.SRCALPHA)
        self.rect = self.image.get_rect()
        self.x = float(x)
        self.rect.x = int(self.x)
        self.rect.y = y
        self.draw_cloud()

    def draw_cloud(self):
        self.image.fill((0, 0, 0, 0))
        r1 = int(18 * self.scale)
        r2 = int(24 * self.scale)
        r3 = int(16 * self.scale)
        pg.draw.circle(self.image, CLOUD_COLOR, (r2, self.height - r2), r2)
        pg.draw.circle(self.image, CLOUD_COLOR, (self.width - r3, self.height - r3), r3)
        pg.draw.circle(self.image, CLOUD_COLOR, (self.width // 2, r1 + 4), r1)
        pg.draw.rect(self.image, CLOUD_COLOR, (r2, self.height - r2 * 2 + 6, self.width - r2 - r3, r2 * 2 - 6))

    def update(self):
        self.x -= self.speed
        self.rect.x = int(self.x)
        if self.rect.right < 0:
            self.kill()


class LeafParticle(pg.sprite.Sprite):
    def __init__(self, game, x, y, color):
        super().__init__()
        self.game = game
        self.size = random.randint(3, 6)
        self.color = color
        self.vx = random.uniform(-2.0, 2.0)
        self.vy = random.uniform(-3.0, 1.0)
        self.image = pg.Surface((self.size, self.size), pg.SRCALPHA)
        self.rect = self.image.get_rect()
        self.rect.center = (x, y)
        self.draw_particle()

    def draw_particle(self):
        self.image.fill((0, 0, 0, 0))
        pg.draw.rect(self.image, self.color, (0, 0, self.size, self.size), border_radius=1)

    def update(self):
        self.rect.x += self.vx
        self.rect.y += self.vy
        self.vy += 0.12
        self.size -= 0.1
        if self.size <= 0:
            self.kill()
        else:
            old_center = self.rect.center
            sz = max(1, int(self.size))
            self.image = pg.Surface((sz, sz), pg.SRCALPHA)
            pg.draw.rect(self.image, self.color, (0, 0, sz, sz), border_radius=1)
            self.rect = self.image.get_rect()
            self.rect.center = old_center


def _tile_center(gx, gy):
    px = GRID_OFFSET_X + gx * GRID_TILE_SIZE + GRID_TILE_SIZE / 2
    py = GRID_OFFSET_Y + gy * GRID_TILE_SIZE + GRID_TILE_SIZE / 2
    return (px, py)


class Snake:
    def __init__(self, game):
        self.game = game
        self.reset()

    def reset(self):
        self.body = [(7, 7), (7, 8), (7, 9)]
        self.direction = (0, -1)
        self.input_queue = []
        self.grow_segments = 0
        self.tongue_timer = 0
        self.tongue_out = False

    def handle_input(self, event):
        if event.type == pg.KEYDOWN:
            if len(self.input_queue) >= 2:
                return
            last_dir = self.input_queue[-1] if self.input_queue else self.direction
            if event.key in [pg.K_UP, pg.K_w] and last_dir != (0, 1):
                self.input_queue.append((0, -1))
            elif event.key in [pg.K_DOWN, pg.K_s] and last_dir != (0, -1):
                self.input_queue.append((0, 1))
            elif event.key in [pg.K_LEFT, pg.K_a] and last_dir != (1, 0):
                self.input_queue.append((-1, 0))
            elif event.key in [pg.K_RIGHT, pg.K_d] and last_dir != (-1, 0):
                self.input_queue.append((1, 0))

    def next_direction(self):
        return self.input_queue[0] if self.input_queue else self.direction

    def move(self):
        if self.input_queue:
            self.direction = self.input_queue.pop(0)
        head_x, head_y = self.body[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)
        self.body.insert(0, new_head)
        if self.grow_segments > 0:
            self.grow_segments -= 1
        else:
            self.body.pop()
        self.tongue_timer += 1
        if self.tongue_timer > 8:
            self.tongue_timer = 0
            self.tongue_out = not self.tongue_out

    def grow(self):
        self.grow_segments += 1

    def check_collision(self):
        head = self.body[0]
        if head[0] < 0 or head[0] >= GRID_SIZE or head[1] < 0 or head[1] >= GRID_SIZE:
            return True
        if head in self.body[1:]:
            return True
        return False

    def _spine_points(self, progress):
        pts = []
        n = len(self.body)
        visual_direction = self.next_direction()
        for i, (gx, gy) in enumerate(self.body):
            if i == 0:
                tx = gx + visual_direction[0]
                ty = gy + visual_direction[1]
            else:
                tx, ty = self.body[i - 1]
            ix = gx + (tx - gx) * progress
            iy = gy + (ty - gy) * progress
            px = GRID_OFFSET_X + ix * GRID_TILE_SIZE + GRID_TILE_SIZE / 2
            py = GRID_OFFSET_Y + iy * GRID_TILE_SIZE + GRID_TILE_SIZE / 2
            pts.append((px, py))
        return pts

    def draw(self, surface, progress=0.0):
        pts = self._spine_points(progress)
        n = len(pts)
        if n < 2:
            return

        body_r = GRID_TILE_SIZE // 2 - 2
        head_r = body_r + 4

        body_color = (64, 122, 226)
        body_edge = (46, 94, 188)
        head_color = (72, 135, 238)
        head_edge = (42, 86, 178)
        eye_white = (252, 254, 255)
        eye_dark = (43, 59, 105)
        mouth_dark = (34, 46, 84)
        mouth_red = (224, 63, 92)
        shine_color = (120, 172, 255)
        shadow_color = (112, 154, 58)
        tongue_color = (235, 55, 96)

        def point(value):
            return (int(value[0]), int(value[1]))

        def smooth_path(points):
            if len(points) < 3:
                return list(reversed(points))

            path = list(reversed(points))
            smoothed = [path[0]]
            corner = GRID_TILE_SIZE * 0.42

            for i in range(1, len(path) - 1):
                prev_x, prev_y = path[i - 1]
                cur_x, cur_y = path[i]
                next_x, next_y = path[i + 1]

                in_dx = prev_x - cur_x
                in_dy = prev_y - cur_y
                out_dx = next_x - cur_x
                out_dy = next_y - cur_y
                in_len = math.hypot(in_dx, in_dy)
                out_len = math.hypot(out_dx, out_dy)

                if in_len == 0 or out_len == 0:
                    smoothed.append(path[i])
                    continue

                if abs(in_dx * out_dy - in_dy * out_dx) < 0.01:
                    smoothed.append(path[i])
                    continue

                cut = min(corner, in_len * 0.45, out_len * 0.45)
                before = (cur_x + in_dx / in_len * cut, cur_y + in_dy / in_len * cut)
                after = (cur_x + out_dx / out_len * cut, cur_y + out_dy / out_len * cut)

                smoothed.append(before)
                for step in range(1, 6):
                    t = step / 6
                    qx = (1 - t) * (1 - t) * before[0] + 2 * (1 - t) * t * cur_x + t * t * after[0]
                    qy = (1 - t) * (1 - t) * before[1] + 2 * (1 - t) * t * cur_y + t * t * after[1]
                    smoothed.append((qx, qy))

            smoothed.append(path[-1])
            return smoothed

        def apple_is_close():
            apple = getattr(self.game, "apple", None)
            apple_pos = getattr(apple, "pos", None)
            if apple_pos is None:
                return False

            ax, ay = _tile_center(*apple_pos)
            ahead = (ax - pts[0][0]) * dx + (ay - pts[0][1]) * dy
            sideways = abs((ax - pts[0][0]) * perp_x + (ay - pts[0][1]) * perp_y)
            return 0 < ahead <= GRID_TILE_SIZE * 2.2 and sideways <= GRID_TILE_SIZE * 0.85

        path = smooth_path(pts)

        def draw_tube_layer():
            scale = 2
            layer = pg.Surface((SCREEN_WIDTH * scale, SCREEN_HEIGHT * scale), pg.SRCALPHA)

            def scaled_point(value):
                return (int(value[0] * scale), int(value[1] * scale))

            def draw_tube(points, color, radius):
                draw_radius = int(radius * scale)
                draw_width = draw_radius * 2
                for i in range(1, len(points)):
                    pg.draw.line(layer, color, scaled_point(points[i - 1]), scaled_point(points[i]), draw_width)
                for p in points:
                    pg.draw.circle(layer, color, scaled_point(p), draw_radius)

            shadow_path = [(x + 2, y + 4) for x, y in path]
            draw_tube(shadow_path, shadow_color, body_r)
            underside_path = [(x, y + 2) for x, y in path]
            draw_tube(underside_path, body_edge, body_r)
            draw_tube(path, body_color, body_r)

            surface.blit(pg.transform.smoothscale(layer, (SCREEN_WIDTH, SCREEN_HEIGHT)), (0, 0))

        draw_tube_layer()

        hx, hy = pts[0]
        dx, dy = self.next_direction()
        perp_x = -dy
        perp_y = dx
        mouth_open = apple_is_close()

        # Cute rounded face at the front of the body.
        face_x = int(hx + dx * 2)
        face_y = int(hy + dy * 2)
        pg.draw.circle(surface, head_edge, (face_x, face_y), head_r + 2)
        pg.draw.circle(surface, head_color, (face_x, face_y), head_r)
        pg.draw.circle(surface, shine_color, (int(hx - dx * 2 - perp_x * 5), int(hy - dy * 2 - perp_y * 5)), 3)

        if mouth_open:
            mouth_x = int(face_x + dx * (head_r - 4))
            mouth_y = int(face_y + dy * (head_r - 4))
            if dx != 0:
                mouth_rect = pg.Rect(0, 0, 13, 22)
            else:
                mouth_rect = pg.Rect(0, 0, 22, 13)
            mouth_rect.center = (mouth_x, mouth_y)
            pg.draw.ellipse(surface, mouth_dark, mouth_rect)

            inner_rect = mouth_rect.inflate(-5, -5)
            pg.draw.ellipse(surface, mouth_red, inner_rect)
        elif pg.time.get_ticks() % 1300 < 190:
            start = (int(face_x + dx * (head_r - 1)), int(face_y + dy * (head_r - 1)))
            mid = (int(face_x + dx * (head_r + 8)), int(face_y + dy * (head_r + 8)))
            left = (int(face_x + dx * (head_r + 15) + perp_x * 4), int(face_y + dy * (head_r + 15) + perp_y * 4))
            right = (int(face_x + dx * (head_r + 15) - perp_x * 4), int(face_y + dy * (head_r + 15) - perp_y * 4))
            pg.draw.line(surface, tongue_color, start, mid, 3)
            pg.draw.line(surface, tongue_color, mid, left, 2)
            pg.draw.line(surface, tongue_color, mid, right, 2)

        eye_r = 6
        pupil_r = 3
        eye_forward = head_r * (-0.05 if mouth_open else 0.18)
        eye_side = head_r * 0.48
        eyes = [
            (hx + dx * eye_forward + perp_x * eye_side, hy + dy * eye_forward + perp_y * eye_side),
            (hx + dx * eye_forward - perp_x * eye_side, hy + dy * eye_forward - perp_y * eye_side)
        ]
        for ex, ey in eyes:
            pg.draw.circle(surface, head_edge, (int(ex), int(ey)), eye_r + 2)
            pg.draw.circle(surface, eye_white, (int(ex), int(ey)), eye_r)
            pg.draw.circle(surface, eye_dark, (int(ex + dx * 2), int(ey + dy * 2)), pupil_r)
            pg.draw.circle(surface, (255, 255, 255), (int(ex + dx), int(ey + dy - 1)), 1)


class Apple:
    def __init__(self, game):
        self.game = game
        self.randomize_position()

    def randomize_position(self, blocked=None):
        blocked_tiles = set(blocked or [])
        free_tiles = [
            (x, y)
            for x in range(GRID_SIZE)
            for y in range(GRID_SIZE)
            if (x, y) not in self.game.snake.body and (x, y) not in blocked_tiles
        ]
        if not free_tiles:
            self.pos = None
            return False

        self.pos = random.choice(free_tiles)
        return True

    def draw(self, surface):
        if self.pos is None:
            return

        gx, gy = self.pos
        px = GRID_OFFSET_X + gx * GRID_TILE_SIZE
        py = GRID_OFFSET_Y + gy * GRID_TILE_SIZE
        pulse = 1.0 + 0.05 * math.sin(pg.time.get_ticks() * 0.006)
        size = int((GRID_TILE_SIZE - 5) * pulse)
        cx = px + GRID_TILE_SIZE // 2
        cy = py + GRID_TILE_SIZE // 2 + 1
        rect = pg.Rect(0, 0, size, size)
        rect.center = (cx, cy)

        shadow_rect = rect.copy()
        shadow_rect.y += 5
        shadow_rect.w += 2
        shadow_rect.h = max(5, shadow_rect.h // 3)
        pg.draw.ellipse(surface, (118, 154, 42), shadow_rect)

        pg.draw.ellipse(surface, (176, 38, 32), rect.inflate(2, 2))
        pg.draw.ellipse(surface, (246, 64, 42), rect)
        pg.draw.ellipse(surface, (226, 48, 36), rect.move(2, 2), width=2)

        highlight = pg.Rect(rect.x + size // 5, rect.y + size // 5, max(4, size // 4), max(5, size // 3))
        pg.draw.ellipse(surface, (255, 143, 110), highlight)

        stem_top = (cx + 1, rect.y - 5)
        stem_bottom = (cx + 2, rect.y + 3)
        pg.draw.line(surface, (114, 75, 35), stem_bottom, stem_top, width=3)
        leaf_rect = pg.Rect(cx + 3, rect.y - 8, 12, 7)
        pg.draw.ellipse(surface, (63, 190, 73), leaf_rect)
