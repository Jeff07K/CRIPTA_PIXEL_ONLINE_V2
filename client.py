"""Cliente gráfico (pygame-ce) del juego multijugador Cripta Pixel Online.

Cada jugador abre este cliente en SU propio ordenador y conecta al mismo
servidor TCP. No hay simulación de colisiones ni de puntos en el cliente.
"""
from __future__ import annotations

import argparse
import json
import math
import queue
import socket
import threading
import time
from pathlib import Path

import pygame

from protocol import PORT, TILE, WORLD_W, WORLD_H, MAX_MESSAGE_BYTES

WIDTH, HEIGHT = 1100, 760
MAP_X, MAP_Y = 24, 116
COL = {
    'bg': (12, 18, 32), 'panel': (25, 35, 54), 'panel2': (34, 46, 67),
    'line': (79, 104, 125), 'text': (234, 242, 233), 'muted': (157, 177, 190),
    'gold': (255, 214, 109), 'green': (124, 226, 157), 'red': (246, 112, 113),
    'violet': (192, 154, 255), 'blue': (99, 197, 232),
}
ASSETS = Path(__file__).resolve().parent / 'assets'


class Network:
    def __init__(self):
        self.sock = None
        self.events = queue.Queue(maxsize=256)
        self.send_lock = threading.Lock()
        self.connected = False
        self.endpoint = None

    def connect(self, host: str, port: int):
        self.close()
        self.sock = socket.create_connection((host, port), timeout=4.0)
        self.sock.settimeout(None)
        self.connected = True
        self.endpoint = (host, port)
        threading.Thread(target=self._reader, args=(self.sock,), daemon=True).start()

    def _reader(self, sock):
        try:
            with sock.makefile('rb') as stream:
                while self.connected and self.sock is sock:
                    line = stream.readline(MAX_MESSAGE_BYTES * 4)
                    if not line:
                        break
                    try:
                        event = json.loads(line)
                    except (ValueError, UnicodeError):
                        continue
                    try:
                        self.events.put_nowait(event)
                    except queue.Full:
                        if event.get('type') != 'game_state':
                            try:
                                self.events.get_nowait()
                                self.events.put_nowait(event)
                            except queue.Empty:
                                pass
        except (OSError, ConnectionError):
            pass
        finally:
            if self.sock is sock and self.connected:
                self.connected = False
                self._notify({'type': 'disconnect', 'message': 'Se perdio la conexion con el servidor.'})

    def _notify(self, event: dict):
        try:
            self.events.put_nowait(event)
        except queue.Full:
            pass

    def send(self, msg: dict):
        if not self.connected or not self.sock:
            return
        try:
            with self.send_lock:
                self.sock.sendall(json.dumps(msg, ensure_ascii=False, separators=(',', ':')).encode() + b'\n')
        except OSError:
            self.connected = False
            self._notify({'type': 'disconnect', 'message': 'Se perdio la conexion.'})

    def close(self):
        self.connected = False
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        self.endpoint = None


class Game:
    def __init__(self, default_host: str = '127.0.0.1', default_port: int = PORT):
        pygame.init()
        pygame.display.set_caption('CRIPTA PIXEL ONLINE | Multiplayer Dungeon')
        pygame.display.set_icon(pygame.image.load(str(ASSETS / 'logo_slime.png')))
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.network = Network()
        self.running = True
        self.scene = 'auth'
        self.name = ''
        self.key = ''
        self.fields = {'username': '', 'password': '', 'server': f'{default_host}:{default_port}', 'code': ''}
        self.focus = 'username'
        self.buttons = []
        self.state = None
        self.room = {}
        self.results = None
        self.leaderboard = []
        self.rank_mode = 'solo'
        self.rank_day = ''
        self.notice, self.notice_at = 'Crea tu cuenta o inicia sesion.', time.monotonic()
        self.next_input = 0.0
        self.next_rank = 0.0
        self.attack_requested = False
        self.special_requested = False
        self.defend_requested = False
        self.special_choice = 'brutal'
        self.window_focused = True
        self.last_floor = None
        self.positions = {}
        self.animations = {}
        self.sprite_frames = {}
        self.special_visuals = {}
        self.special_effects = []
        self.effect_sequences = {}
        self.fonts = {}
        self.sprites = {}
        for name in ('hero', 'knight_rojo', 'knight_azul', 'knight_verde', 'knight_naranja', 'slime', 'bat', 'goblin', 'skeleton', 'flame', 'boss', 'ghost'):
            img = pygame.image.load(str(ASSETS / (name + '.png'))).convert_alpha()
            self.sprites[name] = pygame.transform.scale(img, (48, 48))
        self.sprites['boss'] = pygame.transform.scale(
            pygame.image.load(str(ASSETS / 'boss.png')).convert_alpha(), (66, 66))
        self.small_slime = pygame.transform.scale(self.sprites['slime'], (74, 74))
        # Las animaciones son recursos incluidos: no dependen de ningún editor durante la partida.
        for name in ('knight_rojo','knight_azul','knight_verde','knight_naranja',
                     'slime','bat','goblin','skeleton','flame','boss','ghost'):
            path = ASSETS / (name+'_sheet.png')
            if not path.is_file():
                continue
            image = pygame.image.load(str(path)).convert_alpha()
            is_knight = name.startswith('knight_')
            cell = 48 if is_knight else 40
            rows = 28 if is_knight else 16 if name in ('goblin','skeleton') else 3
            size = (64,64) if is_knight else (80,80) if name=='boss' else (54,54)
            self.sprite_frames[name] = [
                [pygame.transform.scale(image.subsurface((col*cell,row*cell,cell,cell)),size)
                 for col in range(4)] for row in range(rows)
            ]
        for name in ('brutal','distancia','veneno','paralisis'):
            path=ASSETS/f'fx_{name}_sheet.png'
            atlas=pygame.image.load(str(path)).convert_alpha()
            scale=(132,132) if name!='distancia' else (155,155)
            self.special_visuals[name]=[
                pygame.transform.scale(atlas.subsurface((96*i,0,96,96)),scale)
                for i in range(8)]

    def font(self, size=20, bold=False):
        key = (size, bold)
        if key not in self.fonts:
            self.fonts[key] = pygame.font.SysFont('dejavusansmono', size, bold=bold)
        return self.fonts[key]

    def text(self, content, x, y, size=19, color='text', bold=False, center=False):
        color = COL.get(color, color)
        image = self.font(size, bold).render(str(content), True, color)
        rect = image.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(image, rect)
        return rect

    def panel(self, rect, color='panel', border=True):
        r = pygame.Rect(rect)
        pygame.draw.rect(self.screen, COL.get(color, color), r, border_radius=7)
        if border:
            pygame.draw.rect(self.screen, COL['line'], r, 2, border_radius=7)
        return r

    def button(self, id, label, rect, accent='green', disabled=False):
        r = pygame.Rect(rect)
        hover = r.collidepoint(pygame.mouse.get_pos())
        if disabled:
            base = (61, 65, 78)
        elif hover:
            base = {'green': (38, 111, 90), 'violet': (82, 60, 118),
                    'red': (122, 54, 65), 'gold': (118, 90, 43), 'blue': (43, 88, 119)}.get(accent, COL['panel2'])
        else:
            base = COL['panel2']
        pygame.draw.rect(self.screen, (4, 9, 20), r.move(3, 4), border_radius=5)
        pygame.draw.rect(self.screen, base, r, border_radius=5)
        pygame.draw.rect(self.screen, COL[accent] if not disabled else COL['muted'], r, 2, border_radius=5)
        self.text(label, r.centerx, r.centery, 19 if len(label) < 20 else 16,
                  'muted' if disabled else 'text', bold=True, center=True)
        if not disabled:
            self.buttons.append((id, r))

    def field(self, key, label, rect, hidden=False):
        r = pygame.Rect(rect)
        self.text(label, r.x, r.y-27, 17, 'muted')
        pygame.draw.rect(self.screen, (12, 22, 38), r, border_radius=5)
        pygame.draw.rect(self.screen, COL['gold'] if self.focus == key else COL['line'], r, 2, border_radius=5)
        value = self.fields[key]
        visible = '●' * len(value) if hidden else value
        limit = 30 if key == 'server' else 24
        if len(visible) > limit:
            visible = visible[-limit:]
        self.text(visible if visible else '...', r.x+13, r.y+12, 19,
                  'text' if value else 'muted')
        if self.focus == key and int(time.monotonic()*2) % 2:
            tw = self.font(19).size(visible)[0]
            pygame.draw.line(self.screen, COL['gold'], (r.x+14+tw, r.y+10),
                             (r.x+14+tw, r.y+r.h-10), 2)
        self.buttons.append(('field:' + key, r))

    def background(self):
        self.screen.fill(COL['bg'])
        t = time.monotonic()
        for y in range(0, HEIGHT, 40):
            for x in range(0, WIDTH, 40):
                if (x*17+y*31) % 7 in (0, 1):
                    pygame.draw.rect(self.screen, (23, 35, 51), (x+4, y+7, 2, 2))
        for i in range(13):
            x = int((i*97 + math.sin(t*0.25+i)*13) % WIDTH)
            y = int((i*107 + t * (5 + i%4)) % HEIGHT)
            pygame.draw.rect(self.screen, (40, 68, 75), (x, y, 3, 3))

    def notice_draw(self):
        if time.monotonic() - self.notice_at < 5.0:
            r = pygame.Rect(170, 704, 760, 39)
            self.panel(r, (38, 50, 63))
            self.text(self.notice[:83], r.centerx, r.centery, 16, 'gold', center=True)

    def toast(self, message):
        self.notice = message
        self.notice_at = time.monotonic()

    def auth(self):
        self.text('CRIPTA', WIDTH//2, 110, 80, 'gold', True, True)
        self.text('P I X E L   O N L I N E', WIDTH//2, 168, 27, 'violet', True, True)
        pygame.draw.line(self.screen, COL['line'], (195, 192), (905, 192), 2)
        self.screen.blit(self.small_slime, (155, 228))
        self.screen.blit(self.sprites['goblin'], (848, 230))
        self.panel((300, 230, 500, 444))
        self.text('ACCESO A LA AVENTURA', 550, 270, 24, 'text', True, True)
        self.field('username', 'Nombre de usuario', (345, 316, 410, 49))
        self.field('password', 'Contrasena', (345, 401, 410, 49), hidden=True)
        self.field('server', 'Servidor (IP:puerto)', (345, 485, 410, 49))
        self.button('login', 'INICIAR SESION', (345, 560, 199, 54))
        self.button('register', 'CREAR CUENTA', (555, 560, 200, 54), 'violet')
        self.text('Conecta desde otros computadores usando la IP del servidor.',
                  WIDTH//2, 660, 15, 'muted', center=True)

    def home(self):
        self.text('CRIPTA PIXEL ONLINE', WIDTH//2, 64, 42, 'gold', True, True)
        self.text(f'AVENTURERO: {self.name.upper()}', WIDTH//2, 112, 18, 'green', True, True)
        self.panel((125, 149, 850, 489))
        self.text('SELECCIONA UNO DE LOS TRES MODOS', 550, 174, 24, 'text', True, True)
        self.screen.blit(self.sprites['knight_rojo'], (186, 213))
        self.text('SOLITARIO', 290, 213, 20, 'gold', True)
        self.text('1 jugador | 3 pisos | jefe final | ranking individual', 290, 239, 15, 'muted')
        self.button('solo', 'JUGAR SOLO', (290, 264, 525, 45), 'gold')
        self.screen.blit(self.sprites['slime'], (186, 333))
        self.text('COOPERATIVO', 290, 334, 20, 'green', True)
        self.text('2-4 amigos | 3 pisos | ranking de equipo', 290, 361, 15, 'muted')
        self.button('coop', 'CREAR COOPERATIVO', (290, 385, 525, 45))
        self.screen.blit(self.sprites['skeleton'], (186, 450))
        self.text('PVP', 290, 451, 20, 'red', True)
        self.text('2-4 jugadores | arena | ranking de victorias', 290, 479, 15, 'muted')
        self.button('pvp', 'CREAR COMBATE PVP', (290, 505, 525, 45), 'red')
        descriptions={'brutal':'160% dano, cuesta 5 HP', 'distancia':'alcance doble, 75% dano',
                      'veneno':'25% HP actual/s durante 3 s', 'paralisis':'inmoviliza 3 segundos'}
        self.button('special_switch','Q ELEGIDO: '+self.special_choice.upper()+' | '+descriptions[self.special_choice]+'  (CAMBIAR)',(143, 591, 804, 43),'violet')
        self.field('code', 'Codigo de sala de tus amigos', (137, 658, 260, 47))
        self.button('join', 'UNIRSE', (412, 658, 130, 47), 'blue')
        self.button('ranking', 'RANKINGS', (557, 658, 153, 47), 'gold')
        self.button('rank_switch', 'CAMBIAR MODO', (722, 658, 219, 47), 'violet')

    def lobby(self):
        mode = self.room.get('mode', 'coop')
        names = self.room.get('players', [])
        self.text('SALA DE ESPERA', WIDTH//2, 100, 46, 'gold', True, True)
        self.panel((150, 165, 800, 484))
        self.text('CODIGO PARA INVITAR', 550, 205, 20, 'muted', True, True)
        self.text(self.room.get('code', ''), 550, 267, 60, 'blue', True, True)
        self.text('COOPERATIVO · MAZMORRAS' if mode == 'coop' else 'COMBATE · PVP',
                  550, 324, 22, 'green' if mode == 'coop' else 'red', True, True)
        self.text(f'JUGADORES {len(names)}/4 - MINIMO 2', 550, 374, 19, 'muted', center=True)
        for i, name in enumerate(names):
            x = 240 + (i%2) * 340
            y = 422 + (i//2) * 73
            self.panel((x, y, 310, 56), 'panel2')
            color = (self.room.get('loadouts') or [{}]*len(names))[i].get('color','rojo')
            self.screen.blit(pygame.transform.scale(self.sprites['knight_'+color], (43,43)), (x+6, y+6))
            self.text(name[:17], x+58, y+13, 18, 'text', True)
        host = self.room.get('host') == self.name
        self.button('start', 'INICIAR PARTIDA' if host else 'ESPERANDO AL ANFITRION',
                    (333, 576, 434, 56), disabled=(not host or len(names) < 2))
        self.button('special_switch', 'ESPECIAL: '+self.special_choice.upper()+' ↻', (174, 669, 370, 49), 'violet')
        self.button('leave', 'SALIR DE LA SALA', (565, 669, 360, 49), 'red')

    def ranking(self):
        self.text('RANKING '+{'solo':'SOLITARIO','coop':'COOPERATIVO','pvp':'PVP'}[self.rank_mode], WIDTH//2, 99, 40, 'gold', True, True)
        self.text(f'Fecha: {self.rank_day or "consultando..."}  |  Zona: America/Bogota',
                  WIDTH//2, 150, 18, 'muted', center=True)
        self.panel((115, 199, 870, 438))
        self.text('POS', 150, 236, 19, 'blue', True)
        self.text('JUGADOR', 250, 236, 19, 'blue', True)
        self.text('PUNTOS', 540, 236, 19, 'blue', True)
        self.text('VICTORIAS', 710, 236, 19, 'blue', True)
        pygame.draw.line(self.screen, COL['line'], (143, 268), (960, 268), 2)
        if not self.leaderboard:
            self.text('Aun no hay partidas terminadas hoy.', WIDTH//2, 410, 23, 'muted', center=True)
        for i, row in enumerate(self.leaderboard[:10]):
            y = 283 + i*31
            tone = 'gold' if i == 0 else 'text'
            self.text(f'{i+1:02d}', 155, y, 17, tone, True)
            self.text(row['name'][:17], 250, y, 17, tone)
            self.text(f"{row['points']:,}", 542, y, 17, 'green', True)
            self.text(str(row['wins']), 751, y, 17, 'violet', True)
        self.button('rank_switch', 'CAMBIAR MODO', (209, 661, 217, 50), 'violet')
        self.button('refresh_rank', 'ACTUALIZAR', (438, 661, 217, 50), 'blue')
        self.button('back', 'VOLVER', (665, 661, 217, 50), 'red')

    def tiles(self, state):
        floor = state['floor']
        mode = state['mode']
        palettes = [
            ((57, 76, 57), (66, 88, 65), (92, 118, 71), (55, 61, 68), (98, 111, 102)),
            ((64, 99, 121), (74, 117, 139), (123, 186, 194), (49, 73, 93), (104, 151, 179)),
            ((104, 55, 44), (117, 61, 46), (231, 98, 48), (68, 40, 49), (146, 78, 58)),
        ]
        base, alt, detail, wall, rock = palettes[min(floor-1, 2)]
        if mode == 'pvp':
            base, alt, detail, wall, rock = ((62, 64, 78), (70, 74, 92), (117, 104, 132), (46, 44, 62), (100, 94, 110))
        rows = state['map']
        for y, row in enumerate(rows):
            for x, cell in enumerate(row):
                xx, yy = MAP_X + x*TILE, MAP_Y + y*TILE
                rr = pygame.Rect(xx, yy, TILE, TILE)
                if cell == '#':
                    pygame.draw.rect(self.screen, wall, rr)
                    pygame.draw.rect(self.screen, (30, 37, 46), (xx, yy, TILE, 3))
                    pygame.draw.line(self.screen, detail, (xx+3, yy+9), (xx+27, yy+9), 1)
                    pygame.draw.line(self.screen, (29,32,43), (xx+15+(y%2)*6, yy+9), (xx+15+(y%2)*6, yy+31), 2)
                    pygame.draw.line(self.screen, (34,39,50), (xx+2, yy+27), (xx+29, yy+27), 2)
                else:
                    pygame.draw.rect(self.screen, alt if ((x*7+y*19+floor)%7 == 0) else base, rr)
                    if (x*11+y*13)%7 == 0:
                        pygame.draw.rect(self.screen, detail, (xx+6, yy+8, 3, 3))
                        pygame.draw.rect(self.screen, (34, 57, 58), (xx+22, yy+21, 4, 2))
                    if cell == 'X':
                        pygame.draw.rect(self.screen, (26, 36, 43), (xx+3, yy+8, 27, 21))
                        pygame.draw.rect(self.screen, rock, (xx+5, yy+3, 22, 23))
                        pygame.draw.rect(self.screen, detail, (xx+7, yy+5, 15, 5))
                        pygame.draw.rect(self.screen, wall, (xx+18, yy+14, 8, 9))
                    if floor == 3 and mode == 'coop' and (x*23+y*19)%17 == 0:
                        pygame.draw.rect(self.screen, (240, 101, 34), (xx+9, yy+28, 15, 4))
        # Antorchas animadas en el muro superior.
        t = time.monotonic()
        for x in (4, 10, 17, 23):
            xx, yy = MAP_X + x*TILE, MAP_Y
            pygame.draw.rect(self.screen, (122, 93, 60), (xx+13, yy+18, 6, 13))
            pygame.draw.rect(self.screen, (255, 164, 44), (xx+10, yy+10+int(t*7)%3, 12, 13))
            pygame.draw.rect(self.screen, (255, 225, 105), (xx+14, yy+13, 5, 7))

    def lerp_position(self, key: str, x: float, y: float, dt_secs: float):
        if key not in self.positions or math.dist(self.positions[key], (x,y)) > 130:
            self.positions[key] = (x,y)
        else:
            ox, oy = self.positions[key]
            a = min(1.0, dt_secs * 20)
            self.positions[key] = (ox+(x-ox)*a, oy+(y-oy)*a)
        return self.positions[key]

    def animation_frame(self, key, obj, is_player, sprite_name):
        frames = self.sprite_frames.get(sprite_name)
        if not frames:
            return self.sprites.get(sprite_name, self.sprites['hero'])
        now = time.monotonic()
        a = self.animations.get(key)
        if a is None:
            a = {'state':'idle', 'since':now, 'until':0.0, 'action':'',
                 'attack_seq':obj.get('attack_seq',0), 'special_seq':obj.get('special_seq',0),
                 'hurt_seq':obj.get('hurt_seq',0), 'block_seq':obj.get('block_seq',0)}
            self.animations[key] = a
        for remote, state, length in (('special_seq','special',.35), ('attack_seq','attack',.24),
                                      ('hurt_seq','hurt',.18), ('block_seq','block',.18)):
            new = obj.get(remote, 0)
            if new != a[remote]:
                a[remote] = new
                if state != 'block' or obj.get('blocking'):
                    a['action'] = state
                    a['until'] = now + length
        if is_player:
            desired = ('dead' if obj['hp'] <= 0 else 'block' if obj.get('blocking') else
                       'special' if obj.get('special_fx') else 'attack' if obj.get('swing') else
                       'hurt' if obj.get('hurt') else 'walk' if obj.get('moving') else 'idle')
        else:
            desired = ('hurt' if obj.get('hurt') else 'attack' if obj.get('attacking') else
                       'walk' if obj.get('moving') else 'idle')
        if a['until'] > now and desired not in ('dead','block'):
            desired = a['action']
            if not is_player and desired in ('special','block'):
                desired = 'hurt'
        if desired != a['state']:
            a['state'] = desired
            a['since'] = now
        elapsed = max(0,now-a['since'])
        if desired == 'walk': index = int(elapsed*(9 if is_player else 8))%4
        elif desired == 'idle': index = int(elapsed*2.6)%4
        elif desired in ('attack','special','hurt'): index = min(3,int(elapsed*15))
        elif desired == 'block': index = int(elapsed*6)%4
        else:index = 2
        if is_player:
            states = ('idle','walk','attack','special','block','hurt','dead')
            dirs = {'down':0,'left':1,'right':2,'up':3}
            row = states.index(desired)*4+dirs.get(obj.get('face'),0)
        elif sprite_name in ('goblin','skeleton'):
            dirs={'down':0,'left':1,'right':2,'up':3}
            row=('idle','walk','attack','hurt').index(desired)*4+dirs.get(obj.get('face'),0)
        else:
            row = 2 if desired in ('hurt','attack') else 1 if desired=='walk' else 0
        return frames[row][index]

    def entities(self, state, dt_secs):
        ents = []
        present = set()
        for e in state['enemies']:
            key = 'e'+str(e['id'])
            present.add(key)
            x,y = self.lerp_position(key, e['x'], e['y'], dt_secs)
            ents.append(('enemy', y, x, y, e))
        for p in state['players']:
            key = 'p'+p['key']
            present.add(key)
            x,y = self.lerp_position(key, p['x'], p['y'], dt_secs)
            ents.append(('player', y, x, y, p))
        for key in list(self.positions):
            if key not in present:
                self.positions.pop(key)
                self.animations.pop(key,None)
        for typ, _, x, y, obj in sorted(ents, key=lambda a:a[1]):
            xx, yy = int(MAP_X+x), int(MAP_Y+y)
            sprite_name = obj['kind'] if typ == 'enemy' else 'knight_'+obj.get('color','rojo')
            img = self.animation_frame(('p'+obj['key']) if typ=='player' else ('e'+str(obj['id'])), obj,
                                       typ=='player', sprite_name)
            pygame.draw.ellipse(self.screen, (25, 30, 31), (xx-20, yy+9, 41, 11))
            if typ == 'player' and obj.get('invuln') and int(time.monotonic()*9)%2 == 0:
                img = img.copy();img.set_alpha(130)
            if typ == 'enemy' and sprite_name == 'boss':
                self.screen.blit(img,(xx-img.get_width()//2, yy-57))
            else:
                self.screen.blit(img,(xx-img.get_width()//2, yy-int(img.get_height()*.72)))
            if typ == 'player':
                if obj.get('blocking'):
                    pygame.draw.rect(self.screen, COL['blue'], (xx-26,yy-35,52,57), 4)
                if obj.get('paralyzed'):
                    pygame.draw.circle(self.screen, COL['blue'], (xx,yy), 32, 2)
                if obj.get('swing'):
                    pygame.draw.circle(self.screen, COL['gold'], (xx,yy), 50, 4)
                name = obj['name']
                self.text(name[:13], xx, yy-54, 13, 'gold' if obj['key'] == self.key else 'text', True, True)
                hp = obj['hp']
                pygame.draw.rect(self.screen, (26, 20, 28), (xx-20, yy-40, 40, 6))
                pygame.draw.rect(self.screen, COL['green'] if hp > 35 else COL['red'],
                                 (xx-20, yy-40, int(40*hp/100), 6))
                if obj['key'] == self.key:
                    pygame.draw.rect(self.screen, COL['gold'], (xx-25, yy+12, 50, 3))
            elif obj['hp'] < obj['max_hp']:
                if obj.get('poisoned'):
                    pygame.draw.circle(self.screen, COL['green'], (xx,yy), 27, 2)
                if obj.get('paralyzed'):
                    pygame.draw.circle(self.screen, COL['blue'], (xx,yy), 29, 2)
                pygame.draw.rect(self.screen, (32,27,31), (xx-16, yy-32, 32, 5))
                pygame.draw.rect(self.screen, COL['red'],
                                 (xx-16, yy-32, int(32*max(obj['hp'],0)/obj['max_hp']), 5))

    def draw_special_effects(self):
        now=time.monotonic()
        remaining=[]
        dirs={'right':(1,0,0),'left':(-1,0,180),'down':(0,1,90),'up':(0,-1,-90)}
        for start,x,y,face,name in self.special_effects:
            age=now-start
            if age>=.67:continue
            remaining.append((start,x,y,face,name))
            images=self.special_visuals.get(name)
            if not images:continue
            frame=min(7,int(age/.67*8));img=images[frame]
            dx,dy,angle=dirs.get(face,dirs['right'])
            radius=66 if name=='distancia' else 37 if name=='brutal' else 30
            img=pygame.transform.rotate(img,-angle)
            xx=MAP_X+x+dx*radius;yy=MAP_Y+y-9+dy*radius
            img.set_alpha(max(0,min(255,int((.67-age)/.18*255))))
            self.screen.blit(img,(int(xx-img.get_width()/2),int(yy-img.get_height()/2)))
        self.special_effects=remaining

    def gameplay(self, dt_secs):
        state = self.state
        if not state:
            self.text('Cargando mundo...', WIDTH//2, 350, 30, 'gold', center=True)
            return
        self.text('CRIPTA PIXEL', 27, 22, 36, 'gold', True)
        if state['mode'] != 'pvp':
            subtitle = f"{'SOLITARIO' if state['mode']=='solo' else 'COOPERATIVO'}     PISO {state['floor']}/{state['max_floors']}     ENEMIGOS {len(state['enemies'])}"
        else:
            subtitle = f"ARENA PVP     RESTANTE {state['remaining']}s     OBJETIVO: 5 BAJAS"
        self.text(subtitle, 28, 74, 18, 'muted', True)
        self.tiles(state)
        self.entities(state, dt_secs)
        self.draw_special_effects()
        if state.get('message'):
            self.panel((204, 121, 539, 43), (27, 36, 54))
            self.text(state['message'][:39], 473, 143, 18, 'gold', True, True)
        if state.get('transition'):
            self.text(f"Siguiente sala en {state['transition']}s", 473, 646, 22, 'gold', True, True)
        self.panel((941, 115, 141, 575))
        self.text('PARTY', 958, 139, 22, 'gold', True)
        for i,p in enumerate(state['players']):
            yy = 188 + i*97
            self.text(p['name'][:11], 954, yy, 14, 'green' if p['key'] == self.key else 'text', True)
            self.text(f"HP {p['hp']:03d}", 954, yy+23, 14, 'red' if p['hp'] < 34 else 'muted')
            self.text(f"PTS {p['score']}", 954, yy+43, 13, 'gold')
        me=next((p for p in state['players'] if p['key']==self.key),None)
        if me:
            self.text('Q '+me['special'].upper()[:11], 951, 567, 12, 'violet')
            self.text('Q '+str(me['special_ready_in'])+'s / E '+str(me['defense_ready_in'])+'s', 951, 586, 11, 'gold')
        pygame.draw.line(self.screen, COL['line'], (951, 608), (1072,608), 1)
        self.text('WASD /', 951, 613, 14, 'blue')
        self.text('FLECHAS', 951, 634, 14, 'blue')
        self.text('ESPACIO', 951, 657, 13, 'gold')
        self.text('WASD/flechas mover  |  ESPACIO atacar  |  Q especial  |  E defender  |  ESC salir',
                  29, 714, 17, 'muted')

    def results_screen(self):
        result = self.results or {}
        win = (result.get('winner') == 'EQUIPO' or result.get('winner') == self.name)
        self.text('¡VICTORIA!' if win else 'PARTIDA FINALIZADA', WIDTH//2, 103, 50,
                  'gold' if win else 'violet', True, True)
        self.text('Puntuaciones guardadas en el ranking de hoy.', WIDTH//2, 158, 19, 'muted', center=True)
        self.panel((165, 212, 770, 407))
        self.text('JUGADOR', 210, 256, 20, 'blue', True)
        self.text('PUNTOS', 560, 256, 20, 'blue', True)
        self.text('BAJAS', 740, 256, 20, 'blue', True)
        players = sorted(result.get('players', []), key=lambda p:p['score'], reverse=True)
        for i,p in enumerate(players):
            y = 318 + i*66
            self.text(p['name'][:17], 210, y, 20, 'gold' if p['wins'] else 'text', True)
            self.text(str(p['score']), 560, y, 21, 'green', True)
            self.text(str(p['kills']), 744, y, 21, 'violet', True)
        self.button('results_leave', 'VOLVER AL MENU', (420, 649, 260, 59), 'gold')

    def connect_for(self, action: str):
        address = self.fields['server'].strip()
        try:
            host, port_str = address.rsplit(':', 1)
            port = int(port_str)
            if not host or port <= 0 or port > 65535:
                raise ValueError('Puerto invalido')
            if not self.network.connected or self.network.endpoint != (host, port):
                self.network.connect(host, port)
            self.network.send({'type': action, 'username': self.fields['username'].strip(),
                               'password': self.fields['password']})
            self.toast('Consultando el servidor...')
        except (ValueError, OSError, TimeoutError) as exc:
            self.toast(f'No se pudo conectar: {str(exc)[:65]}')

    def on_button(self, id: str):
        if id.startswith('field:'):
            self.focus = id.split(':', 1)[1]
        elif id in ('login', 'register'):
            self.connect_for(id)
        elif id in ('solo', 'coop', 'pvp'):
            self.network.send({'type': 'create_room', 'mode': id, 'special':self.special_choice})
        elif id == 'special_switch':
            order=('brutal','distancia','veneno','paralisis')
            self.special_choice=order[(order.index(self.special_choice)+1)%len(order)]
            if self.scene == 'lobby':
                self.network.send({'type':'equip_special','special':self.special_choice})
        elif id == 'rank_switch':
            modes=('solo','coop','pvp');self.rank_mode=modes[(modes.index(self.rank_mode)+1)%3];self.leaderboard=[];self.toast('Ranking: '+self.rank_mode);
            if self.scene == 'ranking':self.request_ranking()
        elif id == 'join':
            self.network.send({'type': 'join_room', 'code': self.fields['code'].strip(), 'special':self.special_choice})
        elif id == 'start':
            self.network.send({'type': 'start_room'})
        elif id in ('leave', 'results_leave'):
            self.network.send({'type': 'leave_room'})
            self.scene = 'home'
            self.state, self.results = None, None
            self.positions.clear();self.animations.clear()
        elif id == 'ranking':
            self.scene = 'ranking'
            self.request_ranking()
        elif id == 'refresh_rank':
            self.request_ranking()
        elif id == 'back':
            self.scene = 'home'

    def request_ranking(self):
        self.network.send({'type': 'ranking', 'mode': self.rank_mode})
        self.next_rank = time.monotonic() + 15

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.WINDOWFOCUSLOST:
                self.window_focused = False
            elif event.type == pygame.WINDOWFOCUSGAINED:
                self.window_focused = True
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for id, rect in reversed(self.buttons):
                    if rect.collidepoint(event.pos):
                        self.on_button(id)
                        break
            elif event.type == pygame.KEYDOWN:
                if self.scene == 'game':
                    if event.key == pygame.K_SPACE:
                        self.attack_requested = True
                    elif event.key == pygame.K_q:
                        self.special_requested = True
                    elif event.key == pygame.K_e:
                        self.defend_requested = True
                    elif event.key == pygame.K_ESCAPE:
                        self.on_button('leave')
                elif self.scene in ('auth','home'):
                    eligible = ['username', 'password', 'server'] if self.scene == 'auth' else ['code']
                    if event.key == pygame.K_TAB:
                        self.focus = eligible[(eligible.index(self.focus)+1)%len(eligible)] if self.focus in eligible else eligible[0]
                    elif event.key == pygame.K_RETURN:
                        self.on_button('login' if self.scene == 'auth' else 'join')
                    elif event.key == pygame.K_BACKSPACE and self.focus in eligible:
                        self.fields[self.focus] = self.fields[self.focus][:-1]
                    elif event.unicode and event.unicode.isprintable() and self.focus in eligible:
                        limit = 64 if self.focus == 'password' else 42 if self.focus == 'server' else 18 if self.focus == 'username' else 6
                        if len(self.fields[self.focus]) < limit:
                            self.fields[self.focus] += event.unicode
                elif event.key == pygame.K_ESCAPE:
                    if self.scene == 'lobby':
                        self.on_button('leave')
                    elif self.scene == 'ranking':
                        self.scene = 'home'
                    elif self.scene == 'results':
                        self.on_button('results_leave')

    def consume_network(self):
        count = 0
        while count < 256:
            try:
                event = self.network.events.get_nowait()
            except queue.Empty:
                break
            count += 1
            kind = event.get('type')
            if kind in ('hello', 'error', 'register_result'):
                self.toast(event.get('message', ''))
            elif kind == 'login_result':
                self.toast(event.get('message', ''))
                if event.get('ok'):
                    self.name = event['name']
                    self.key = event['key']
                    self.scene = 'home'
                    self.focus = 'code'
                    self.request_ranking()
            elif kind == 'room_state':
                self.room = event
                for loadout in event.get('loadouts',[]):
                    if loadout.get('name') == self.name:
                        self.special_choice = loadout.get('special', self.special_choice)
                if event['status'] == 'lobby':
                    self.scene = 'lobby'
                elif event['status'] == 'playing':
                    self.scene = 'game'
            elif kind == 'game_state':
                if self.last_floor != event.get('floor'):
                    self.positions.clear();self.animations.clear();self.effect_sequences.clear();self.special_effects.clear()
                    self.last_floor = event.get('floor')
                for player in event.get('players', []):
                    key='p'+player['key']
                    sequence=player.get('special_seq',0)
                    prev=self.effect_sequences.get(key)
                    if prev is not None and sequence>prev and player.get('special'):
                        self.special_effects.append((time.monotonic(),player['x'],player['y'],
                                                     player.get('face','right'),player['special']))
                    self.effect_sequences[key]=sequence
                self.state = event
                if self.scene in ('lobby', 'game'):
                    self.scene = 'game'
            elif kind == 'game_over':
                self.results = event
                self.rank_mode = event.get('mode','solo')
                self.scene = 'results'
                self.positions.clear();self.animations.clear();self.effect_sequences.clear();self.special_effects.clear()
            elif kind == 'ranking':
                if event.get('mode') != self.rank_mode: continue
                self.leaderboard = event.get('items', [])
                self.rank_day = event.get('date', '')
            elif kind == 'left_room':
                self.room = {}
            elif kind == 'disconnect':
                self.toast(event.get('message', 'Sin conexion.'))
                self.scene = 'auth'
                self.network.close()
                self.key = ''
                self.name = ''

    def send_controls(self):
        if self.scene != 'game' or not self.network.connected:
            return
        now = time.monotonic()
        if now < self.next_input:
            return
        held = pygame.key.get_pressed()
        dx = int(bool(held[pygame.K_d] or held[pygame.K_RIGHT])) - int(bool(held[pygame.K_a] or held[pygame.K_LEFT]))
        dy = int(bool(held[pygame.K_s] or held[pygame.K_DOWN])) - int(bool(held[pygame.K_w] or held[pygame.K_UP]))
        if not self.window_focused:
            dx = dy = 0
        self.network.send({'type': 'input', 'dx': dx, 'dy': dy,
                           'attack': self.attack_requested and self.window_focused,
                           'special_attack': self.special_requested and self.window_focused,
                           'defend': self.defend_requested and self.window_focused})
        self.attack_requested = False
        self.special_requested = False
        self.defend_requested = False
        self.next_input = now + 0.05

    def draw(self, dt_secs):
        self.buttons = []
        self.background()
        if self.scene == 'auth':
            self.auth()
        elif self.scene == 'home':
            self.home()
        elif self.scene == 'lobby':
            self.lobby()
        elif self.scene == 'ranking':
            self.ranking()
        elif self.scene == 'game':
            self.gameplay(dt_secs)
        elif self.scene == 'results':
            self.results_screen()
        self.notice_draw()
        pygame.display.flip()

    def run(self):
        try:
            while self.running:
                delta = min(0.075, self.clock.tick(60)/1000)
                self.handle_events()
                self.consume_network()
                self.send_controls()
                if self.scene == 'ranking' and time.monotonic() > self.next_rank:
                    self.request_ranking()
                self.draw(delta)
        finally:
            self.network.close()
            pygame.quit()


def main():
    parser = argparse.ArgumentParser(description='Cliente de Cripta Pixel Online')
    parser.add_argument('--host', default='127.0.0.1', help='IP del servidor')
    parser.add_argument('--port', type=int, default=PORT)
    args = parser.parse_args()
    Game(args.host, args.port).run()


if __name__ == '__main__':
    main()
