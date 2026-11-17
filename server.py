"""Servidor autoritativo de Cripta Pixel Online (solo biblioteca estándar).

Almacena usuarios con PBKDF2 + sal, controla salas y colisiones y registra
partidas terminadas en SQLite. No confiar en coordenadas enviadas por clientes.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import datetime as dt
import hashlib
import hmac
import json
import math
import os
import queue
import random
import re
import secrets
import socket
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

from protocol import (PORT, HOST, TILE, GRID_W, GRID_H, FPS_SERVER,
                      MIN_PLAYERS, MAX_PLAYERS, MAX_MESSAGE_BYTES, GAME_FLOORS, dungeon_map)

try:
    BOGOTA = ZoneInfo('America/Bogota')
except Exception:
    BOGOTA = dt.timezone(dt.timedelta(hours=-5))

SPAWNS = [(3.5 * TILE, 3.5 * TILE), (3.5 * TILE, 14.5 * TILE),
          (24.5 * TILE, 3.5 * TILE), (24.5 * TILE, 14.5 * TILE)]
GAME_MODES = ('solo', 'coop', 'pvp')
SCARF_COLORS = ('rojo', 'azul', 'verde', 'naranja')
SPECIALS = ('brutal', 'distancia', 'veneno', 'paralisis')
SPECIAL_COOLDOWN = 6.0
DEFENSE_DURATION = 1.0
DEFENSE_COOLDOWN = 3.0
POISON_TICKS = 3  # 25 % de HP actual por segundo, durante tres segundos.
PARALYSIS_DURATION = 3.0
NORMAL_DAMAGE_PVE = 32
NORMAL_DAMAGE_PVP = 34


ENEMY_KINDS = {
    'slime': {'hp': 50, 'speed': 44, 'damage': 9, 'points': 65},
    'bat': {'hp': 35, 'speed': 82, 'damage': 7, 'points': 70},
    'goblin': {'hp': 75, 'speed': 55, 'damage': 13, 'points': 110},
    'skeleton': {'hp': 80, 'speed': 49, 'damage': 13, 'points': 120},
    'flame': {'hp': 95, 'speed': 67, 'damage': 17, 'points': 160},
    'boss': {'hp': 310, 'speed': 52, 'damage': 24, 'points': 450},
}


def today() -> str:
    return dt.datetime.now(BOGOTA).date().isoformat()


def dist(a, b) -> float:
    return math.hypot(a['x'] - b['x'], a['y'] - b['y'])


def solid(grid: list[str], x: float, y: float, radius: float = 10) -> bool:
    for px in (x-radius, x+radius):
        for py in (y-radius, y+radius):
            cx, cy = int(px // TILE), int(py // TILE)
            if not (0 <= cx < GRID_W and 0 <= cy < GRID_H):
                return True
            if grid[cy][cx] in ('#', 'X'):
                return True
    return False


def move_entity(entity: dict, dx: float, dy: float, grid: list[str], radius: float = 10):
    if not solid(grid, entity['x'] + dx, entity['y'], radius):
        entity['x'] += dx
    if not solid(grid, entity['x'], entity['y'] + dy, radius):
        entity['y'] += dy


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._init()

    @contextmanager
    def connection(self):
        """Transaccion que tambien cierra SQLite al terminar."""
        db = sqlite3.connect(self.path, timeout=10)
        db.execute('PRAGMA busy_timeout=10000')
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def _init(self):
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('''CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                salt BLOB NOT NULL,
                hash BLOB NOT NULL,
                created_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                mode TEXT NOT NULL,
                points INTEGER NOT NULL,
                wins INTEGER NOT NULL,
                kills INTEGER NOT NULL,
                floors INTEGER NOT NULL,
                day TEXT NOT NULL,
                played_at TEXT NOT NULL)''')
            db.execute('CREATE INDEX IF NOT EXISTS idx_results_day ON results(day, user_id)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_results_mode_day ON results(mode, day, user_id)')

    def register(self, username: str, password: str):
        if not re.fullmatch(r'[A-Za-z0-9_]{3,18}', username):
            return None, 'Usuario: 3-18 letras, numeros o _.'
        if not isinstance(password, str) or not 6 <= len(password) <= 72:
            return None, 'Contrasena: entre 6 y 72 caracteres.'
        salt = secrets.token_bytes(16)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 240_000)
        try:
            with self.connection() as db:
                cur = db.execute('INSERT INTO users(username,salt,hash,created_at) VALUES (?,?,?,?)',
                                 (username, salt, pwd_hash, dt.datetime.now(dt.timezone.utc).isoformat()))
                return cur.lastrowid, 'Cuenta creada correctamente.'
        except sqlite3.IntegrityError:
            return None, 'Ese usuario ya existe.'

    def login(self, username: str, password: str):
        with self.connection() as db:
            row = db.execute('SELECT id, username, salt, hash FROM users WHERE username=?',
                             (username,)).fetchone()
        if row is None:
            return None, None, 'Credenciales invalidas.'
        check = hashlib.pbkdf2_hmac('sha256', str(password).encode(), row[2], 240_000)
        if not hmac.compare_digest(check, row[3]):
            return None, None, 'Credenciales invalidas.'
        return row[0], row[1], 'Bienvenido.'

    def result(self, user_id: int, mode: str, points: int, wins: int, kills: int, floors: int):
        current = dt.datetime.now(BOGOTA)
        with self.connection() as db:
            db.execute('''INSERT INTO results(user_id,mode,points,wins,kills,floors,day,played_at)
                          VALUES (?,?,?,?,?,?,?,?)''',
                       (user_id, mode, int(points), int(wins), int(kills), int(floors),
                        current.date().isoformat(), current.isoformat()))

    def ranking(self, day: str | None = None, limit: int = 12, mode: str | None = None):
        """Clasificaciones independientes por modalidad y día (America/Bogota).

        mode=None queda reservado para compatibilidad con informes antiguos; la
        API pública pide explícitamente uno de solo/coop/pvp y nunca los mezcla.
        """
        if mode is not None and mode not in GAME_MODES:
            raise ValueError('Modo de clasificación no válido')
        day = day or today()
        mode_filter = ' AND r.mode=?' if mode else ''
        params = (day, mode, limit) if mode else (day, limit)
        with self.connection() as db:
            records = db.execute('''SELECT u.username, SUM(r.points) AS total,
                SUM(r.wins) AS victories, COUNT(*) AS games, MAX(r.points) AS best
                FROM results r JOIN users u ON u.id = r.user_id
                WHERE r.day=?''' + mode_filter + ''' GROUP BY r.user_id
                ORDER BY total DESC, victories DESC, best DESC, u.username ASC LIMIT ?''',
                params).fetchall()
        return [{'name': n, 'points': p, 'wins': w, 'games': g, 'best': b}
                for n, p, w, g, b in records]


class ClientPeer:
    def __init__(self, sock: socket.socket, address):
        self.sock, self.address = sock, address
        self.key = uuid.uuid4().hex[:12]
        self.user_id = None
        self.username = None
        self.room_id = None
        self.out = queue.Queue(maxsize=72)
        self.alive = True
        self.special = 'brutal'
        self.writer = threading.Thread(target=self._write, daemon=True)
        self.writer.start()

    def send(self, payload: dict):
        if not self.alive:
            return
        try:
            self.out.put_nowait(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode() + b'\n')
        except queue.Full:
            # Sustituye fotogramas antiguos, conserva mensajes críticos en la medida de lo posible.
            if payload.get('type') == 'game_state':
                return
            try:
                self.out.get_nowait()
                self.out.put_nowait(json.dumps(payload, ensure_ascii=False).encode() + b'\n')
            except queue.Empty:
                pass

    def _write(self):
        while self.alive:
            try:
                data = self.out.get(timeout=0.5)
                self.sock.sendall(data)
            except queue.Empty:
                continue
            except (OSError, ConnectionError):
                self.alive = False
                break

    def close(self):
        self.alive = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class Room:
    def __init__(self, code: str, mode: str, creator: ClientPeer):
        self.code = code
        self.mode = mode
        self.peers = [creator]
        self.host_key = creator.key
        self.status = 'lobby'
        self.grid = dungeon_map(1, mode)
        self.floor = 1
        self.players = {}
        self.enemies = []
        self.finished_at = 0.0
        self.next_floor_at = 0.0
        self.started_at = 0.0
        self.announcement = ''
        self.last_announcement_at = 0.0
        self._ids = 0

    def summary(self) -> dict:
        return {'type': 'room_state', 'code': self.code, 'mode': self.mode,
                'status': self.status, 'host': next((p.username for p in self.peers if p.key == self.host_key), '?'),
                'players': [p.username for p in self.peers],
                'loadouts': [{'name': p.username, 'color': SCARF_COLORS[i],
                              'special': getattr(p, 'special', 'brutal')}
                             for i, p in enumerate(self.peers)],
                'min_players': 1 if self.mode == 'solo' else MIN_PLAYERS,
                'max_players': 1 if self.mode == 'solo' else MAX_PLAYERS}

    def broadcast(self, payload: dict):
        for peer in self.peers:
            peer.send(payload)

    def start(self):
        self.status = 'playing'
        self.started_at = time.monotonic()
        self.players = {}
        for i, peer in enumerate(self.peers):
            x, y = SPAWNS[i]
            self.players[peer.key] = {
                'key': peer.key, 'name': peer.username, 'x': x, 'y': y,
                'hp': 100, 'score': 0, 'kills': 0, 'wins': 0,
                'color': SCARF_COLORS[i], 'special': getattr(peer, 'special', 'brutal'),
                'dx': 0, 'dy': 0, 'attack': False, 'special_attack': False,
                'defend': False, 'face': 'down',
                'cooldown': 0.0, 'special_cd': 0.0, 'defense_cd': 0.0,
                'block_until': 0.0, 'block_reduction': 0.0,
                'paralyzed_until': 0.0, 'poison_ticks': 0, 'poison_next': 0.0,
                'poison_source': None,
                'swing': 0.0, 'special_fx_until': 0.0, 'special_fx': '',
                'attack_seq': 0, 'special_seq': 0, 'block_seq': 0,
                'hurt_seq': 0, 'hurt_until': 0.0, 'moving': False,
                'respawn': 0.0, 'invuln': 0.0,
                'last_input': time.monotonic(),
            }
        self.floor = 1
        self.grid = dungeon_map(1, self.mode)
        self.enemies = []
        self.next_floor_at = 0.0
        self.announcement = ('¡EXPLORA LA CRIPTA EN SOLITARIO!' if self.mode == 'solo' else
                             '¡COMIENZA LA AVENTURA EN EQUIPO!' if self.mode == 'coop' else
                             '¡DUELO EN LA CRIPTA!')
        self.last_announcement_at = time.monotonic()
        if self.mode in ('solo', 'coop'):
            self.spawn_wave()

    def spawn_wave(self):
        self._ids = 0
        self.enemies = []
        rng = random.Random(344 + self.floor * 11 + len(self.peers))
        kinds = ['slime', 'bat', 'goblin', 'skeleton'] if self.floor == 1 else (
            ['slime', 'goblin', 'skeleton', 'bat', 'flame'] if self.floor == 2 else
            ['goblin', 'skeleton', 'flame', 'bat'])
        amount = 3 + self.floor * 2 + len(self.peers)
        if self.mode == 'solo':
            amount = max(3, amount - 2)  # reto equilibrado para una persona
        if self.floor == 3:
            amount -= 1
        attempts = 0
        while len(self.enemies) < amount and attempts < 500:
            attempts += 1
            x = rng.randrange(11, 26) * TILE + 16
            y = rng.randrange(2, 16) * TILE + 16
            if solid(self.grid, x, y, 11) or any(dist({'x': x, 'y': y}, p) < 155 for p in self.players.values()):
                continue
            kind = rng.choice(kinds)
            self._ids += 1
            self.enemies.append({'id': self._ids, 'kind': kind, 'x': float(x), 'y': float(y),
                                 'hp': ENEMY_KINDS[kind]['hp'], 'max_hp': ENEMY_KINDS[kind]['hp'],
                                 'hit_at': 0.0, 'attack_until': 0.0, 'attack_seq': 0,
                                 'hurt_seq': 0, 'hurt_until': 0.0, 'moving': False, 'face': 'down',
                                 'paralyzed_until': 0.0, 'poison_ticks': 0, 'poison_next': 0.0, 'poison_source': None})
        if self.floor == 3:
            bx, by = 22.5 * TILE, 8.5 * TILE
            if solid(self.grid, bx, by, 13):
                bx, by = 19.5 * TILE, 8.5 * TILE
            self._ids += 1
            self.enemies.append({'id': self._ids, 'kind': 'boss', 'x': bx, 'y': by,
                                 'hp': 310, 'max_hp': 310, 'hit_at': 0.0, 'attack_until': 0.0, 'attack_seq': 0,
                                 'hurt_seq': 0, 'hurt_until': 0.0, 'moving': False, 'face': 'down',
                                 'paralyzed_until': 0.0, 'poison_ticks': 0, 'poison_next': 0.0, 'poison_source': None})

    def snapshot(self) -> dict:
        now = time.monotonic()
        players = []
        for p in self.players.values():
            players.append({'key': p['key'], 'name': p['name'],
                'x': round(p['x'], 1), 'y': round(p['y'], 1), 'hp': p['hp'],
                'score': p['score'], 'kills': p['kills'], 'face': p['face'],
                'color': p['color'], 'special': p['special'],
                'special_ready_in': round(max(0.0, p['special_cd']-now), 1),
                'defense_ready_in': round(max(0.0, p['defense_cd']-now), 1),
                'blocking': p['block_until'] > now,
                'block_reduction': round(p['block_reduction']*100, 1) if p['block_until'] > now else 0,
                'paralyzed': p['paralyzed_until'] > now,
                'poisoned': p['poison_ticks'] > 0, 'moving': p['moving'],
                'attack_seq': p['attack_seq'], 'special_seq': p['special_seq'],
                'block_seq': p['block_seq'], 'hurt_seq': p['hurt_seq'],
                'hurt': p['hurt_until'] > now,
                'special_fx': p['special_fx'] if p['special_fx_until'] > now else '',
                'swing': p['swing'] > now, 'invuln': p['invuln'] > now})
        return {'type': 'game_state', 'code': self.code, 'mode': self.mode,
                'status': self.status, 'floor': self.floor, 'max_floors': GAME_FLOORS,
                'map': self.grid, 'players': players,
                'enemies': [{'id': e['id'], 'kind': e['kind'], 'x': round(e['x'], 1),
                             'y': round(e['y'], 1), 'hp': e['hp'], 'max_hp': e['max_hp'],
                             'poisoned': e['poison_ticks'] > 0,
                             'paralyzed': e['paralyzed_until'] > now,
                             'face': e['face'], 'moving': e['moving'],
                             'attack_seq': e['attack_seq'], 'attacking': e['attack_until'] > now,
                             'hurt_seq': e['hurt_seq'], 'hurt': e['hurt_until'] > now}
                            for e in self.enemies],
                'message': self.announcement if now - self.last_announcement_at < 2.8 else '',
                'remaining': max(0, round(180 - (now - self.started_at))) if self.mode == 'pvp' else None,
                'transition': max(0, round(self.next_floor_at - now, 1)) if self.next_floor_at else 0}

    @staticmethod
    def _round_damage(value: float) -> int:
        return max(1, int(value + 0.5))

    def _damage_player(self, victim: dict, damage: int, attacker: dict | None, now: float,
                       dot: bool = False) -> int:
        if victim['hp'] <= 0:
            return 0
        actual = int(damage)
        # La defensa protege de golpes directos; no detiene el veneno ya aplicado.
        if not dot and now < victim['block_until']:
            reduction = random.uniform(.005, .90)
            victim['block_reduction'] = reduction
            actual = self._round_damage(actual * (1.0 - reduction))
        victim['hp'] = max(0, victim['hp'] - actual)
        if actual > 0:
            victim['hurt_seq'] = victim.get('hurt_seq', 0) + 1
            victim['hurt_until'] = now + 0.19
        if victim['hp'] == 0:
            victim['poison_ticks'] = 0
            if self.mode == 'pvp':
                victim['respawn'] = now + 2.4
                if attacker is not None and attacker['key'] != victim['key']:
                    attacker['kills'] += 1
                    attacker['score'] += 140
                    self.announcement = f"{attacker['name']} derribó a {victim['name']}"
                    self.last_announcement_at = now
        return actual

    def _defend(self, p: dict, now: float):
        if p['hp'] <= 0 or now < p['defense_cd']:
            return
        p['block_until'] = now + DEFENSE_DURATION
        p['defense_cd'] = now + DEFENSE_COOLDOWN
        p['block_reduction'] = 0.0
        p['block_seq'] += 1

    def _apply_poison(self, victim: dict, source_key: str, now: float):
        # Un segundo veneno reemplaza al anterior; no se apilan efectos.
        victim['poison_ticks'] = POISON_TICKS
        victim['poison_next'] = now + 1.0
        victim['poison_source'] = source_key

    def _damage_enemy(self, e: dict, amount: int, attacker: dict):
        if e['hp'] <= 0:
            return
        e['hp'] = max(0, e['hp']-amount)
        if amount > 0:
            e['hurt_seq'] = e.get('hurt_seq', 0) + 1
            e['hurt_until'] = time.monotonic() + 0.19
        if e['hp'] == 0:
            attacker['score'] += ENEMY_KINDS[e['kind']]['points']
            attacker['kills'] += 1
            e['poison_ticks'] = 0

    def _attack(self, p: dict, now: float, special: bool = False):
        if p['hp'] <= 0:
            return
        if special:
            if now < p['special_cd']:
                return
            p['special_cd'] = now + SPECIAL_COOLDOWN
            kind = p['special']
            p['special_fx'] = kind
            p['special_fx_until'] = now + 0.35
            p['special_seq'] += 1
            if kind == 'brutal':
                # El coste existe aunque el ataque no alcance un blanco.
                self._damage_player(p, 5, None, now, dot=True)
                if p['hp'] == 0:
                    return
        else:
            if now < p['cooldown']:
                return
            p['cooldown'] = now + 0.44
            p['attack_seq'] += 1
            kind = 'normal'
        p['swing'] = now + 0.20
        normal = NORMAL_DAMAGE_PVP if self.mode == 'pvp' else NORMAL_DAMAGE_PVE
        damage = (self._round_damage(normal * 1.6) if kind == 'brutal' else
                  self._round_damage(normal * .75) if kind == 'distancia' else normal)
        if self.mode in ('solo', 'coop'):
            for e in self.enemies:
                if e['hp'] <= 0:
                    continue
                base_range = 70 if e['kind'] == 'boss' else 60
                radius = base_range * (2 if kind == 'distancia' else 1)
                if dist(p, e) > radius:
                    continue
                self._damage_enemy(e, damage, p)
                if e['hp'] > 0 and kind == 'veneno':
                    self._apply_poison(e, p['key'], now)
                if e['hp'] > 0 and kind == 'paralisis':
                    e['paralyzed_until'] = max(e['paralyzed_until'], now+PARALYSIS_DURATION)
            self.enemies = [e for e in self.enemies if e['hp'] > 0]
        else:
            for victim in self.players.values():
                if victim['key'] == p['key'] or victim['hp'] <= 0 or now < victim['invuln']:
                    continue
                if dist(p, victim) > 62*(2 if kind == 'distancia' else 1):
                    continue
                self._damage_player(victim, damage, p, now)
                if victim['hp'] > 0 and kind == 'veneno':
                    self._apply_poison(victim, p['key'], now)
                if victim['hp'] > 0 and kind == 'paralisis':
                    victim['paralyzed_until'] = max(victim['paralyzed_until'], now+PARALYSIS_DURATION)

    def _update_poison(self, now: float):
        if self.mode in ('solo', 'coop'):
            targets = self.enemies
        else:
            targets = self.players.values()
        for victim in targets:
            while victim['hp'] > 0 and victim['poison_ticks'] > 0 and now >= victim['poison_next']:
                damage = self._round_damage(victim['hp'] * .25)
                attacker = self.players.get(victim['poison_source'])
                if self.mode == 'pvp':
                    self._damage_player(victim, damage, attacker, now, dot=True)
                else:
                    victim['hp'] = max(0, victim['hp'] - damage)
                    victim['hurt_seq'] = victim.get('hurt_seq', 0) + 1
                    victim['hurt_until'] = now + 0.19
                    if victim['hp'] == 0 and attacker:
                        attacker['score'] += ENEMY_KINDS[victim['kind']]['points']
                        attacker['kills'] += 1
                victim['poison_ticks'] = max(0, victim['poison_ticks'] - 1)
                victim['poison_next'] += 1.0
        if self.mode in ('solo', 'coop'):
            self.enemies = [e for e in self.enemies if e['hp'] > 0]

    def _update_enemies(self, dt_secs: float, now: float):
        for e in self.enemies:
            targets = [p for p in self.players.values() if p['hp'] > 0]
            if not targets:
                return
            target = min(targets, key=lambda p: dist(e, p))
            prev_x, prev_y = e['x'], e['y']
            # Orientación por eje dominante: necesaria para animaciones reales en 4 direcciones.
            delta_x, delta_y = target['x']-e['x'], target['y']-e['y']
            e['face'] = (('right' if delta_x >= 0 else 'left') if abs(delta_x) >= abs(delta_y)
                         else ('down' if delta_y >= 0 else 'up'))
            distance = dist(e, target)
            kind = ENEMY_KINDS[e['kind']]
            if 19 < distance < 530 and now >= e['paralyzed_until']:
                diff_x = (target['x'] - e['x']) / distance
                diff_y = (target['y'] - e['y']) / distance
                move_entity(e, diff_x * kind['speed'] * dt_secs,
                            diff_y * kind['speed'] * dt_secs, self.grid, 11)
            e['moving'] = (abs(e['x']-prev_x) + abs(e['y']-prev_y)) > 0.04
            if distance < (29 if e['kind'] != 'boss' else 37) and now >= e['hit_at'] and now >= target['invuln']:
                self._damage_player(target, kind['damage'], None, now)
                target['invuln'] = now + 0.6
                e['hit_at'] = now + (0.85 if e['kind'] != 'boss' else 1.05)
                e['attack_seq'] += 1
                e['attack_until'] = now + 0.24

    def tick(self, dt_secs: float, now: float):
        if self.status != 'playing':
            return
        for p in self.players.values():
            if now - p['last_input'] > 0.9:  # evita parones por latencia HTTP en Internet
                p['dx'], p['dy'] = 0.0, 0.0
            if p['hp'] <= 0:
                if self.mode == 'pvp' and now >= p['respawn']:
                    idx = list(self.players).index(p['key'])
                    p['x'], p['y'] = SPAWNS[idx]
                    p['hp'] = 100
                    p['poison_ticks'] = 0
                    p['paralyzed_until'] = 0.0
                    p['block_until'] = 0.0
                    p['invuln'] = now + 1.5
                p['attack'] = p['special_attack'] = p['defend'] = False
                p['moving'] = False
                continue
            if p['defend']:
                self._defend(p, now)
                p['defend'] = False
            mx, my = p['dx'], p['dy']
            old_x, old_y = p['x'], p['y']
            mag = math.hypot(mx, my)
            if mag > 0 and now >= p['paralyzed_until']:
                mx, my = mx / mag, my / mag
                p['face'] = ('right' if mx > 0 else 'left') if abs(mx) > abs(my) else ('down' if my > 0 else 'up')
                move_entity(p, mx * 145 * dt_secs, my * 145 * dt_secs, self.grid, 10)
            # Solo animar caminata si realmente hubo desplazamiento (colision => idle).
            p['moving'] = (abs(p['x']-old_x) + abs(p['y']-old_y)) > 0.05
            if p['attack']:
                self._attack(p, now)
                p['attack'] = False
            if p['special_attack']:
                self._attack(p, now, special=True)
                p['special_attack'] = False
        self._update_poison(now)
        if self.mode in ('solo', 'coop'):
            self._update_enemies(dt_secs, now)
            if all(p['hp'] <= 0 for p in self.players.values()):
                return 'defeat'
            if not self.enemies and not self.next_floor_at:
                for p in self.players.values():
                    p['score'] += 160
                self.next_floor_at = now + 3.0
                self.announcement = f'¡PISO {self.floor} SUPERADO!'
                self.last_announcement_at = now
            if self.next_floor_at and now >= self.next_floor_at:
                if self.floor >= GAME_FLOORS:
                    return 'victory'
                self.floor += 1
                self.grid = dungeon_map(self.floor, self.mode)
                for i, p in enumerate(self.players.values()):
                    p['hp'] = min(100, max(35, p['hp']) + 35)
                    p['x'], p['y'] = SPAWNS[i]
                    p['invuln'] = now + 1.5
                    p['poison_ticks'] = 0
                    p['paralyzed_until'] = 0.0
                    p['block_until'] = 0.0
                self.spawn_wave()
                self.next_floor_at = 0.0
                self.announcement = f'¡PISO {self.floor} - NUEVOS ENEMIGOS!'
                self.last_announcement_at = now
        else:
            if any(p['kills'] >= 5 for p in self.players.values()) or now - self.started_at >= 180:
                return 'pvp_end'
        return None


class GameServer:
    def __init__(self, bind_host: str = HOST, port: int = PORT, db_path: str = 'cripta.db'):
        self.bind_host, self.port = bind_host, port
        # En Internet, Neon/PostgreSQL conserva cuentas y rankings entre reinicios.
        # En local, SQLite mantiene compatibilidad con todas las versiones previas.
        if os.environ.get('DATABASE_URL'):
            from db_postgres import PostgresDatabase
            self.db = PostgresDatabase(os.environ['DATABASE_URL'])
        else:
            self.db = Database(db_path)
        self.lock = threading.RLock()
        self.rooms: dict[str, Room] = {}
        self.peers: dict[str, ClientPeer] = {}
        self.running = False
        self.server_socket = None
        self.threads = []

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.bind_host, self.port))
        self.server_socket.listen(64)
        self.server_socket.settimeout(0.5)
        self.port = self.server_socket.getsockname()[1]
        self.running = True
        for target in (self._accept_loop, self._tick_loop):
            t = threading.Thread(target=target, daemon=True)
            t.start()
            self.threads.append(t)
        print(f'[CRIPTA] Servidor en {self.bind_host}:{self.port}. Ranking: America/Bogota. Ctrl+C para cerrar.', flush=True)

    def stop(self):
        self.running = False
        try:
            self.server_socket.close()
        except (OSError, AttributeError):
            pass
        with self.lock:
            for p in list(self.peers.values()):
                p.close()
        for t in self.threads:
            if t.is_alive():
                t.join(timeout=1.0)

    def _accept_loop(self):
        while self.running:
            try:
                sock, address = self.server_socket.accept()
                sock.settimeout(None)
            except socket.timeout:
                continue
            except OSError:
                break
            peer = ClientPeer(sock, address)
            with self.lock:
                self.peers[peer.key] = peer
            threading.Thread(target=self._client_loop, args=(peer,), daemon=True).start()

    def _client_loop(self, peer: ClientPeer):
        peer.send({'type': 'hello', 'message': 'Conectado a Cripta Pixel Online.'})
        try:
            with peer.sock.makefile('rb') as stream:
                while self.running and peer.alive:
                    try:
                        line = stream.readline(MAX_MESSAGE_BYTES + 1)
                    except socket.timeout:
                        continue
                    if not line or len(line) > MAX_MESSAGE_BYTES:
                        break
                    try:
                        obj = json.loads(line)
                        if not isinstance(obj, dict):
                            raise ValueError()
                        self._handle(peer, obj)
                    except (ValueError, TypeError, KeyError, OverflowError):
                        peer.send({'type': 'error', 'message': 'Mensaje invalido.'})
        except (OSError, ConnectionError):
            pass
        finally:
            with self.lock:
                self._leave_room(peer)
                self.peers.pop(peer.key, None)
            peer.close()

    def _send_error(self, peer: ClientPeer, message: str):
        peer.send({'type': 'error', 'message': message})

    def _handle(self, peer: ClientPeer, msg: dict):
        action = msg.get('type', '')
        if action in ('register', 'login'):
            if peer.user_id:
                self._send_error(peer, 'Ya iniciaste sesion.')
                return
            username = msg.get('username', '')
            password = msg.get('password', '')
            if not isinstance(username, str) or not isinstance(password, str) or len(username) > 32 or len(password) > 100:
                self._send_error(peer, 'Datos invalidos.')
                return
            if action == 'register':
                uid, message = self.db.register(username, password)
                peer.send({'type': 'register_result', 'ok': bool(uid), 'message': message})
                return
            uid, actual_name, message = self.db.login(username, password)
            if uid:
                with self.lock:
                    if any(p.user_id == uid for p in self.peers.values() if p is not peer):
                        uid, message = None, 'Esta cuenta ya esta conectada.'
                    else:
                        peer.user_id = uid
                        peer.username = actual_name
            peer.send({'type': 'login_result', 'ok': bool(uid), 'name': actual_name if uid else '',
                       'key': peer.key if uid else '', 'message': message})
            return
        if not peer.user_id:
            self._send_error(peer, 'Inicia sesion primero.')
            return
        if action == 'ranking':
            mode = msg.get('mode', 'solo')
            if mode not in GAME_MODES:
                self._send_error(peer, 'Modo de ranking inválido.')
                return
            peer.send({'type': 'ranking', 'date': today(), 'mode': mode,
                       'items': self.db.ranking(mode=mode)})
            return
        if action == 'input':
            with self.lock:
                room = self.rooms.get(peer.room_id)
                if room and room.status == 'playing' and peer.key in room.players:
                    p = room.players[peer.key]
                    p['last_input'] = time.monotonic()
                    for axis in ('dx', 'dy'):
                        value = msg.get(axis, 0)
                        if isinstance(value, (int, float)) and math.isfinite(value):
                            p[axis] = max(-1.0, min(1.0, float(value)))
                    if msg.get('attack') is True:
                        p['attack'] = True
                    if msg.get('special_attack') is True:
                        p['special_attack'] = True
                    if msg.get('defend') is True:
                        p['defend'] = True
            return
        with self.lock:
            if action == 'equip_special':
                special = msg.get('special')
                room = self.rooms.get(peer.room_id)
                if special not in SPECIALS:
                    self._send_error(peer, 'Especial no válido.')
                elif room and room.status != 'lobby':
                    self._send_error(peer, 'Solo puedes equipar antes de comenzar la partida.')
                else:
                    peer.special = special
                    if room:
                        room.broadcast(room.summary())
                    else:
                        peer.send({'type': 'loadout', 'special': special})
                return
            if action == 'create_room':
                mode = msg.get('mode')
                desired = msg.get('special', getattr(peer, 'special', 'brutal'))
                if desired not in SPECIALS:
                    self._send_error(peer, 'Especial no válido.')
                elif mode not in GAME_MODES:
                    self._send_error(peer, 'Modo invalido.')
                elif peer.room_id:
                    self._send_error(peer, 'Abandona tu sala actual primero.')
                else:
                    peer.special = desired
                    code = secrets.token_hex(3).upper()
                    while code in self.rooms:
                        code = secrets.token_hex(3).upper()
                    room = Room(code, mode, peer)
                    self.rooms[code] = room
                    peer.room_id = code
                    if mode == 'solo':
                        room.start()  # Solitario: sin sala de espera ni otros usuarios
                        peer.send(room.summary())
                        peer.send(room.snapshot())
                    else:
                        peer.send(room.summary())
            elif action == 'join_room':
                code = str(msg.get('code', '')).upper().strip()
                desired = msg.get('special', getattr(peer, 'special', 'brutal'))
                room = self.rooms.get(code)
                if desired not in SPECIALS:
                    self._send_error(peer, 'Especial no válido.')
                elif peer.room_id:
                    self._send_error(peer, 'Abandona tu sala actual primero.')
                elif not room:
                    self._send_error(peer, 'No existe esa sala.')
                elif room.mode == 'solo':
                    self._send_error(peer, 'El modo solitario no admite otros jugadores.')
                elif room.status != 'lobby':
                    self._send_error(peer, 'Esa partida ya ha comenzado.')
                elif len(room.peers) >= MAX_PLAYERS:
                    self._send_error(peer, 'La sala esta llena (4/4).')
                else:
                    peer.special = desired
                    room.peers.append(peer)
                    peer.room_id = code
                    room.broadcast(room.summary())
            elif action == 'start_room':
                room = self.rooms.get(peer.room_id)
                if not room or room.host_key != peer.key:
                    self._send_error(peer, 'Solo el anfitrion puede iniciar.')
                elif room.status != 'lobby':
                    self._send_error(peer, 'La partida ya empezo.')
                elif not (1 if room.mode == 'solo' else MIN_PLAYERS) <= len(room.peers) <= (1 if room.mode == 'solo' else MAX_PLAYERS):
                    self._send_error(peer, 'Necesitas entre 2 y 4 jugadores.')
                else:
                    room.start()
                    room.broadcast(room.summary())
                    room.broadcast(room.snapshot())
            elif action == 'leave_room':
                self._leave_room(peer)
                peer.send({'type': 'left_room'})
            else:
                self._send_error(peer, 'Accion desconocida.')

    def _leave_room(self, peer: ClientPeer):
        code = peer.room_id
        if not code or code not in self.rooms:
            peer.room_id = None
            return
        room = self.rooms[code]
        if peer in room.peers:
            room.peers.remove(peer)
        peer.room_id = None
        if room.status == 'playing':
            room.players.pop(peer.key, None)
            if len(room.peers) < (1 if room.mode == 'solo' else MIN_PLAYERS):
                # Si queda un solo jugador PvP, gana por abandono.
                winner = room.peers[0].key if room.mode == 'pvp' and room.peers else None
                self._finish(room, 'abandon', winner)
        if not room.peers:
            self.rooms.pop(code, None)
            return
        if room.host_key == peer.key:
            room.host_key = room.peers[0].key
        room.broadcast(room.summary())

    def _finish(self, room: Room, reason: str, winner_key: str | None = None):
        if room.status != 'playing':
            return
        if room.mode in ('solo', 'coop'):
            win = reason == 'victory'
            for p in room.players.values():
                if win:
                    p['score'] += 550
                    p['wins'] = 1
        else:
            if reason == 'pvp_end':
                scores = sorted(room.players.values(), key=lambda p: (p['kills'], p['score']), reverse=True)
                winner_key = scores[0]['key'] if scores and (len(scores) == 1 or scores[0]['kills'] > scores[1]['kills']) else None
            if winner_key in room.players:
                room.players[winner_key]['score'] += 550
                room.players[winner_key]['wins'] = 1
        room.status = 'finished'
        room.finished_at = time.monotonic()
        for peer in room.peers:
            player = room.players.get(peer.key)
            if not player:
                continue
            floors = room.floor if room.mode in ('solo', 'coop') else 0
            self.db.result(peer.user_id, room.mode, player['score'], player['wins'], player['kills'], floors)
        room.broadcast({'type': 'game_over', 'reason': reason, 'mode': room.mode,
                        'winner': room.players[winner_key]['name'] if winner_key and winner_key in room.players else
                                  ('EQUIPO' if room.mode == 'coop' and reason == 'victory' else
                                   (next(iter(room.players.values()))['name'] if room.mode == 'solo' and reason == 'victory' and room.players else '')),
                        'players': [{'name': p['name'], 'score': p['score'], 'kills': p['kills'], 'wins': p['wins']}
                                    for p in room.players.values()], 'date': today()})
        room.broadcast(room.summary())

    def _tick_loop(self):
        interval = 1 / FPS_SERVER
        previous = time.monotonic()
        while self.running:
            start = time.monotonic()
            delta = min(0.07, start - previous)
            previous = start
            with self.lock:
                for room in list(self.rooms.values()):
                    if room.status != 'playing':
                        continue
                    result = room.tick(delta, start)
                    if result:
                        self._finish(room, result)
                    else:
                        room.broadcast(room.snapshot())
            time.sleep(max(0.001, interval - (time.monotonic() - start)))


def main():
    parser = argparse.ArgumentParser(description='Servidor de Cripta Pixel Online')
    parser.add_argument('--host', default=HOST, help='IP de escucha (por defecto 0.0.0.0)')
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--db', default=str(Path(__file__).resolve().parent / 'cripta.db'))
    args = parser.parse_args()
    srv = GameServer(args.host, args.port, args.db)
    srv.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('\n[CRIPTA] Cerrando...')
    finally:
        srv.stop()


if __name__ == '__main__':
    main()
