import pygame as pg # type: ignore
from settings import *
import random

vec = pg.math.Vector2

class Player(pg.sprite.Sprite):
    def __init__(self, game):
        super().__init__()
        self.game = game
        self.width = 40
        self.height = 40
        self.pos = vec(SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.75)
        self.vel = vec(0, 0)
        self.acc = vec(0, 0)
        self.facing_right = True
        self.jump_stretch = 1.0
        self.blink_timer = random.randint(90, 240)
        self.riding_platform = None
        self.image = pg.Surface((self.width, self.height), pg.SRCALPHA)
        self.rect = self.image.get_rect()
        self.rect.midbottom = self.pos
        self.draw_player()
        
    def draw_player(self):
        temp_surface = pg.Surface((self.width, self.height), pg.SRCALPHA)
        body_color = PLAYER_COLOR
        snout_color = (255, 105, 180)
        eye_white = (255, 255, 255)
        eye_pupil = (0, 0, 0)
        leg_color = (0, 0, 0)
        for lx in [12, 18, 24, 30]:
            pg.draw.line(temp_surface, leg_color, (lx, self.height - 6), (lx, self.height - 1), width=2)
        pg.draw.ellipse(temp_surface, body_color, (6, 4, self.width - 12, self.height - 10))
        eye_y = 12
        if self.vel.y < -2:
            eye_y = 8
        elif self.vel.y > 2:
            eye_y = 16
        if self.facing_right:
            pg.draw.ellipse(temp_surface, snout_color, (self.width - 14, 15, 12, 8))
            pg.draw.ellipse(temp_surface, leg_color, (self.width - 14, 15, 12, 8), width=1)
            pg.draw.circle(temp_surface, eye_white, (self.width - 18, eye_y), 4.5)
            pg.draw.circle(temp_surface, eye_pupil, (self.width - 17, eye_y), 2)
        else:
            pg.draw.ellipse(temp_surface, snout_color, (2, 15, 12, 8))
            pg.draw.ellipse(temp_surface, leg_color, (2, 15, 12, 8), width=1)
            pg.draw.circle(temp_surface, eye_white, (18, eye_y), 4.5)
            pg.draw.circle(temp_surface, eye_pupil, (17, eye_y), 2)
        w = int(self.width * (2.0 - self.jump_stretch))
        h = int(self.height * self.jump_stretch)
        w = max(10, min(w, 80))
        h = max(10, min(h, 80))
        scaled_image = pg.transform.smoothscale(temp_surface, (w, h))
        angle = -self.vel.x * 2.5
        angle = max(-15, min(15, angle))
        self.image = pg.transform.rotate(scaled_image, angle)
        self.rect = self.image.get_rect()
        self.rect.midbottom = self.pos
        
    def jump(self):
        self.vel.y = PLAYER_JUMP
        self.riding_platform = None
        self.jump_stretch = 1.45
        self.game.play_sound('jump')
        self.game.spawn_shockwave(self.pos.x, self.pos.y, PLAYER_COLOR)
        for _ in range(12):
            self.game.spawn_particle(
                self.pos.x, 
                self.pos.y, 
                PLAYER_COLOR, 
                vx=random.uniform(-4.0, 4.0), 
                vy=random.uniform(1.0, 4.0), 
                size=random.randint(3, 5)
            )

    def super_jump(self):
        self.vel.y = PLAYER_SUPER_JUMP
        self.riding_platform = None
        self.jump_stretch = 1.7
        self.game.play_sound('spring')
        self.game.spawn_shockwave(self.pos.x, self.pos.y, SPRING_COLOR)
        for _ in range(20):
            self.game.spawn_particle(
                self.pos.x, 
                self.pos.y, 
                SPRING_COLOR, 
                vx=random.uniform(-6.0, 6.0), 
                vy=random.uniform(2.0, 6.0), 
                size=random.randint(3, 6)
            )

    def update(self):
        self.acc = vec(0, GRAVITY)
        self.blink_timer -= 1
        if self.blink_timer <= 0:
            self.blink_timer = random.randint(90, 240)
        if abs(self.vel.y) > 2 and random.random() < 0.35:
            self.game.spawn_particle(self.pos.x + random.uniform(-5, 5), self.pos.y - 12, PLAYER_COLOR, size=random.randint(2, 4))
        keys = pg.key.get_pressed()
        if keys[pg.K_LEFT] or keys[pg.K_a]:
            self.acc.x = -PLAYER_ACC
            self.facing_right = False
        elif keys[pg.K_RIGHT] or keys[pg.K_d]:
            self.acc.x = PLAYER_ACC
            self.facing_right = True
        self.acc.x += self.vel.x * PLAYER_FRICTION
        self.vel += self.acc
        if self.vel.y > 18:
            self.vel.y = 18
        self.pos += self.vel + 0.5 * self.acc
        if self.riding_platform and self.riding_platform.alive():
            self.pos.x += self.riding_platform.vx
        if self.pos.x > SCREEN_WIDTH + self.width / 2:
            self.pos.x = -self.width / 2
        elif self.pos.x < -self.width / 2:
            self.pos.x = SCREEN_WIDTH + self.width / 2
        self.rect.midbottom = self.pos
        self.jump_stretch += (1.0 - self.jump_stretch) * 0.15
        self.draw_player()


class Platform(pg.sprite.Sprite):
    def __init__(self, game, x, y, plat_type='normal'):
        super().__init__()
        self.game = game
        self.type = plat_type
        self.width = PLATFORM_WIDTH
        self.height = PLATFORM_HEIGHT
        if self.type == 'moving':
            base_speed = random.choice([-2.2, -1.6, 1.6, 2.2])
            speed_factor = 1.0 + min(1.5, self.game.score / 500.0)
            self.vx = base_speed * speed_factor
        else:
            self.vx = 0
        self.broken = False
        self.stepped_on = False
        self.vy = 0
        self.image = pg.Surface((self.width, self.height), pg.SRCALPHA)
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.draw_platform()
        
    def draw_platform(self):
        self.image.fill((0, 0, 0, 0))
        body_h = self.height - 3
        if self.type == 'normal':
            pg.draw.rect(self.image, (12, 14, 22, 100), (0, 3, self.width, body_h), border_radius=6)
            pg.draw.rect(self.image, PLATFORM_COLOR, (0, 0, self.width, body_h), border_radius=6)
            pg.draw.rect(self.image, (150, 255, 240), (0, 0, self.width, body_h), width=2, border_radius=6)
            pg.draw.line(self.image, (255, 255, 255), (6, 2), (self.width - 6, 2), width=1)
            pg.draw.line(self.image, (255, 255, 255), (12, 2), (20, body_h - 2), width=2)
            pg.draw.circle(self.image, (255, 255, 255), (self.width - 15, body_h // 2), 2)
        elif self.type == 'moving':
            pg.draw.rect(self.image, (12, 14, 22, 100), (0, 3, self.width, body_h), border_radius=6)
            pg.draw.rect(self.image, MOVING_PLATFORM_COLOR, (0, 0, self.width, body_h), border_radius=6)
            pg.draw.rect(self.image, (255, 180, 245), (0, 0, self.width, body_h), width=2, border_radius=6)
            pg.draw.line(self.image, (255, 255, 255), (6, 2), (self.width - 6, 2), width=1)
            pg.draw.line(self.image, (255, 255, 255), (12, 2), (20, body_h - 2), width=2)
            pg.draw.circle(self.image, (255, 255, 255), (self.width - 15, body_h // 2), 2)
        elif self.type == 'broken':
            if not self.broken:
                pg.draw.rect(self.image, (12, 14, 22, 100), (0, 3, self.width, body_h), border_radius=6)
                pg.draw.rect(self.image, BREAKING_PLATFORM_COLOR, (0, 0, self.width, body_h), border_radius=6)
                pg.draw.rect(self.image, (255, 215, 130), (0, 0, self.width, body_h), width=2, border_radius=6)
                points = [
                    (self.width // 2 - 2, 0),
                    (self.width // 2 + 4, body_h // 3),
                    (self.width // 2 - 4, body_h * 2 // 3),
                    (self.width // 2 + 2, body_h)
                ]
                pg.draw.lines(self.image, (9, 4, 44), False, points, width=3)
                pg.draw.line(self.image, (255, 255, 255), (12, 2), (20, body_h - 2), width=2)
                pg.draw.circle(self.image, (255, 255, 255), (self.width - 15, body_h // 2), 2)
            else:
                shift = int(self.vy * 0.8)
                half_w = self.width // 2
                left_surf = pg.Surface((half_w, body_h), pg.SRCALPHA)
                pg.draw.rect(left_surf, BREAKING_PLATFORM_COLOR, (0, 0, half_w + 3, body_h), border_top_left_radius=6, border_bottom_left_radius=6)
                pg.draw.rect(left_surf, (255, 215, 130), (0, 0, half_w + 3, body_h), width=2, border_top_left_radius=6, border_bottom_left_radius=6)
                self.image.blit(left_surf, (-shift, shift // 2))
                right_surf = pg.Surface((half_w, body_h), pg.SRCALPHA)
                pg.draw.rect(right_surf, BREAKING_PLATFORM_COLOR, (-3, 0, half_w + 3, body_h), border_top_right_radius=6, border_bottom_right_radius=6)
                pg.draw.rect(right_surf, (255, 215, 130), (-3, 0, half_w + 3, body_h), width=2, border_top_right_radius=6, border_bottom_right_radius=6)
                self.image.blit(right_surf, (half_w + shift, shift // 2))

    def update(self):
        if self.type == 'moving':
            self.rect.x += self.vx
            if self.rect.right > SCREEN_WIDTH or self.rect.left < 0:
                self.vx *= -1
        if self.type == 'broken' and self.broken:
            self.vy += GRAVITY
            self.rect.y += self.vy
            self.draw_platform()
            if self.rect.top > SCREEN_HEIGHT:
                self.kill()


class Spring(pg.sprite.Sprite):
    def __init__(self, game, platform):
        super().__init__()
        self.game = game
        self.platform = platform
        self.width = 18
        self.height = 12
        self.activated = False
        self.image = pg.Surface((self.width, self.height), pg.SRCALPHA)
        self.rect = self.image.get_rect()
        self.rect.centerx = self.platform.rect.centerx
        self.rect.bottom = self.platform.rect.top
        self.draw_spring()
        
    def draw_spring(self):
        self.image.fill((0, 0, 0, 0))
        if not self.activated:
            pg.draw.rect(self.image, SPRING_COLOR, (0, 4, self.width, 8), border_radius=2)
            pg.draw.line(self.image, (200, 160, 0), (2, 8), (self.width - 2, 8), width=2)
        else:
            extended_height = 24
            self.image = pg.Surface((self.width, extended_height), pg.SRCALPHA)
            pg.draw.rect(self.image, SPRING_COLOR, (0, 0, self.width, 4), border_radius=2)
            points = [
                (self.width // 2, 2),
                (3, 8),
                (self.width - 3, 14),
                (3, 20),
                (self.width // 2, 23)
            ]
            pg.draw.lines(self.image, (200, 160, 0), False, points, width=3)
            old_bottom = self.rect.bottom
            old_centerx = self.rect.centerx
            self.rect = self.image.get_rect()
            self.rect.bottom = old_bottom
            self.rect.centerx = old_centerx
            
    def update(self):
        if not self.platform.alive() or (self.platform.type == 'broken' and self.platform.broken):
            self.kill()
            return
        self.rect.centerx = self.platform.rect.centerx
        self.rect.bottom = self.platform.rect.top
        if self.activated:
            self.draw_spring()


class Particle(pg.sprite.Sprite):
    def __init__(self, game, x, y, color, size=None, vx=None, vy=None):
        super().__init__()
        self.game = game
        self.size = size if size else random.randint(4, 7)
        self.color = color
        self.vx = vx if vx is not None else random.uniform(-2.5, 2.5)
        self.vy = vy if vy is not None else random.uniform(-5.0, -1.0)
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
        self.vy += 0.15
        self.size -= 0.12
        if self.size <= 0:
            self.kill()
        else:
            old_center = self.rect.center
            sz = max(1, int(self.size))
            self.image = pg.Surface((sz, sz), pg.SRCALPHA)
            pg.draw.rect(self.image, self.color, (0, 0, sz, sz), border_radius=1)
            self.rect = self.image.get_rect()
            self.rect.center = old_center
