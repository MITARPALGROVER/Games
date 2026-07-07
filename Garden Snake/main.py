import pygame as pg
import sys
import random
import math
import os
from settings import *
from sprites import *

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HIGHSCORE_FILE = os.path.join(BASE_DIR, "highscore.txt")


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
            'eat': os.path.join(BASE_DIR, '..', 'jump.wav'),
            'gameover': os.path.join(BASE_DIR, '..', 'gameover.wav')
        }
        for name, filename in sound_files.items():
            try:
                if os.path.exists(filename):
                    self.sounds[name] = pg.mixer.Sound(filename)
                else:
                    self.sounds[name] = None
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
        self.font_name = pg.font.match_font(['segoeui', 'arial', 'dejavusans'])
        self.sound_manager = SoundManager()
        
        self.background_surface = pg.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        for y in range(SCREEN_HEIGHT):
            r = int(110 + (220 - 110) * (y / SCREEN_HEIGHT))
            g = int(190 + (240 - 190) * (y / SCREEN_HEIGHT))
            b = int(255 + (255 - 255) * (y / SCREEN_HEIGHT))
            pg.draw.line(self.background_surface, (r, g, b), (0, y), (SCREEN_WIDTH, y))

        grass_rng = random.Random(7)
        self.ground_blades = [
            {
                "x": grass_rng.randint(0, SCREEN_WIDTH),
                "y": grass_rng.randint(SCREEN_HEIGHT - 36, SCREEN_HEIGHT - 6),
                "h": grass_rng.randint(8, 24),
                "phase": grass_rng.uniform(0, math.tau),
                "color": grass_rng.choice([(56, 150, 70), (72, 176, 82), (38, 128, 58)])
            }
            for _ in range(70)
        ]

        self.load_data()
        
    def play_sound(self, name):
        self.sound_manager.play(name)
        
    def spawn_particle(self, x, y, color):
        p = LeafParticle(self, x, y, color)
        self.all_sprites.add(p)
        self.particles.add(p)
        
    def load_data(self):
        try:
            with open(HIGHSCORE_FILE, 'r') as f:
                self.highscore = int(f.read())
        except (FileNotFoundError, ValueError):
            self.highscore = 0
            try:
                with open(HIGHSCORE_FILE, 'w') as f:
                    f.write('0')
            except Exception:
                pass
                
    def new(self):
        self.score = 0
        self.slide_progress = 0.0
        self.crash_triggered = False
        self.final_draw_progress = 0.0
        self.cloud_spawn_timer = 0
        self.won = False
        self.all_sprites = pg.sprite.Group()
        self.clouds = pg.sprite.Group()
        self.particles = pg.sprite.Group()
        self.snake = Snake(self)
        self.apple = Apple(self)
        
        for _ in range(5):
            cloud = BackgroundCloud(self, random.randint(0, SCREEN_WIDTH), random.randint(30, 200))
            self.all_sprites.add(cloud)
            self.clouds.add(cloud)
            
        self.run()
        
    def run(self):
        self.playing = True
        while self.playing:
            self.clock.tick(FPS)
            self.events()
            self.update()
            self.draw()
            
    def will_collide(self):
        head = self.snake.body[0]
        dx, dy = self.snake.next_direction()
        target = (head[0] + dx, head[1] + dy)
        if target[0] < 0 or target[0] >= GRID_SIZE or target[1] < 0 or target[1] >= GRID_SIZE:
            return True, "wall"

        solid_body = self.snake.body if self.snake.grow_segments > 0 else self.snake.body[:-1]
        if target in solid_body:
            return True, "self"
        return False, None

    def next_head_cell(self):
        head_x, head_y = self.snake.body[0]
        dx, dy = self.snake.next_direction()
        return (head_x + dx, head_y + dy)

    def eat_apple(self, target):
        if self.apple.pos != target:
            return

        self.snake.grow()
        self.score += 1
        self.play_sound('eat')

        gx, gy = self.apple.pos
        ax = GRID_OFFSET_X + gx * GRID_TILE_SIZE + GRID_TILE_SIZE // 2
        ay = GRID_OFFSET_Y + gy * GRID_TILE_SIZE + GRID_TILE_SIZE // 2
        for _ in range(12):
            self.spawn_particle(ax, ay, APPLE_COLOR)
        for _ in range(6):
            self.spawn_particle(ax, ay, CATERPILLAR_LEAF)

        blocked = set(self.snake.body)
        blocked.add(target)
        if not self.apple.randomize_position(blocked):
            self.won = True
            self.playing = False
            self.save_highscore()

    def save_highscore(self):
        if self.score > self.highscore:
            self.highscore = self.score
            try:
                with open(HIGHSCORE_FILE, 'w') as f:
                    f.write(str(self.highscore))
            except Exception:
                pass

    def update(self):
        self.all_sprites.update()
        
        self.cloud_spawn_timer += 1
        if self.cloud_spawn_timer >= random.randint(180, 320):
            self.cloud_spawn_timer = 0
            cloud = BackgroundCloud(self, SCREEN_WIDTH + 80, random.randint(30, 200))
            self.all_sprites.add(cloud)
            self.clouds.add(cloud)
            
        move_delay = max(4, 12 - int(self.score // 4))
        is_collision, collision_type = self.will_collide()
        
        if is_collision:
            self.slide_progress += 1.0 / move_delay
            if self.slide_progress >= 0.35 and not self.crash_triggered:
                self.crash_triggered = True
                self.play_sound('gameover')
                hx, hy = self.snake.body[0]
                dx, dy = self.snake.direction
                cx = GRID_OFFSET_X + (hx + dx * 0.4) * GRID_TILE_SIZE + GRID_TILE_SIZE // 2
                cy = GRID_OFFSET_Y + (hy + dy * 0.4) * GRID_TILE_SIZE + GRID_TILE_SIZE // 2
                for _ in range(20):
                    self.spawn_particle(cx, cy, (230, 70, 70))
            
            if self.slide_progress >= 1.0:
                t = 1.0
                self.final_draw_progress = -0.2 + 0.12 * math.sin((t - 0.7) * 25.0) * math.exp(-(t - 0.7) * 6.0)
                self.playing = False
                self.save_highscore()
        else:
            self.slide_progress += 1.0 / move_delay
            target = self.next_head_cell()
            if self.slide_progress >= 0.38:
                self.eat_apple(target)
                if not self.playing:
                    return

            if self.slide_progress >= 1.0:
                self.slide_progress -= 1.0
                self.snake.move()
                
    def events(self):
        for event in pg.event.get():
            if event.type == pg.QUIT:
                if self.playing:
                    self.playing = False
                self.running = False
            self.snake.handle_input(event)
            
    def draw_background_effects(self):
        self.display_surface.blit(self.background_surface, (0, 0))
        self.clouds.draw(self.display_surface)
        
        pg.draw.circle(self.display_surface, (80, 180, 100), (90, SCREEN_HEIGHT + 40), 170)
        pg.draw.circle(self.display_surface, (80, 180, 100), (360, SCREEN_HEIGHT + 50), 190)
        pg.draw.circle(self.display_surface, (46, 150, 75), (225, SCREEN_HEIGHT + 70), 210)
        
        wave = math.sin(pg.time.get_ticks() * 0.002) * 8
        pg.draw.ellipse(self.display_surface, (86, 190, 94), (-40 + int(wave), SCREEN_HEIGHT - 105, 160, 80))
        pg.draw.ellipse(self.display_surface, (70, 166, 82), (330 - int(wave), SCREEN_HEIGHT - 95, 160, 70))

        pg.draw.rect(self.display_surface, (34, 112, 56), (0, SCREEN_HEIGHT - 40, SCREEN_WIDTH, 40))

        sway_time = pg.time.get_ticks() * 0.004
        for blade in self.ground_blades:
            sway = math.sin(sway_time + blade["phase"]) * 4
            x = blade["x"]
            y = blade["y"]
            tip = (int(x + sway), int(y - blade["h"]))
            pg.draw.line(self.display_surface, blade["color"], (x, y), tip, width=2)

        pg.draw.rect(self.display_surface, (20, 80, 40), (0, SCREEN_HEIGHT - 40, SCREEN_WIDTH, 40), width=2)
        
    def draw(self):
        self.draw_background_effects()
        
        pg.draw.rect(self.display_surface, (40, 100, 45), (GRID_OFFSET_X - 3, GRID_OFFSET_Y - 3, GRID_SIZE * GRID_TILE_SIZE + 6, GRID_SIZE * GRID_TILE_SIZE + 6), width=3, border_radius=4)
        for x in range(GRID_SIZE):
            for y in range(GRID_SIZE):
                px = GRID_OFFSET_X + x * GRID_TILE_SIZE
                py = GRID_OFFSET_Y + y * GRID_TILE_SIZE
                tile_color = GRASS_LIGHT if (x + y) % 2 == 0 else GRASS_DARK
                pg.draw.rect(self.display_surface, tile_color, (px, py, GRID_TILE_SIZE, GRID_TILE_SIZE))
                
        is_collision, _ = self.will_collide()
        if is_collision:
            t = self.slide_progress
            if t < 0.35:
                draw_progress = t
            elif t < 0.7:
                draw_progress = 0.35 - (t - 0.35) * 2.0
            else:
                draw_progress = -0.2 + 0.12 * math.sin((t - 0.7) * 25.0) * math.exp(-(t - 0.7) * 6.0)
        else:
            draw_progress = self.slide_progress
            
        grid_rect = pg.Rect(GRID_OFFSET_X, GRID_OFFSET_Y, GRID_SIZE * GRID_TILE_SIZE, GRID_SIZE * GRID_TILE_SIZE)
        self.display_surface.set_clip(grid_rect)
        self.apple.draw(self.display_surface)
        self.snake.draw(self.display_surface, draw_progress)
        self.display_surface.set_clip(None)
        self.particles.draw(self.display_surface)
        
        cap_w = 200
        cap_h = 46
        cap_x = (SCREEN_WIDTH - cap_w) // 2
        cap_y = 20
        
        cap_surf = pg.Surface((cap_w, cap_h), pg.SRCALPHA)
        pg.draw.rect(cap_surf, (255, 255, 255, 180), (0, 0, cap_w, cap_h), border_radius=10)
        pg.draw.rect(cap_surf, (46, 150, 75), (0, 0, cap_w, cap_h), width=2, border_radius=10)
        self.display_surface.blit(cap_surf, (cap_x, cap_y))
        
        self.draw_text(f"{self.score}", 24, (34, 112, 56), SCREEN_WIDTH // 2, cap_y + 8, bold=True)
        
        self.screen.blit(self.display_surface, (0, 0))
        pg.display.flip()
        
    def draw_text(self, text, size, color, x, y, bold=False, shadow_offset=None):
        font = self.get_font(size)
        font.set_bold(bold)
        
        if shadow_offset:
            shadow_color = shadow_offset.get('color', (20, 50, 30))
            offset_val = shadow_offset.get('offset', 4)
            shadow_surface = font.render(text, True, shadow_color)
            shadow_rect = shadow_surface.get_rect()
            for dx in range(-offset_val, offset_val + 1):
                for dy in range(-offset_val, offset_val + 1):
                    if dx*dx + dy*dy <= offset_val*offset_val:
                        shadow_rect.midtop = (x + dx + 1, y + dy + 2)
                        self.display_surface.blit(shadow_surface, shadow_rect)
                        
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect()
        text_rect.midtop = (x, y)
        self.display_surface.blit(text_surface, text_rect)

    def get_font(self, size):
        if self.font_name:
            return pg.font.Font(self.font_name, size)
        return pg.font.SysFont('arial', size)
        
    def draw_medal(self, surface, center, rank):
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
        pg.draw.rect(self.display_surface, (240, 240, 240), (x, y, 22, 22), border_radius=4)
        pg.draw.rect(self.display_surface, (46, 150, 75), (x, y, 22, 22), width=1, border_radius=4)
        
        font = self.get_font(11)
        font.set_bold(True)
        ts = font.render(text, True, (46, 150, 75))
        tr = ts.get_rect()
        tr.center = (x + 11, y + 10)
        self.display_surface.blit(ts, tr)

    def show_start_screen(self):
        waiting = True
        pg.event.pump()
        
        temp_clouds = []
        for _ in range(5):
            temp_clouds.append({
                'x': random.randint(0, SCREEN_WIDTH),
                'y': random.randint(30, 200),
                'scale': random.uniform(0.6, 1.2),
                'speed': random.uniform(0.5, 1.2)
            })
            
        while waiting:
            self.clock.tick(FPS)
            
            self.display_surface.fill((SKY_COLOR))
            for y in range(SCREEN_HEIGHT):
                r = int(110 + (220 - 110) * (y / SCREEN_HEIGHT))
                g = int(190 + (240 - 190) * (y / SCREEN_HEIGHT))
                b = int(255 + (255 - 255) * (y / SCREEN_HEIGHT))
                pg.draw.line(self.display_surface, (r, g, b), (0, y), (SCREEN_WIDTH, y))
                
            for cloud in temp_clouds:
                cloud['x'] -= cloud['speed']
                if cloud['x'] < -100:
                    cloud['x'] = SCREEN_WIDTH + 20
                    cloud['y'] = random.randint(30, 200)
                
                cw = int(80 * cloud['scale'])
                ch = int(45 * cloud['scale'])
                cs = pg.Surface((cw, ch), pg.SRCALPHA)
                r1 = int(18 * cloud['scale'])
                r2 = int(24 * cloud['scale'])
                r3 = int(16 * cloud['scale'])
                pg.draw.circle(cs, CLOUD_COLOR, (r2, ch - r2), r2)
                pg.draw.circle(cs, CLOUD_COLOR, (cw - r3, ch - r3), r3)
                pg.draw.circle(cs, CLOUD_COLOR, (cw // 2, r1 + 4), r1)
                pg.draw.rect(cs, CLOUD_COLOR, (r2, ch - r2 * 2 + 6, cw - r2 - r3, r2 * 2 - 6))
                self.display_surface.blit(cs, (int(cloud['x']), int(cloud['y'])))
                
            pg.draw.circle(self.display_surface, (80, 180, 100), (90, SCREEN_HEIGHT + 40), 170)
            pg.draw.circle(self.display_surface, (80, 180, 100), (360, SCREEN_HEIGHT + 50), 190)
            pg.draw.circle(self.display_surface, (46, 150, 75), (225, SCREEN_HEIGHT + 70), 210)
            
            pg.draw.rect(self.display_surface, (34, 112, 56), (0, SCREEN_HEIGHT - 40, SCREEN_WIDTH, 40))
            pg.draw.rect(self.display_surface, (20, 80, 40), (0, SCREEN_HEIGHT - 40, SCREEN_WIDTH, 40), width=2)
            
            self.draw_text("GARDEN", 38, TEXT_COLOR, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4 - 65, bold=True, shadow_offset={'color': (20, 80, 45), 'offset': 4})
            self.draw_text("SNAKE", 48, (235, 60, 60), SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4 - 20, bold=True, shadow_offset={'color': (80, 20, 20), 'offset': 5})
            
            card_w = 340
            card_h = 180
            card_x = (SCREEN_WIDTH - card_w) // 2
            card_y = SCREEN_HEIGHT // 2 - 70
            
            card_surf = pg.Surface((card_w, card_h), pg.SRCALPHA)
            pg.draw.rect(card_surf, (255, 255, 255, 220), (0, 0, card_w, card_h), border_radius=10)
            pg.draw.rect(card_surf, (46, 150, 75, 150), (0, 0, card_w, card_h), width=2, border_radius=10)
            self.display_surface.blit(card_surf, (card_x, card_y))
            
            self.draw_text("HIGH SCORES", 18, (34, 112, 56), SCREEN_WIDTH // 2, card_y + 12, bold=True)
            
            for i, score_val in enumerate([f"{self.highscore} PTS", "---", "---"]):
                row_y = card_y + 45 + i * 40
                pg.draw.rect(self.display_surface, (240, 248, 240, 230), (card_x + 15, row_y, card_w - 30, 32), border_radius=6)
                self.draw_medal(self.display_surface, (card_x + 45, row_y + 16), i + 1)
                score_color = (34, 112, 56) if i == 0 else (100, 100, 100)
                self.draw_text(score_val, 16, score_color, card_x + 170, row_y + 7, bold=(i == 0))
                
            ctrl_w = 340
            ctrl_h = 50
            ctrl_x = (SCREEN_WIDTH - ctrl_w) // 2
            ctrl_y = card_y + card_h + 15
            
            ctrl_surf = pg.Surface((ctrl_w, ctrl_h), pg.SRCALPHA)
            pg.draw.rect(ctrl_surf, (255, 255, 255, 220), (0, 0, ctrl_w, ctrl_h), border_radius=8)
            pg.draw.rect(ctrl_surf, (46, 150, 75, 100), (0, 0, ctrl_w, ctrl_h), width=1, border_radius=8)
            self.display_surface.blit(ctrl_surf, (ctrl_x, ctrl_y))
            
            self.draw_key_icon("W", ctrl_x + 25, ctrl_y + 14)
            self.draw_key_icon("A", ctrl_x + 49, ctrl_y + 14)
            self.draw_key_icon("S", ctrl_x + 73, ctrl_y + 14)
            self.draw_key_icon("D", ctrl_x + 97, ctrl_y + 14)
            self.draw_text("Use WASD or Arrows", 13, (34, 112, 56), ctrl_x + 225, ctrl_y + 16, bold=True)
            
            btn_w = 260
            btn_h = 48
            btn_x = (SCREEN_WIDTH - btn_w) // 2
            btn_y = SCREEN_HEIGHT * 13 // 16
            
            pulse = int(127 + 128 * abs(pg.time.get_ticks() / 300.0 % 2.0 - 1.0))
            pulse = max(60, min(255, pulse))
            btn_color = (int(46 * (pulse / 255.0)), int(150 * (pulse / 255.0)), int(75 * (pulse / 255.0)))
            
            btn_surf = pg.Surface((btn_w, btn_h), pg.SRCALPHA)
            pg.draw.rect(btn_surf, (255, 255, 255, 240), (0, 0, btn_w, btn_h), border_radius=14)
            pg.draw.rect(btn_surf, btn_color, (0, 0, btn_w, btn_h), width=2, border_radius=14)
            self.display_surface.blit(btn_surf, (btn_x, btn_y))
            
            self.draw_text("PRESS ENTER/SPACE", 14, (34, 112, 56), btn_x + btn_w//2, btn_y + 9, bold=True)
            self.draw_text("TO START HARVEST!", 14, (34, 112, 56), btn_x + btn_w//2, btn_y + 25, bold=True)
            
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
            
            pg.draw.rect(self.display_surface, (40, 100, 45), (GRID_OFFSET_X - 3, GRID_OFFSET_Y - 3, GRID_SIZE * GRID_TILE_SIZE + 6, GRID_SIZE * GRID_TILE_SIZE + 6), width=3, border_radius=4)
            for x in range(GRID_SIZE):
                for y in range(GRID_SIZE):
                    px = GRID_OFFSET_X + x * GRID_TILE_SIZE
                    py = GRID_OFFSET_Y + y * GRID_TILE_SIZE
                    tile_color = GRASS_LIGHT if (x + y) % 2 == 0 else GRASS_DARK
                    pg.draw.rect(self.display_surface, tile_color, (px, py, GRID_TILE_SIZE, GRID_TILE_SIZE))
                    
            grid_rect = pg.Rect(GRID_OFFSET_X, GRID_OFFSET_Y, GRID_SIZE * GRID_TILE_SIZE, GRID_SIZE * GRID_TILE_SIZE)
            self.display_surface.set_clip(grid_rect)
            self.apple.draw(self.display_surface)
            self.snake.draw(self.display_surface, self.final_draw_progress)
            self.display_surface.set_clip(None)
            
            title = "YOU WIN!" if self.won else "GAME OVER"
            title_color = (46, 150, 75) if self.won else (230, 70, 70)
            shadow_color = (20, 80, 45) if self.won else (100, 30, 30)
            self.draw_text(title, 38, title_color, SCREEN_WIDTH // 2, 90, bold=True, shadow_offset={'color': shadow_color, 'offset': 4})
            
            card_w = 340
            card_h = 180
            card_x = (SCREEN_WIDTH - card_w) // 2
            card_y = SCREEN_HEIGHT // 2 - 70
            
            card_surf = pg.Surface((card_w, card_h), pg.SRCALPHA)
            pg.draw.rect(card_surf, (255, 255, 255, 220), (0, 0, card_w, card_h), border_radius=10)
            pg.draw.rect(card_surf, (46, 150, 75, 150), (0, 0, card_w, card_h), width=2, border_radius=10)
            self.display_surface.blit(card_surf, (card_x, card_y))
            
            row1_y = card_y + 45
            pg.draw.rect(self.display_surface, (240, 248, 240, 230), (card_x + 15, row1_y, card_w - 30, 32), border_radius=6)
            self.draw_medal(self.display_surface, (card_x + 45, row1_y + 16), 1)
            self.draw_text(f"HIGH RECORD: {self.highscore} PTS", 14, (34, 112, 56), card_x + 180, row1_y + 8, bold=True)
            
            row2_y = card_y + 95
            pg.draw.rect(self.display_surface, (240, 248, 240, 230), (card_x + 15, row2_y, card_w - 30, 48), border_radius=6)
            self.draw_text("FINAL SCORE", 13, (100, 100, 100), card_x + 170, row2_y + 4)
            self.draw_text(f"{self.score} PTS", 18, (46, 150, 75), card_x + 170, row2_y + 20, bold=True)
            
            btn_w = 260
            btn_h = 48
            btn_x = (SCREEN_WIDTH - btn_w) // 2
            btn_y = SCREEN_HEIGHT * 13 // 16
            
            pulse = int(127 + 128 * abs(pg.time.get_ticks() / 300.0 % 2.0 - 1.0))
            pulse = max(60, min(255, pulse))
            btn_color = (int(46 * (pulse / 255.0)), int(150 * (pulse / 255.0)), int(75 * (pulse / 255.0)))
            
            btn_surf = pg.Surface((btn_w, btn_h), pg.SRCALPHA)
            pg.draw.rect(btn_surf, (255, 255, 255, 240), (0, 0, btn_w, btn_h), border_radius=14)
            pg.draw.rect(btn_surf, btn_color, (0, 0, btn_w, btn_h), width=2, border_radius=14)
            self.display_surface.blit(btn_surf, (btn_x, btn_y))
            
            self.draw_text("PRESS ENTER/SPACE", 14, (34, 112, 56), btn_x + btn_w//2, btn_y + 9, bold=True)
            self.draw_text("TO TRY AGAIN", 14, (34, 112, 56), btn_x + btn_w//2, btn_y + 25, bold=True)
            
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
