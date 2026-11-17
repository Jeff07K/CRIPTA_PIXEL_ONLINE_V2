import json
import math
import socket
import tempfile
import time
import unittest
from pathlib import Path

from server import Database, GameServer, Room, SPAWNS, solid, move_entity
from protocol import dungeon_map


class FakePeer:
    def __init__(self, name, index):
        self.key = f'key-{index}'
        self.user_id = index+1
        self.username = name
        self.room_id = None
        self.messages = []

    def send(self, obj):
        self.messages.append(obj)


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.dir.name)/'test.db')

    def tearDown(self):
        self.dir.cleanup()

    def test_registration_validation_login(self):
        uid, _ = self.db.register('hero_01', 'secret654')
        self.assertTrue(uid)
        self.assertIsNone(self.db.register('hero_01', 'secret654')[0])
        self.assertIsNone(self.db.register('ab', 'secret654')[0])
        self.assertIsNone(self.db.register('validname', '12')[0])
        self.assertEqual(self.db.login('hero_01', 'bad')[0], None)
        self.assertEqual(self.db.login('HERO_01', 'secret654')[0], uid)

    def test_daily_ranking_aggregates_and_archives(self):
        a, _ = self.db.register('dungeonA', 'password1')
        b, _ = self.db.register('dungeonB', 'password2')
        self.db.result(a, 'coop', 50, 0, 1, 1)
        self.db.result(a, 'pvp', 200, 1, 3, 0)
        self.db.result(b, 'pvp', 249, 0, 2, 0)
        current = self.db.ranking()
        self.assertEqual(current[0]['name'], 'dungeonA')
        self.assertEqual(current[0]['points'], 250)
        self.assertEqual(current[0]['wins'], 1)
        self.assertEqual(current[0]['games'], 2)
        self.assertEqual(self.db.ranking('2001-01-01'), [])
        self.assertEqual(self.db.ranking(mode='solo'), [])
        coop=self.db.ranking(mode='coop')
        self.assertEqual(len(coop),1)
        self.assertEqual(coop[0]['name'],'dungeonA')
        self.assertEqual(coop[0]['points'],50)
        pvp=self.db.ranking(mode='pvp')
        self.assertEqual(len(pvp),2)
        self.assertEqual(next(x for x in pvp if x['name']=='dungeonA')['points'],200)
        self.assertEqual(next(x for x in pvp if x['name']=='dungeonB')['points'],249)



class TestPhysics(unittest.TestCase):
    def test_border_and_rocks(self):
        grid = dungeon_map(1)
        self.assertTrue(solid(grid, 1, 1))
        self.assertFalse(solid(grid, SPAWNS[0][0], SPAWNS[0][1]))
        p = {'x': SPAWNS[0][0], 'y': SPAWNS[0][1]}
        move_entity(p, -900, 0, grid)
        self.assertEqual(p['x'], SPAWNS[0][0])
        self.assertTrue(all(len(row) == 28 for row in grid))

    def test_combat_and_coop_progression(self):
        a, b = FakePeer('Aria', 0), FakePeer('Beto', 1)
        room = Room('COOP99', 'coop', a)
        room.peers.append(b)
        room.start()
        self.assertEqual(room.floor, 1)
        self.assertTrue(room.enemies)
        now = time.monotonic()
        room.enemies.clear()
        self.assertIsNone(room.tick(0, now))
        self.assertTrue(room.next_floor_at > now)
        room.tick(0, now+3.1)
        self.assertEqual(room.floor, 2)
        self.assertGreaterEqual(room.players[a.key]['score'], 160)
        self.assertEqual(room.players[a.key]['hp'], 100)

    def test_pvp_damage_and_kill(self):
        a, b = FakePeer('Aria', 0), FakePeer('Beto', 1)
        room = Room('PVP001', 'pvp', a)
        room.peers.append(b)
        room.start()
        p, target = room.players[a.key], room.players[b.key]
        target['x'] = p['x'] + 20
        target['y'] = p['y']
        t = time.monotonic() + 1
        for i in range(3):
            room._attack(p, t+i*.6)
        self.assertEqual(target['hp'], 0)
        self.assertEqual(p['kills'], 1)
        self.assertEqual(p['score'], 140)

    def test_minimum_and_maximum_room_capacity(self):
        peers = [FakePeer('test'+str(i), i) for i in range(4)]
        room = Room('TEST', 'coop', peers[0])
        room.peers.extend(peers[1:])
        room.start()
        self.assertEqual(len(room.players), 4)
        self.assertEqual(len(room.snapshot()['players']), 4)


class TcpTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = GameServer('127.0.0.1', 0, str(Path(self.temp.name)/'tcp.db'))
        self.server.start()
        self.clients = []
        self.buffers = {}

    def tearDown(self):
        for sock in self.clients:
            sock.close()
        self.server.stop()
        self.temp.cleanup()

    def newclient(self):
        s = socket.create_connection(('127.0.0.1', self.server.port), timeout=5)
        self.clients.append(s)
        self.buffers[s] = b''
        self.next_event(s, 'hello')
        return s

    def send(self, s, obj):
        s.sendall(json.dumps(obj).encode() + b'\n')

    def next_event(self, s, expected, timeout=4):
        limit = time.monotonic() + timeout
        while time.monotonic() < limit:
            while b'\n' in self.buffers[s]:
                line, self.buffers[s] = self.buffers[s].split(b'\n', 1)
                event = json.loads(line)
                if event.get('type') == expected:
                    return event
                if event.get('type') == 'error' and expected != 'error':
                    self.fail('Server error: '+str(event))
            s.settimeout(max(0.1, limit-time.monotonic()))
            self.buffers[s] += s.recv(16384)
        self.fail(f'Timed out waiting for {expected}')

    def test_network_two_clients_create_join_and_start(self):
        a = self.newclient()
        b = self.newclient()
        for s, username in ((a, 'alpha123'), (b, 'bravo123')):
            self.send(s, {'type':'register','username':username,'password':'password_1'})
            self.assertTrue(self.next_event(s,'register_result')['ok'])
            self.send(s, {'type':'login','username':username,'password':'password_1'})
            self.assertTrue(self.next_event(s,'login_result')['ok'])
        self.send(a, {'type':'create_room', 'mode':'coop'})
        room = self.next_event(a, 'room_state')
        code = room['code']
        self.assertEqual(len(room['players']), 1)
        self.send(a, {'type':'start_room'})
        self.assertIn('entre 2 y 4', self.next_event(a,'error')['message'].lower())
        self.send(b, {'type':'join_room', 'code':code})
        joined = self.next_event(b, 'room_state')
        self.assertEqual(len(joined['players']), 2)
        self.send(a, {'type':'start_room'})
        game = self.next_event(a, 'game_state')
        self.assertEqual(game['mode'], 'coop')
        self.assertEqual(len(game['players']), 2)
        self.assertTrue(len(game['enemies']) >= 5)
        key = game['players'][0]['key']
        x0 = game['players'][0]['x']
        self.send(a, {'type':'input', 'dx':1, 'dy':0, 'attack':False})
        time.sleep(0.25)
        game2 = self.next_event(a, 'game_state')
        # Puede haber snapshots previos en el buffer; consultar el estado verdadero del servidor.
        with self.server.lock:
            room_obj = self.server.rooms[code]
            self.assertGreater(room_obj.players[key]['x'], x0)
        self.send(a, {'type':'ranking'})
        self.assertEqual(self.next_event(a, 'ranking')['items'], [])


if __name__ == '__main__':
    unittest.main()
