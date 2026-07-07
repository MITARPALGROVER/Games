import pygame as pg # type: ignore
import sys
import random
import math
from settings import *
from sprites import *

def draw_hollow_star(surface, center, r_outer, r_inner, color, width=2):
    cx, cy = center
    points = []
    for i in range(10):
        angle = i * math.pi / 5 - math.pi / 2
        r = r_outer if i % 2 == 0 else r_inner
        x = cx + int(r * math.cos(angle))
        y = cy + int(r * math.sin(angle))
        points.append((x, y))
    pg.draw.polygon(surface, color, points, width=width)

def player_platform_collide(player, platform):
    fixed_rect = pg.Rect(0, 0, 22, 38)
    fixed_rect.midbottom = player.pos
    return fixed_rect.colliderect(platform.rect)

def player_spring_collide(player, spring):
    fixed_rect = pg.Rect(0, 0, 22, 38)
    fixed_rect.midbottom = player.pos
    return fixed_rect.colliderect(spring.rect)

class SoundManager:
    def __init__(self):
        self.sounds = {}
        try:
            pg.mixer.init()
            self.enabled = True
        except Exception:
            self.enabled = False
            return
            
        sound_files = {
            'jump': 'jump.wav',
            'spring': 'spring.wav',
            'break': 'break.wav',
            'gameover': 'gameover.wav'
        }
        for name, filename in sound_files.items():
            try:
                self.sounds[name] = pg.mixer.Sound(filename)
            except Exception:
                self.sounds[name] = None
                
    def play(self, name):
        if self.enabled and name in self.sounds and self.sounds[name]:
            try:
                self.sounds[name].play()
            except Exception:
                pass

class Game:
    def __init__(self):
        pg.init()
        try:
            self.screen = pg.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pg.SCALED, vsync=1)
        except Exception:
            try:
                self.screen = pg.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pg.SCALED)
            except Exception:
                self.screen = pg.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.display_surface = pg.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        pg.display.set_caption(TITLE)
        self.clock = pg.time.Clock()
        self.running = True
        self.font_name = pg.font.match_font('Segoe UI', 'arial')
        self.sound_manager = SoundManager()
        
        self.background_surface = pg.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            r = int(9 + (23 - 9) * (y / SCREEN_HEIGHT))
            g = int(4 + (11 - 4) * (y / SCREEN_HEIGHT))
            b = int(44 + (62 - 44) * (y / SCREEN_HEIGHT))
            pg.draw.line(self.background_surface, (r, g, b), (0, y), (SCREEN_WIDTH, y))
        
        self.stars = []
        for _ in range(25):
            self.stars.append({
                'pos': [random.randint(0, SCREEN_WIDTH), random.randint(0, SCREEN_HEIGHT)],
                'size': random.randint(1, 3),
                'color': random.choice([PLAYER_COLOR, ACCENT_COLOR, (255, 255, 255)]),
                'alpha': random.randint(60, 255),
                'twinkle_speed': random.uniform(2.5, 6.0),
                'type': random.choice(['circle', 'cross'])
            })
            
        self.load_data()
        
    def play_sound(self, name):
        self.sound_manager.play(name)
        
    def spawn_particle(self, x, y, color, size=None, vx=None, vy=None):
        p = Particle(self, x, y, color, size, vx, vy)
        self.all_sprites.add(p)
        self.particles.add(p)
        
    def spawn_shockwave(self, x, y, color):
        self.shockwaves.append({
            'x': x,
            'y': y,
            'radius': 3.0,
            'max_radius': 45.0,
            'speed': 3.0,
            'color': color,
            'width': 3
        })
        
    def load_data(self):
        try:
            with open('highscore.txt', 'r') as f:
                self.highscore = int(f.read())
        except (FileNotFoundError, ValueError):
            self.highscore = 0
            try:
                with open('highscore.txt', 'w') as f:
                    f.write('0')
            except Exception:
                pass
        
    def new(self):
        self.score = 0
        self.screen_shake = 0
        self.all_sprites = pg.sprite.Group()
        self.platforms = pg.sprite.Group()
        self.springs = pg.sprite.Group()
        self.particles = pg.sprite.Group()
        self.shockwaves = []
        
        self.player = Player(self)
        self.all_sprites.add(self.player)
        
        p_start = Platform(self, SCREEN_WIDTH / 2 - PLATFORM_WIDTH / 2, SCREEN_HEIGHT - 60, 'normal')
        self.all_sprites.add(p_start)
        self.platforms.add(p_start)
        
        for i in range(7):
            p = Platform(
                self,
                random.randrange(0, SCREEN_WIDTH - PLATFORM_WIDTH),
                SCREEN_HEIGHT - 130 - i * 85,
                'normal'
            )
            self.all_sprites.add(p)
            self.platforms.add(p)
            
        self.run()
        
    def run(self):
        self.playing = True
        while self.playing:
            self.clock.tick(FPS)
            self.events()
            self.update()
            self.draw()
            
    def update(self):
        self.all_sprites.update()
        
        for sw in self.shockwaves[:]:
            sw['radius'] += sw['speed']
            if sw['radius'] >= sw['max_radius']:
                self.shockwaves.remove(sw)
                
        spring_activated = False
        hits_springs = pg.sprite.spritecollide(self.player, self.springs, False, collided=player_spring_collide)
        for spring in hits_springs:
            if not spring.activated and self.player.vel.y > 0:
                if (self.player.pos.y - self.player.vel.y) <= spring.rect.top + 8:
                    spring.activated = True
                    self.player.super_jump()
                    self.screen_shake = 12
                    for _ in range(16):
                        self.spawn_particle(spring.rect.centerx, spring.rect.top, SPRING_COLOR)
                    spring_activated = True
                    break
                    
        if not spring_activated:
            hits = pg.sprite.spritecollide(self.player, self.platforms, False, collided=player_platform_collide)
            if self.player.vel.y >= 0:
                if hits:
                    lowest = hits[0]
                    for hit in hits:
                        if hit.rect.y > lowest.rect.y:
                            lowest = hit
                    if (self.player.pos.y - self.player.vel.y) <= lowest.rect.top + 8:
                        if lowest.type == 'broken':
                            if not lowest.broken:
                                self.player.pos.y = lowest.rect.top
                                self.player.jump()
                                lowest.broken = True
                                self.play_sound('break')
                                for _ in range(10):
                                    self.spawn_particle(lowest.rect.centerx, lowest.rect.centery, BREAKING_PLATFORM_COLOR)
                        else:
                            self.player.pos.y = lowest.rect.top
                            self.player.jump()
                    
        if self.player.rect.top <= SCREEN_HEIGHT / 4:
            if self.player.vel.y < 0:
                scroll_amount = abs(self.player.vel.y)
                self.player.pos.y += scroll_amount
                
                for star in self.stars:
                    star['pos'][1] += scroll_amount * 0.35
                    if star['pos'][1] >= SCREEN_HEIGHT:
                        star['pos'][1] = random.randint(-50, -5)
                        star['pos'][0] = random.randint(0, SCREEN_WIDTH)
                        
                for plat in self.platforms:
                    plat.rect.y += scroll_amount
                    if plat.rect.top >= SCREEN_HEIGHT:
                        plat.kill()
                        self.score += 10
                        
        while len(self.platforms) < 8:
            highest_plat = None
            highest_y = SCREEN_HEIGHT
            for plat in self.platforms:
                if plat.rect.y < highest_y:
                    highest_y = plat.rect.y
                    highest_plat = plat
                    
            if self.score < 200:
                min_dy, max_dy = 65, 85
                max_shift = 120
                plat_type = 'normal'
            elif self.score < 600:
                min_dy, max_dy = 75, 110
                max_shift = 150
                rand = random.random()
                if rand < 0.65:
                    plat_type = 'normal'
                elif rand < 0.85:
                    plat_type = 'moving'
                else:
                    plat_type = 'broken'
            else:
                min_dy, max_dy = 95, 135
                max_shift = 185
                rand = random.random()
                if rand < 0.25:
                    plat_type = 'normal'
                elif rand < 0.65:
                    plat_type = 'moving'
                else:
                    plat_type = 'broken'
            
            new_y = highest_y - random.randrange(min_dy, max_dy)
            
            if highest_plat:
                min_x = max(0, highest_plat.rect.x - max_shift)
                max_x = min(SCREEN_WIDTH - PLATFORM_WIDTH, highest_plat.rect.x + max_shift)
                new_x = random.randint(min_x, max_x)
            else:
                new_x = random.randrange(0, SCREEN_WIDTH - PLATFORM_WIDTH)
                
            if highest_plat and highest_plat.type == 'broken':
                plat_type = 'normal' if random.random() < 0.6 else 'moving'
            
            p = Platform(self, new_x, new_y, plat_type)
            self.all_sprites.add(p)
            self.platforms.add(p)
            
            if plat_type in ['normal', 'moving'] and random.random() < 0.15:
                s = Spring(self, p)
                self.all_sprites.add(s)
                self.springs.add(s)
            
        if self.player.rect.top > SCREEN_HEIGHT:
            self.player.riding_platform = None
            self.play_sound('gameover')
            self.playing = False
            if self.score > self.highscore:
                self.highscore = self.score
                try:
                    with open('highscore.txt', 'w') as f:
                        f.write(str(self.highscore))
                except Exception:
                    pass
            
    def events(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                if self.playing:
                    self.playing = False
                self.running = False
                
    def draw_background_effects(self):
        self.display_surface.blit(self.background_surface, (0, 0))
        
        for star in self.stars:
            star['alpha'] += star['twinkle_speed']
            if star['alpha'] >= 255 or star['alpha'] <= 50:
                star['twinkle_speed'] *= -1
            star['alpha'] = max(50, min(255, star['alpha']))
            
            x, y = int(star['pos'][0]), int(star['pos'][1])
            size = star['size']
            c = star['color']
            star_color = (
                int(c[0] * (star['alpha'] / 255.0)),
                int(c[1] * (star['alpha'] / 255.0)),
                int(c[2] * (star['alpha'] / 255.0))
            )
            
            if star['type'] == 'cross':
                pg.draw.line(self.display_surface, star_color, (x - size*2, y), (x + size*2, y), width=1)
                pg.draw.line(self.display_surface, star_color, (x, y - size*2), (x, y + size*2), width=1)
            else:
                pg.draw.circle(self.display_surface, star_color, (x, y), size)
                
        cloud_color = (18, 9, 46)
        pg.draw.circle(self.display_surface, cloud_color, (60, SCREEN_HEIGHT + 40), 90)
        pg.draw.circle(self.display_surface, cloud_color, (200, SCREEN_HEIGHT + 60), 110)
        pg.draw.circle(self.display_surface, cloud_color, (340, SCREEN_HEIGHT + 30), 80)
        outline_color = (235, 60, 210)
        pg.draw.circle(self.display_surface, outline_color, (60, SCREEN_HEIGHT + 40), 90, width=1)
        pg.draw.circle(self.display_surface, outline_color, (200, SCREEN_HEIGHT + 60), 110, width=1)
        pg.draw.circle(self.display_surface, outline_color, (340, SCREEN_HEIGHT + 30), 80, width=1)
        
        draw_hollow_star(self.display_surface, (55, 150), 12, 6, (235, 60, 210), width=2)
        draw_hollow_star(self.display_surface, (285, 120), 12, 6, (255, 215, 70), width=2)

    def draw(self):
        self.draw_background_effects()
        
        for sw in self.shockwaves:
            pct = 1.0 - (sw['radius'] / sw['max_radius'])
            alpha = int(255 * pct)
            if alpha > 0:
                sw_surf = pg.Surface((int(sw['radius'] * 2 + 10), int(sw['radius'] * 2 + 10)), pg.SRCALPHA)
                color = (sw['color'][0], sw['color'][1], sw['color'][2], alpha)
                pg.draw.circle(sw_surf, color, (int(sw['radius'] + 5), int(sw['radius'] + 5)), int(sw['radius']), max(1, int(sw['width'] * pct)))
                self.display_surface.blit(sw_surf, (int(sw['x'] - sw['radius'] - 5), int(sw['y'] - sw['radius'] - 5)))
                
        self.all_sprites.draw(self.display_surface)
        
        cap_w = 200
        cap_h = 46
        cap_x = (SCREEN_WIDTH - cap_w) // 2
        cap_y = 15
        
        cap_surf = pg.Surface((cap_w, cap_h), pg.SRCALPHA)
        pg.draw.rect(cap_surf, (10, 15, 30, 200), (0, 0, cap_w, cap_h), border_radius=12)
        pg.draw.rect(cap_surf, (0, 240, 200), (0, 0, cap_w, cap_h), width=2, border_radius=12)
        self.display_surface.blit(cap_surf, (cap_x, cap_y))
        
        self.draw_text("SCORE: ", 22, TEXT_COLOR, cap_x + 55, cap_y + 10, bold=True)
        self.draw_text(f"{self.score}", 22, PLATFORM_COLOR, cap_x + 135, cap_y + 10, bold=True, glow_color=(0, 150, 120))
        
        if self.screen_shake > 0:
            dx = random.randint(-self.screen_shake, self.screen_shake)
            dy = random.randint(-self.screen_shake, self.screen_shake)
            self.screen.blit(self.display_surface, (dx, dy))
            self.screen_shake = max(0, self.screen_shake - 1)
        else:
            self.screen.blit(self.display_surface, (0, 0))
            
        pg.display.flip()
        
    def draw_text(self, text, size, color, x, y, bold=False, glow_color=None, shadow_offset=None):
        font = pg.font.Font(self.font_name, size)
        font.set_bold(bold)
        
        if shadow_offset:
            shadow_color = shadow_offset.get('color', (8, 4, 30))
            offset_val = shadow_offset.get('offset', 4)
            shadow_surface = font.render(text, True, shadow_color)
            shadow_rect = shadow_surface.get_rect()
            
            for dx in range(-offset_val, offset_val + 1):
                for dy in range(-offset_val, offset_val + 1):
                    if dx*dx + dy*dy <= offset_val*offset_val:
                        shadow_rect.midtop = (x + dx + 1, y + dy + 2)
                        self.display_surface.blit(shadow_surface, shadow_rect)
        
        if glow_color:
            glow_surface = font.render(text, True, glow_color)
            glow_rect = glow_surface.get_rect()
            for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
                glow_rect.midtop = (x + dx, y + dy)
                self.display_surface.blit(glow_surface, glow_rect)
                
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect()
        text_rect.midtop = (x, y)
        self.display_surface.blit(text_surface, text_rect)
        
    def draw_medal(self, surface, center, rank, score_text):
        cx, cy = center
        if rank == 1:
            ribbon_color = (220, 130, 0)
            medal_color = (255, 195, 0)
            border_color = (255, 220, 100)
        elif rank == 2:
            ribbon_color = (140, 150, 165)
            medal_color = (185, 195, 205)
            border_color = (225, 230, 240)
        else:
            ribbon_color = (160, 90, 30)
            medal_color = (205, 127, 50)
            border_color = (235, 170, 110)
            
        pg.draw.polygon(surface, ribbon_color, [(cx - 8, cy + 4), (cx - 12, cy + 20), (cx - 5, cy + 16), (cx, cy + 4)])
        pg.draw.polygon(surface, ribbon_color, [(cx, cy + 4), (cx + 5, cy + 16), (cx + 12, cy + 20), (cx + 8, cy + 4)])
        
        pg.draw.circle(surface, medal_color, (cx, cy), 11)
        pg.draw.circle(surface, border_color, (cx, cy), 11, width=2)
        
        self.draw_text(str(rank), 13, (0, 0, 0), cx, cy - 6, bold=True)
        
    def draw_key_icon(self, text, x, y):
        pg.draw.rect(self.display_surface, (10, 15, 30), (x, y, 22, 22), border_radius=4)
        pg.draw.rect(self.display_surface, (0, 240, 200), (x, y, 22, 22), width=1, border_radius=4)
        
        font = pg.font.Font(self.font_name, 11)
        font.set_bold(True)
        ts = font.render(text, True, (0, 240, 200))
        tr = ts.get_rect()
        tr.center = (x + 11, y + 10)
        self.display_surface.blit(ts, tr)
        
    def show_start_screen(self):
        waiting = True
        pg.event.pump()
        while waiting:
            self.clock.tick(FPS)
            
            self.draw_background_effects()
            
            pg.draw.rect(self.display_surface, (12, 14, 22, 100), (15, SCREEN_HEIGHT // 2 - 117, 70, 12), border_radius=6)
            pg.draw.rect(self.display_surface, PLATFORM_COLOR, (15, SCREEN_HEIGHT // 2 - 120, 70, 12), border_radius=6)
            pg.draw.rect(self.display_surface, (150, 255, 240), (15, SCREEN_HEIGHT // 2 - 120, 70, 12), width=2, border_radius=6)
            
            pg.draw.rect(self.display_surface, (12, 14, 22, 100), (SCREEN_WIDTH - 85, SCREEN_HEIGHT // 2 - 157, 70, 12), border_radius=6)
            pg.draw.rect(self.display_surface, MOVING_PLATFORM_COLOR, (SCREEN_WIDTH - 85, SCREEN_HEIGHT // 2 - 160, 70, 12), border_radius=6)
            pg.draw.rect(self.display_surface, (255, 180, 245), (SCREEN_WIDTH - 85, SCREEN_HEIGHT // 2 - 160, 70, 12), width=2, border_radius=6)

            pg.draw.rect(self.display_surface, (12, 14, 22, 100), (SCREEN_WIDTH - 85, SCREEN_HEIGHT // 2 - 47, 70, 12), border_radius=6)
            pg.draw.rect(self.display_surface, PLATFORM_COLOR, (SCREEN_WIDTH - 85, SCREEN_HEIGHT // 2 - 50, 70, 12), border_radius=6)
            pg.draw.rect(self.display_surface, (150, 255, 240), (SCREEN_WIDTH - 85, SCREEN_HEIGHT // 2 - 50, 70, 12), width=2, border_radius=6)

            pg.draw.rect(self.display_surface, (12, 14, 22, 100), (SCREEN_WIDTH - 85, SCREEN_HEIGHT // 2 + 57, 70, 12), border_radius=6)
            pg.draw.rect(self.display_surface, BREAKING_PLATFORM_COLOR, (SCREEN_WIDTH - 85, SCREEN_HEIGHT // 2 + 60, 70, 12), border_radius=6)
            pg.draw.rect(self.display_surface, (255, 215, 130), (SCREEN_WIDTH - 85, SCREEN_HEIGHT // 2 + 60, 70, 12), width=2, border_radius=6)
            
            pg.draw.rect(self.display_surface, (12, 14, 22, 100), (20, SCREEN_HEIGHT - 57, 80, 12), border_radius=6)
            pg.draw.rect(self.display_surface, PLATFORM_COLOR, (20, SCREEN_HEIGHT - 60, 80, 12), border_radius=6)
            pg.draw.rect(self.display_surface, (150, 255, 240), (20, SCREEN_HEIGHT - 60, 80, 12), width=2, border_radius=6)
            
            dj_x = 35
            dj_y = SCREEN_HEIGHT - 95
            pg.draw.ellipse(self.display_surface, (255, 225, 75), (dj_x, dj_y, 40, 36))
            pg.draw.ellipse(self.display_surface, (255, 225, 75), (dj_x + 28, dj_y + 15, 12, 8))
            pg.draw.ellipse(self.display_surface, (0, 0, 0), (dj_x + 28, dj_y + 15, 12, 8), width=1)
            pg.draw.circle(self.display_surface, (255, 255, 255), (dj_x + 20, dj_y + 12), 4)
            pg.draw.circle(self.display_surface, (0, 0, 0), (dj_x + 21, dj_y + 12), 1.5)
            pg.draw.ellipse(self.display_surface, (0, 160, 100), (dj_x + 2, dj_y + 26, 36, 4))
            pg.draw.ellipse(self.display_surface, (0, 160, 100), (dj_x + 4, dj_y + 30, 32, 3))
            for lx in [6, 14, 22, 30]:
                pg.draw.line(self.display_surface, (0, 0, 0), (dj_x + lx, dj_y + 34), (dj_x + lx, dj_y + 39), width=2)
            
            self.draw_text("DOODLE", 40, TEXT_COLOR, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4 - 65, bold=True, shadow_offset={'color': (8, 4, 30), 'offset': 4})
            self.draw_text("JUMP", 48, (235, 60, 210), SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4 - 20, bold=True, shadow_offset={'color': (8, 4, 30), 'offset': 5})
            self.draw_text("RETRO", 38, PLATFORM_COLOR, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4 + 25, bold=True, shadow_offset={'color': (8, 4, 30), 'offset': 4})
            
            card_w = 300
            card_h = 160
            card_x = (SCREEN_WIDTH - card_w) // 2
            card_y = SCREEN_HEIGHT // 2 - 50
            
            card_surf = pg.Surface((card_w, card_h), pg.SRCALPHA)
            pg.draw.rect(card_surf, (10, 15, 30, 210), (0, 0, card_w, card_h), border_radius=10)
            pg.draw.rect(card_surf, (235, 60, 210, 150), (0, 0, card_w, card_h), width=1, border_radius=10)
            self.display_surface.blit(card_surf, (card_x, card_y))
            
            self.draw_text("HIGH SCORES", 18, TEXT_COLOR, SCREEN_WIDTH // 2, card_y + 12, bold=True)
            
            for i, score_val in enumerate([f"{self.highscore} PTS", "---", "---"]):
                row_y = card_y + 42 + i * 36
                pg.draw.rect(self.display_surface, (14, 18, 38, 220), (card_x + 12, row_y, card_w - 24, 30), border_radius=6)
                self.draw_medal(self.display_surface, (card_x + 35, row_y + 15), i + 1, score_val)
                score_color = PLATFORM_COLOR if i == 0 else TEXT_COLOR
                self.draw_text(score_val, 15, score_color, card_x + 160, row_y + 7, bold=(i == 0))
            
            ctrl_w = 300
            ctrl_h = 50
            ctrl_x = (SCREEN_WIDTH - ctrl_w) // 2
            ctrl_y = card_y + card_h + 15
            
            ctrl_surf = pg.Surface((ctrl_w, ctrl_h), pg.SRCALPHA)
            pg.draw.rect(ctrl_surf, (10, 15, 30, 180), (0, 0, ctrl_w, ctrl_h), border_radius=8)
            pg.draw.rect(ctrl_surf, (0, 240, 200, 120), (0, 0, ctrl_w, ctrl_h), width=1, border_radius=8)
            self.display_surface.blit(ctrl_surf, (ctrl_x, ctrl_y))
            
            self.draw_key_icon("<-", ctrl_x + 18, ctrl_y + 14)
            self.draw_key_icon("->", ctrl_x + 46, ctrl_y + 14)
            self.draw_text("Use Arrows or A/D to steer", 13, TEXT_COLOR, ctrl_x + 160, ctrl_y + 16)
            self.draw_key_icon("A", ctrl_x + 242, ctrl_y + 14)
            self.draw_key_icon("D", ctrl_x + 270, ctrl_y + 14)
            
            btn_w = 220
            btn_h = 46
            btn_x = (SCREEN_WIDTH - btn_w) // 2
            btn_y = SCREEN_HEIGHT * 13 // 16
            
            pulse = int(127 + 128 * abs(pg.time.get_ticks() / 300.0 % 2.0 - 1.0))
            pulse = max(60, min(255, pulse))
            btn_color = (int(ACCENT_COLOR[0] * (pulse / 255.0)), int(ACCENT_COLOR[1] * (pulse / 255.0)), int(ACCENT_COLOR[2] * (pulse / 255.0)))
            
            btn_surf = pg.Surface((btn_w, btn_h), pg.SRCALPHA)
            pg.draw.rect(btn_surf, (10, 15, 30, 220), (0, 0, btn_w, btn_h), border_radius=14)
            pg.draw.rect(btn_surf, btn_color, (0, 0, btn_w, btn_h), width=2, border_radius=14)
            
            for px, py in [(20, 10), (45, 30), (90, 15), (140, 35), (180, 12), (200, 28)]:
                pg.draw.circle(btn_surf, (255, 255, 255, 100), (px, py), 1)
                
            self.display_surface.blit(btn_surf, (btn_x, btn_y))
            
            self.draw_text("PRESS ENTER/SPACE", 14, TEXT_COLOR, btn_x + btn_w//2, btn_y + 8, bold=True)
            self.draw_text("TO BOUNCE OFF!", 14, TEXT_COLOR, btn_x + btn_w//2, btn_y + 24, bold=True)
            
            self.screen.blit(self.display_surface, (0, 0))
            pg.display.flip()
            
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    waiting = False
                    self.running = False
                if event.type == pg.KEYUP:
                    if event.key == pg.K_RETURN or event.key == pg.K_SPACE:
                        waiting = False
        
    def show_go_screen(self):
        if not self.running:
            return
        waiting = True
        pg.event.pump()
        while waiting:
            self.clock.tick(FPS)
            
            self.draw_background_effects()
            
            self.draw_text("GAME OVER", 38, (255, 80, 80), SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4 - 30, bold=True, shadow_offset={'color': (8, 4, 30), 'offset': 4})
            
            card_w = 300
            card_h = 160
            card_x = (SCREEN_WIDTH - card_w) // 2
            card_y = SCREEN_HEIGHT // 2 - 50
            
            card_surf = pg.Surface((card_w, card_h), pg.SRCALPHA)
            pg.draw.rect(card_surf, (10, 15, 30, 210), (0, 0, card_w, card_h), border_radius=10)
            pg.draw.rect(card_surf, (235, 60, 210, 150), (0, 0, card_w, card_h), width=1, border_radius=10)
            self.display_surface.blit(card_surf, (card_x, card_y))
            
            row1_y = card_y + 42
            pg.draw.rect(self.display_surface, (14, 18, 38, 220), (card_x + 12, row1_y, card_w - 24, 30), border_radius=6)
            self.draw_medal(self.display_surface, (card_x + 35, row1_y + 15), 1, f"{self.highscore} PTS")
            self.draw_text(f"HIGH RECORD: {self.highscore} PTS", 14, ACCENT_COLOR, card_x + 160, row1_y + 7, bold=True)
            
            row2_y = card_y + 88
            pg.draw.rect(self.display_surface, (14, 18, 38, 220), (card_x + 12, row2_y, card_w - 24, 42), border_radius=6)
            self.draw_text("FINAL SCORE", 13, TEXT_COLOR, card_x + 160, row2_y + 4)
            self.draw_text(f"{self.score} PTS", 18, PLATFORM_COLOR, card_x + 160, row2_y + 18, bold=True, glow_color=(0, 180, 120))
            
            btn_w = 220
            btn_h = 46
            btn_x = (SCREEN_WIDTH - btn_w) // 2
            btn_y = SCREEN_HEIGHT * 13 // 16
            
            pulse = int(127 + 128 * abs(pg.time.get_ticks() / 300.0 % 2.0 - 1.0))
            pulse = max(60, min(255, pulse))
            btn_color = (int(ACCENT_COLOR[0] * (pulse / 255.0)), int(ACCENT_COLOR[1] * (pulse / 255.0)), int(ACCENT_COLOR[2] * (pulse / 255.0)))
            
            btn_surf = pg.Surface((btn_w, btn_h), pg.SRCALPHA)
            pg.draw.rect(btn_surf, (10, 15, 30, 220), (0, 0, btn_w, btn_h), border_radius=14)
            pg.draw.rect(btn_surf, btn_color, (0, 0, btn_w, btn_h), width=2, border_radius=14)
            
            for px, py in [(20, 10), (45, 30), (90, 15), (140, 35), (180, 12), (200, 28)]:
                pg.draw.circle(btn_surf, (255, 255, 255, 100), (px, py), 1)
                
            self.display_surface.blit(btn_surf, (btn_x, btn_y))
            
            self.draw_text("PRESS ENTER/SPACE", 14, TEXT_COLOR, btn_x + btn_w//2, btn_y + 8, bold=True)
            self.draw_text("TO TRY AGAIN", 14, TEXT_COLOR, btn_x + btn_w//2, btn_y + 24, bold=True)
            
            self.screen.blit(self.display_surface, (0, 0))
            pg.display.flip()
            
            for event in pg.event.get():
                if event.type == pg.QUIT:
                    waiting = False
                    self.running = False
                if event.type == pg.KEYUP:
                    if event.key == pg.K_RETURN or event.key == pg.K_SPACE:
                        waiting = False

if __name__ == "__main__":
    g = Game()
    g.show_start_screen()
    while g.running:
        g.new()
        g.show_go_screen()
    pg.quit()
    sys.exit()
