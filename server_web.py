"""Pasarela HTTP para Cripta Pixel Online.

Todo el estado del juego, movimientos, combates, autenticacion y puntuacion
lo procesa GameServer (Python). Esta pasarela permite jugar desde navegadores
separados en la misma LAN, sin instalar dependencias en cada dispositivo.

Uso de clase: python server_web.py --host 0.0.0.0 --web-port 8080
Nota de seguridad: HTTP no cifra contrasenas; usar solo en LAN de confianza/VPN.
"""
from __future__ import annotations

import argparse
import collections
import json
import mimetypes
import os
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from protocol import PORT
from server import GameServer, today

ROOT = Path(__file__).resolve().parent
WEB = ROOT / 'web'
IMAGE_NAME = re.compile(r'^[a-z0-9_-]+\.png$')
MAX_BODY = 8192
SESSION_IDLE_SECONDS = 300


class BrowserPeer:
    """Cliente equivalente al TCP: misma API send y mismo estado de sesion."""

    def __init__(self):
        self.key = secrets.token_hex(12)
        self.token = secrets.token_urlsafe(32)
        self.user_id = None
        self.username = None
        self.special = 'brutal'
        self.room_id = None
        self.alive = True
        self.last_seen = time.monotonic()
        self._lock = threading.Lock()
        self._events = collections.deque(maxlen=80)
        self._last_snapshot = None

    def send(self, payload: dict):
        if not self.alive:
            return
        with self._lock:
            if payload.get('type') == 'game_state':
                self._last_snapshot = payload
            else:
                self._events.append(payload)

    def drain(self) -> list[dict]:
        with self._lock:
            events = list(self._events)
            self._events.clear()
            if self._last_snapshot is not None:
                events.append(self._last_snapshot)
                self._last_snapshot = None
            return events

    def close(self):
        self.alive = False


class BrowserGateway:
    def __init__(self, game: GameServer, host='0.0.0.0', port=8080):
        self.game = game
        self.host = host
        self.port = port
        self.sessions: dict[str, BrowserPeer] = {}
        self.httpd = None
        self._running = False
        self._threads = []

    def new_session(self) -> BrowserPeer:
        peer = BrowserPeer()
        with self.game.lock:
            self.sessions[peer.token] = peer
            self.game.peers[peer.key] = peer
        peer.send({'type':'hello','message':'Conectado al servidor multijugador.'})
        return peer

    def lookup(self, token: str):
        with self.game.lock:
            peer = self.sessions.get(token)
            if peer is not None and peer.alive:
                peer.last_seen = time.monotonic()
                return peer
            return None

    def dispose(self, token: str):
        with self.game.lock:
            peer = self.sessions.pop(token, None)
            if peer is None:
                return
            self.game._leave_room(peer)
            self.game.peers.pop(peer.key, None)
            peer.close()

    def _reap(self):
        while self._running:
            cutoff = time.monotonic() - SESSION_IDLE_SECONDS
            with self.game.lock:
                expired = [token for token, p in self.sessions.items() if p.last_seen < cutoff]
            for token in expired:
                self.dispose(token)
            time.sleep(2)

    def start(self):
        gateway = self
        class Handler(BaseHTTPRequestHandler):
            server_version = 'CriptaPixel/2.0'
            sys_version = ''

            def log_message(self, fmt, *args):
                # Evita registrar los tokens de sesion en URL o mensajes.
                pass

            def _reply(self, code, body: bytes, mime='application/json; charset=utf-8'):
                try:
                    self.send_response(code)
                    self.send_header('Content-Type', mime)
                    self.send_header('Content-Length', str(len(body)))
                    self.send_header('Cache-Control', 'no-store' if mime.startswith('application/json') else 'public, max-age=60')
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    self.send_header('X-Frame-Options', 'DENY')
                    self.send_header('Referrer-Policy', 'no-referrer')
                    self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'")
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return

            def _json(self, code, obj):
                self._reply(code, json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))

            def _read_data(self):
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not (0 < length <= MAX_BODY):
                        raise ValueError('Tamano no permitido')
                    data = json.loads(self.rfile.read(length))
                    if not isinstance(data, dict):
                        raise ValueError('Se requiere objeto JSON')
                    return data
                except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
                    return None

            def _session_token(self, payload):
                return str(payload.get('session', '')) if payload else ''

            def do_GET(self):
                url = urlsplit(self.path)
                if url.path == '/api/status':
                    with gateway.game.lock:
                        members = sum(p.user_id is not None for p in gateway.game.peers.values())
                        rooms = sum(room.status == 'playing' for room in gateway.game.rooms.values())
                    self._json(200, {'ok':True, 'online':members, 'playing_rooms':rooms, 'date':today()})
                    return
                if url.path == '/api/state':
                    token = parse_qs(url.query).get('session', [''])[0]
                    peer = gateway.lookup(token)
                    if not peer:
                        self._json(401, {'ok':False, 'error':'Sesion vencida'})
                        return
                    with gateway.game.lock:
                        room = gateway.game.rooms.get(peer.room_id)
                        room_data = room.summary() if room else None
                        game_data = room.snapshot() if room and room.status == 'playing' else None
                    self._json(200, {'ok':True, 'key':peer.key, 'name':peer.username,
                                     'room':room_data, 'game':game_data})
                    return
                if url.path == '/api/events':
                    token = parse_qs(url.query).get('session', [''])[0]
                    peer = gateway.lookup(token)
                    if not peer:
                        self._json(401, {'ok':False, 'error':'Sesion vencida. Vuelve a conectar.'})
                        return
                    self._json(200, {'ok':True, 'events':peer.drain()})
                    return
                # Servir solamente archivos conocidos, sin recorrer el filesystem.
                if url.path in ('/', '/index.html'):
                    path = WEB / 'index.html'
                elif url.path == '/app.js':
                    path = WEB / 'app.js'
                elif url.path == '/style.css':
                    path = WEB / 'style.css'
                elif url.path.startswith('/assets/') and IMAGE_NAME.fullmatch(url.path.split('/')[-1]):
                    path = ROOT / 'assets' / url.path.split('/')[-1]
                else:
                    self._json(404, {'ok':False, 'error':'No encontrado'})
                    return
                if not path.is_file():
                    self._json(404, {'ok':False, 'error':'Archivo no encontrado'})
                    return
                mime = mimetypes.guess_type(path)[0] or 'application/octet-stream'
                if mime.startswith('text/') or mime == 'application/javascript':
                    mime += '; charset=utf-8'
                self._reply(200, path.read_bytes(), mime)

            def do_POST(self):
                path = urlsplit(self.path).path
                if path not in ('/api/connect', '/api/action', '/api/disconnect'):
                    self._json(404, {'ok':False, 'error':'No encontrado'})
                    return
                data = self._read_data()
                if data is None:
                    self._json(400, {'ok':False, 'error':'JSON invalido o demasiado grande'})
                    return
                if path == '/api/connect':
                    peer = gateway.new_session()
                    self._json(200, {'ok':True, 'session':peer.token, 'key':peer.key})
                    return
                token = self._session_token(data)
                peer = gateway.lookup(token)
                if not peer:
                    self._json(401, {'ok':False, 'error':'Sesion vencida'})
                    return
                if path == '/api/disconnect':
                    gateway.dispose(token)
                    self._json(200, {'ok':True})
                    return
                action = data.get('action')
                if not isinstance(action, dict):
                    self._json(400, {'ok':False, 'error':'Accion invalida'})
                    return
                # El propio GameServer valida permisos/estado, no se aceptan
                # cambios de coordenadas ni puntuaciones enviadas por el cliente.
                try:
                    gateway.game._handle(peer, action)
                except (ValueError, TypeError, KeyError, OverflowError):
                    peer.send({'type':'error', 'message':'Mensaje invalido.'})
                self._json(200, {'ok':True})

        self.httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self._running = True
        for target in (self.httpd.serve_forever, self._reap):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self._threads.append(thread)
        print(f'[WEB] Abre http://IP_DEL_SERVIDOR:{self.port} en cada dispositivo.', flush=True)

    def stop(self):
        self._running = False
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
        for token in list(self.sessions):
            self.dispose(token)
        for thread in self._threads:
            if thread.is_alive():
                thread.join(timeout=2)


def main():
    parser = argparse.ArgumentParser(description='Cripta Pixel Online: servidor Python + clientes web multijugador')
    parser.add_argument('--host', default='0.0.0.0', help='Escuchar en todas las interfaces (LAN)')
    parser.add_argument('--web-port', type=int, default=8080, help='Puerto web (navegador)')
    parser.add_argument('--tcp-port', type=int, default=PORT, help='Puerto para el cliente Python opcional')
    parser.add_argument('--db', default=str(ROOT/'cripta.db'), help='Ubicacion SQLite')
    args = parser.parse_args()
    game = GameServer(args.host, args.tcp_port, args.db)
    gateway = BrowserGateway(game, args.host, args.web_port)
    try:
        game.start()
        gateway.start()
        print(f'[LISTO] Servidor web={gateway.port} / cliente Python TCP={game.port}', flush=True)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('\n[CRIPTA] Apagando servidor.', flush=True)
    finally:
        gateway.stop()
        game.stop()

if __name__ == '__main__':
    main()
