"""Pruebas reproducibles del transporte de baja latencia, sin servicios externos."""
from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from server import GameServer
from server_web import BrowserGateway


class TransportPerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.game = GameServer('127.0.0.1', 0, str(Path(cls.tmp.name) / 'test.db'))
        cls.game.start()
        cls.gateway = BrowserGateway(cls.game, '127.0.0.1', 0)
        cls.gateway.start()
        cls.base = f'http://127.0.0.1:{cls.gateway.port}'

    @classmethod
    def tearDownClass(cls):
        cls.gateway.stop()
        cls.game.stop()
        cls.tmp.cleanup()

    def post(self, path, obj):
        req = Request(self.base + path, data=json.dumps(obj).encode(),
                      headers={'Content-Type': 'application/json'}, method='POST')
        with urlopen(req, timeout=5) as resp:
            return json.load(resp)

    def new_session(self):
        return self.post('/api/connect', {})

    def action(self, session, **action):
        return self.post('/api/action', {'session': session, 'action': action})

    def collect(self, session):
        with urlopen(self.base + '/api/events?session=' + quote(session), timeout=5) as resp:
            return json.load(resp)['events']

    def wait_for(self, session, kind, timeout=4):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for item in self.collect(session):
                if item.get('type') == kind:
                    return item
            time.sleep(.04)
        self.fail(f'No llego {kind}')

    def create_solo(self, user):
        conn = self.new_session()
        token = conn['session']
        self.action(token, type='register', username=user, password='password123')
        self.wait_for(token, 'register_result')
        self.action(token, type='login', username=user, password='password123')
        self.wait_for(token, 'login_result')
        self.action(token, type='create_room', mode='solo')
        room = self.wait_for(token, 'room_state')
        self.assertEqual(room['status'], 'playing')
        return token, conn['key'], room['code']

    def test_sse_stream_receives_events_without_polling(self):
        c = self.new_session()
        token = c['session']
        with urlopen(self.base + '/api/stream?session=' + quote(token), timeout=4) as resp:
            self.assertIn('text/event-stream', resp.headers['Content-Type'])
            self.assertEqual(resp.readline(), b': connected\n')
            self.assertEqual(resp.readline(), b'\n')
            data = resp.readline()
            self.assertTrue(data.startswith(b'data: '))
            first = json.loads(data[6:])
            self.assertEqual(first['events'][0]['type'], 'hello')
            self.assertEqual(resp.readline(), b'\n')
            t = time.monotonic()
            self.action(token, type='register', username='streamTest', password='password123')
            nxt = json.loads(resp.readline()[6:])
            self.assertEqual(nxt['events'][0]['type'], 'register_result')
            # Prueba local de entrega inmediata: NO es latencia del Internet/Render.
            self.assertLess(time.monotonic()-t, 0.8)
        self.assertTrue(self.post('/api/disconnect', {'session': token})['ok'])

    def test_sse_unknown_session_rejected(self):
        with self.assertRaises(HTTPError) as cm:
            urlopen(self.base+'/api/stream?session=noexiste', timeout=4)
        self.assertEqual(cm.exception.code, 401)

    def test_input_sequence_prevents_reordering_and_preserves_legacy_clients(self):
        token, key, code = self.create_solo('priorityUser')
        with self.game.lock:
            p = self.game.rooms[code].players[key]
            x = p['x']
        # Un ataque especial llega con seq nuevo, un antiguo intento de mover
        # llega tarde: el servidor ignora el paquete viejo.
        self.action(token, type='input', dx=1, dy=0, special_attack=True, seq=200)
        self.action(token, type='input', dx=-1, dy=0, seq=199)
        with self.game.lock:
            p = self.game.rooms[code].players[key]
            self.assertEqual(p['dx'], 1)
            self.assertTrue(p['special_attack'])
        time.sleep(.12)
        with self.game.lock:
            self.assertGreater(self.game.rooms[code].players[key]['x'], x)
        # Los clientes existentes sin campo seq siguen funcionando.
        self.action(token, type='input', dx=0, dy=0)
        with self.game.lock:
            self.assertEqual(self.game.rooms[code].players[key]['dx'], 0)
        self.action(token, type='leave_room')

    def test_snapshot_rate_reduced_but_physics_unchanged(self):
        token, key, code = self.create_solo('snapshotUser')
        self.collect(token)
        times = []
        stop = time.monotonic() + 1.3
        while time.monotonic() < stop:
            events = self.collect(token)
            if any(e.get('type') == 'game_state' for e in events):
                times.append(time.monotonic())
            time.sleep(.012)
        # Original: 20 estados/s; el nuevo objetivo es ~10/s.
        self.assertGreaterEqual(len(times), 6)
        self.assertLessEqual(len(times), 15)
        self.action(token, type='leave_room')

    def test_web_client_keeps_animations_and_fallback(self):
        js = (Path(__file__).resolve().parents[1] / 'web' / 'app.js').read_text()
        self.assertIn("new EventSource('/api/stream?session='", js)
        self.assertIn("'/api/events?wait=1&session='", js)
        self.assertIn('requestAnimationFrame(animate)', js)
        self.assertIn('function animatedPose', js)
        self.assertIn('requestInput(true)', js)
        self.assertIn('inputSeq', js)
        self.assertNotIn('},70);', js)


if __name__ == '__main__':
    unittest.main()
