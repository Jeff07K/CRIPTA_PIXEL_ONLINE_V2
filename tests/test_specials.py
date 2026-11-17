"""Pruebas de Q/E: efectos y validación desde el servidor, no del navegador."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from server import (Room, SCARF_COLORS, SPECIALS, GameServer, DEFENSE_COOLDOWN,
                    DEFENSE_DURATION, SPECIAL_COOLDOWN)
from server_web import BrowserGateway
from test_web_multiplayer import HttpClient

class Peer:
    def __init__(self, n, special='brutal'):
        self.key=n
        self.username=n
        self.user_id=1
        self.room_id=None
        self.special=special
        self.messages=[]
    def send(self, msg):self.messages.append(msg)


def room(mode='solo', specials=('brutal',)):
    peers=[Peer('p'+str(i),s) for i,s in enumerate(specials)]
    r=Room('SAMPLE',mode,peers[0]);r.peers.extend(peers[1:]);r.start()
    return r,[r.players[p.key] for p in peers]

class MechanicsTests(unittest.TestCase):
    def test_scarf_colors_unique_and_identical_class(self):
        r,players=room('coop',tuple(SPECIALS))
        self.assertEqual([p['color'] for p in players],list(SCARF_COLORS))
        self.assertEqual([p['special'] for p in players],list(SPECIALS))
        self.assertEqual([p['color'] for p in r.snapshot()['players']],list(SCARF_COLORS))

    def test_brutal_damage_and_hp_cost_even_when_misses(self):
        r,ps=room('solo',('brutal',));p=ps[0]
        t=time.monotonic()+1
        p['hp']=100
        r.enemies=[]
        r._attack(p,t,special=True)
        self.assertEqual(p['hp'],95)
        self.assertAlmostEqual(p['special_cd']-t,SPECIAL_COOLDOWN)
        r._attack(p,t+1,special=True)
        self.assertEqual(p['hp'],95)
        # PVE: 32*1.6 redondeado al entero mas cercano = 51.
        r.enemies=[{'id':9,'kind':'boss','x':p['x']+20,'y':p['y'],'hp':310,'max_hp':310,
                    'poison_ticks':0,'poison_next':0,'poison_source':None,'paralyzed_until':0,'hit_at':0}]
        r._attack(p,t+6.1,special=True)
        self.assertEqual(r.enemies[0]['hp'],259)
        self.assertEqual(p['hp'],90)

    def test_double_range_and_75_percent(self):
        r,ps=room('solo',('distancia',));p=ps[0];t=time.monotonic()+1
        e={'id':1,'kind':'slime','x':p['x']+100,'y':p['y'],'hp':50,'max_hp':50,
            'poison_ticks':0,'poison_next':0,'poison_source':None,'paralyzed_until':0,'hit_at':0}
        r.enemies=[e]
        r._attack(p,t)
        self.assertEqual(e['hp'],50)
        r._attack(p,t+.1,special=True)
        self.assertEqual(e['hp'],26)  # 32 x 75%=24

    def test_poison_three_seconds_of_current_health_nonstacking(self):
        r,ps=room('solo',('veneno',));p=ps[0];t=time.monotonic()+1
        e={'id':1,'kind':'boss','x':p['x']+18,'y':p['y'],'hp':310,'max_hp':310,
           'poison_ticks':0,'poison_next':0,'poison_source':None,'paralyzed_until':0,'hit_at':0}
        r.enemies=[e]
        r._attack(p,t,special=True)
        self.assertEqual(e['hp'],278)
        self.assertEqual(e['poison_ticks'],3)
        r._update_poison(t+.9);self.assertEqual(e['hp'],278)
        r._update_poison(t+1.1);self.assertEqual(e['hp'],208) # round(278*.25) -> 70
        r._update_poison(t+2.1);self.assertEqual(e['hp'],156)
        r._update_poison(t+3.1);self.assertEqual(e['hp'],117)
        self.assertEqual(e['poison_ticks'],0)
        r._update_poison(t+30);self.assertEqual(e['hp'],117)

    def test_paralysis_stops_movement_but_expires(self):
        r,ps=room('pvp',('paralisis','brutal'));attacker,target=ps
        t=time.monotonic()+1
        target['x']=attacker['x']+20;target['y']=attacker['y']
        r._attack(attacker,t,special=True)
        self.assertEqual(target['hp'],66) # base pvp 34
        self.assertAlmostEqual(target['paralyzed_until']-t,3)
        target['dx']=1
        old_x=target['x'];target['last_input']=t
        r.tick(.2,t+.5);self.assertEqual(target['x'],old_x)
        target['dx']=1
        target['last_input']=t+3.1
        r.tick(.2,t+3.1);self.assertGreater(target['x'],old_x)

    def test_defense_limits_and_cooldown(self):
        r,ps=room('pvp',('brutal','brutal'));attacker,defender=ps
        t=time.monotonic()+1
        r._defend(defender,t)
        self.assertAlmostEqual(defender['block_until']-t,DEFENSE_DURATION)
        self.assertAlmostEqual(defender['defense_cd']-t,DEFENSE_COOLDOWN)
        with patch('server.random.uniform',return_value=.90):
            r._damage_player(defender,20,attacker,t+.3)
        self.assertEqual(defender['hp'],98)
        with patch('server.random.uniform',return_value=.005):
            r._damage_player(defender,20,attacker,t+.6)
        self.assertEqual(defender['hp'],78)
        r._defend(defender,t+1.1)
        self.assertEqual(defender['block_until'],t+1)
        r._defend(defender,t+3.1)
        self.assertGreater(defender['block_until'],t+3)
        self.assertEqual(defender['hp'],78)

    def test_poison_pvp_attributes_kill_to_attacker_and_respawn(self):
        r,ps=room('pvp',('veneno','brutal'));a,b=ps
        t=time.monotonic()+1
        b['x']=a['x']+20;b['y']=a['y'];b['hp']=45
        r._attack(a,t,special=True)
        self.assertEqual(b['hp'],11)
        r._update_poison(t+1.1)
        self.assertEqual(b['hp'],8)
        r._update_poison(t+2.1)
        self.assertEqual(b['hp'],6)
        r._update_poison(t+3.1)
        self.assertEqual(b['hp'],4)
        self.assertEqual(a['kills'],0)
        # Direct kill after poison via normal attack, should not award twice
        r._attack(a,t+3.2)
        self.assertEqual(b['hp'],0)
        self.assertEqual(a['kills'],1)
        self.assertEqual(a['score'],140)
        r._update_poison(t+100)
        self.assertEqual(a['kills'],1)

class NetworkLoadoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.game=GameServer('127.0.0.1',0,str(Path(cls.tmp.name)/'db.sqlite'))
        cls.game.start()
        cls.gateway=BrowserGateway(cls.game,'127.0.0.1',0)
        cls.gateway.start()
        cls.base=f'http://127.0.0.1:{cls.gateway.port}'
    @classmethod
    def tearDownClass(cls):
        cls.gateway.stop();cls.game.stop();cls.tmp.cleanup()
    def make_user(self,name):
        c=HttpClient(self.base);c.expect('hello')
        c.action('register',username=name,password='password123');self.assertTrue(c.expect('register_result')['ok'])
        c.action('login',username=name,password='password123');self.assertTrue(c.expect('login_result')['ok'])
        return c
    def test_web_two_players_select_and_lock(self):
        a=self.make_user('QwebAlice');b=self.make_user('QwebBob')
        a.action('create_room',mode='coop',special='veneno')
        code=a.expect('room_state')['code']
        b.action('join_room',code=code,special='distancia')
        room_state=b.expect('room_state')
        self.assertEqual([x['special'] for x in room_state['loadouts']],['veneno','distancia'])
        b.action('equip_special',special='paralisis')
        changed=b.expect('room_state')
        self.assertEqual(changed['loadouts'][1]['special'],'paralisis')
        a.action('start_room')
        snap=a.expect('game_state')
        self.assertEqual([(p['color'],p['special']) for p in snap['players']],
                         [('rojo','veneno'),('azul','paralisis')])
        b.action('equip_special',special='brutal')
        self.assertIn('antes',b.expect('error')['message'])
        b.action('input',dx=0,dy=0,special_attack=True,defend=True)
        time.sleep(.10)
        with self.game.lock:
            room=self.game.rooms[code]
            p=room.players[b.key]
            self.assertGreater(p['special_cd'],time.monotonic())
            self.assertGreater(p['block_until'],time.monotonic())
        a.action('leave_room');b.action('leave_room')
    def test_invalid_special_rejected(self):
        a=self.make_user('QwebBad')
        a.action('create_room',mode='solo',special='godmode')
        self.assertIn('Especial',a.expect('error')['message'])
        with self.game.lock:
            self.assertFalse(any(r.mode=='solo' and r.peers[0].key==a.key for r in self.game.rooms.values()))
        a.action('equip_special',special='veneno')
        self.assertEqual(a.expect('loadout')['special'],'veneno')
        a.action('create_room',mode='solo')
        snap=a.expect('game_state')
        self.assertEqual(snap['players'][0]['special'],'veneno')
        a.action('leave_room')

if __name__=='__main__':unittest.main()
