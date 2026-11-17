"""Constantes compartidas por cliente y servidor. Mensajes JSON delimitados por LF."""
from __future__ import annotations

HOST = '0.0.0.0'
PORT = 8765
TILE = 32
GRID_W, GRID_H = 28, 18
WORLD_W, WORLD_H = GRID_W * TILE, GRID_H * TILE
FPS_SERVER = 20
MAX_PLAYERS = 4
MIN_PLAYERS = 2
MAX_MESSAGE_BYTES = 8192
GAME_FLOORS = 3


def dungeon_map(floor: int, mode: str = 'coop') -> list[str]:
    """Mapa determinista; el servidor decide las colisiones, el cliente lo dibuja."""
    import random
    r = random.Random(2349 + floor * 179 + (0 if mode in ('coop', 'solo') else 99))
    rows = [['.' for _ in range(GRID_W)] for __ in range(GRID_H)]
    for y in range(GRID_H):
        for x in range(GRID_W):
            if x in (0, GRID_W-1) or y in (0, GRID_H-1):
                rows[y][x] = '#'
    for y in range(3, GRID_H - 2):
        for x in range(4, GRID_W - 3):
            # Obstáculos pequeños y dispersos, no se crea una pared que corte la sala.
            if (x + y) % 3 == 0 and r.random() < (0.15 if mode == 'pvp' else 0.22):
                rows[y][x] = 'X'
    # Despejar las zonas de aparición de todos los jugadores y monstruos.
    starts = [(3, 3), (3, 14), (24, 3), (24, 14), (18, 7), (21, 11), (16, 13)]
    for sx, sy in starts:
        for yy in range(max(1,sy-2), min(GRID_H-1,sy+3)):
            for xx in range(max(1,sx-2), min(GRID_W-1,sx+3)):
                rows[yy][xx] = '.'
    return [''.join(row) for row in rows]
