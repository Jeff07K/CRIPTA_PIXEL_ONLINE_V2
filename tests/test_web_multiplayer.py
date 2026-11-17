"""Pruebas HTTP reales con clientes independientes, sin dependencias externas."""
import json
import socket
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from server import GameServer
from server_web import BrowserGateway


class HttpClient:
    def __init__(self, base):
        self.base=base
        data=self.post('/api/connect',{})
        self.session=data['session']
        self.key=data['key']

    def get(self,path):
        with urlopen(self.base+path,timeout=5) as reply:
            return json.loads(reply.read())

    def post(self,path,obj):
        data=json.dumps(obj).encode()
        req=Request(self.base+path,data=data,headers={'Content-Type':'application/json'},method='POST')
        with urlopen(req,timeout=5) as reply:
            return json.loads(reply.read())

    def action(self,kind,**attrs):
        return self.post('/api/action',{'session':self.session,'action':{'type':kind,**attrs}})

    def events(self):
        return self.get('/api/events?session='+quote(self.session))['events']

    def expect(self,kind,timeout=5):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            messages=self.events()
            for e in messages:
                if e.get('type')==kind:return e
                if e.get('type')=='error':raise AssertionError(f'Respuesta del servidor: {e}')
            time.sleep(.05)
        raise AssertionError(f'No llego evento {kind}')


class BrowserGameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.game=GameServer('127.0.0.1',0,str(Path(cls.tmp.name)/'game.db'))
        cls.game.start()
        cls.gateway=BrowserGateway(cls.game,'127.0.0.1',0)
        cls.gateway.start()
        cls.base=f'http://127.0.0.1:{cls.gateway.port}'

    @classmethod
    def tearDownClass(cls):
        cls.gateway.stop();cls.game.stop();cls.tmp.cleanup()

    def make_player(self,name):
        c=HttpClient(self.base)
        c.expect('hello')
        c.action('register',username=name,password='mypassword08')
        self.assertTrue(c.expect('register_result')['ok'])
        c.action('login',username=name,password='mypassword08')
        self.assertTrue(c.expect('login_result')['ok'])
        return c

    def test_01_static_files_and_status(self):
        with urlopen(self.base+'/') as page:
            html=page.read().decode()
        self.assertIn('Cripta Pixel Online',html)
        self.assertIn('app.js',html)
        self.assertIn('canvas id="world"',html)
        with urlopen(self.base+'/app.js') as page:
            self.assertIn(b'function paint',page.read())
        with urlopen(self.base+'/assets/hero.png') as page:
            self.assertEqual(page.read(8),b'\x89PNG\r\n\x1a\n')
        self.assertTrue(HttpClient(self.base).get('/api/status')['ok'])

    def test_02_four_players_join_coop_start_and_movement(self):
        people=[self.make_player('html_A'+str(i)) for i in range(4)]
        host=people[0]
        host.action('create_room',mode='coop')
        code=host.expect('room_state')['code']
        host.action('start_room')
        self.assertIn('entre 2 y 4',host.expect('error')['message'])
        for peer in people[1:]:peer.action('join_room',code=code)
        self.assertEqual(len(people[-1].expect('room_state')['players']),4)
        fifth=self.make_player('html_Extra')
        fifth.action('join_room',code=code)
        self.assertIn('llena',fifth.expect('error')['message'])
        host.action('start_room')
        snapshots=[p.expect('game_state') for p in people]
        for state in snapshots:
            self.assertEqual(state['mode'],'coop')
            self.assertEqual(len(state['players']),4)
            self.assertGreaterEqual(len(state['enemies']),5)
            self.assertEqual(len(state['map']),18)
        player_key=host.key
        with self.game.lock:
            p=self.game.rooms[code].players[player_key]
            x=p['x'];y=p['y']
        host.action('input',dx=1,dy=0,attack=False)
        time.sleep(.25)
        with self.game.lock:
            p=self.game.rooms[code].players[player_key]
            self.assertGreater(p['x'],x)
            self.assertLess(p['x']-x,45)  # servidor limita velocidad
            self.assertEqual(p['y'],y)
        # Ningun jugador puede inyectar un puntaje/posicion como 'input'.
        host.action('input',dx=10000,dy=0,x=888888,score=999999)
        time.sleep(.08)
        with self.game.lock:
            self.assertNotEqual(self.game.rooms[code].players[player_key]['x'],888888)
            self.assertEqual(self.game.rooms[code].players[player_key]['score'],0)
        for peer in people:peer.action('leave_room')
        self.assertTrue(people[0].expect('left_room'))

    def test_03_pvp_finished_and_ranking_saved(self):
        a=self.make_player('pvp_Alpha')
        b=self.make_player('pvp_Bravo')
        a.action('create_room',mode='pvp')
        code=a.expect('room_state')['code']
        b.action('join_room',code=code)
        self.assertEqual(len(b.expect('room_state')['players']),2)
        a.action('start_room')
        self.assertEqual(a.expect('game_state')['mode'],'pvp')
        # Simular un marcador de final de partida dentro del servidor (sin esperar
        # 3 minutos), comprobar que el evento y SQL llegan via HTTP a los clientes.
        with self.game.lock:
            room=self.game.rooms[code]
            room.players[a.key]['kills']=5
            room.players[a.key]['score']=700
        end=a.expect('game_over',timeout=4)
        self.assertEqual(end['winner'],'pvp_Alpha')
        self.assertEqual(end['mode'],'pvp')
        self.assertIn(b.expect('game_over')['reason'],('pvp_end',))
        a.action('ranking',mode='pvp')
        listing=a.expect('ranking')['items']
        found=next(v for v in listing if v['name']=='pvp_Alpha')
        self.assertGreaterEqual(found['points'],1250)
        self.assertEqual(found['wins'],1)
        a.action('leave_room');b.action('leave_room')

    def test_04_sessions_are_independent(self):
        one=HttpClient(self.base);two=HttpClient(self.base)
        self.assertNotEqual(one.session,two.session)
        self.assertNotEqual(one.key,two.key)
        one.post('/api/disconnect',{'session':one.session})
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError) as cm:
            one.get('/api/events?session='+quote(one.session))
        self.assertEqual(cm.exception.code,401)
        self.assertTrue(two.get('/api/events?session='+quote(two.session))['ok'])

    def test_05_restore_session_state(self):
        a=self.make_player('resumePlayer')
        a.action('create_room',mode='coop')
        room=a.expect('room_state')
        snapshot=a.get('/api/state?session='+quote(a.session))
        self.assertEqual(snapshot['name'],'resumePlayer')
        self.assertEqual(snapshot['key'],a.key)
        self.assertEqual(snapshot['room']['code'],room['code'])
        self.assertIsNone(snapshot['game'])
        a.action('leave_room')

    def test_06_mixed_tcp_and_browser_players(self):
        # Un cliente nativo Python y un cliente web comparten sala y simulacion.
        browser=self.make_player('mixedBrowser')
        tcp=socket.create_connection(('127.0.0.1',self.game.port),timeout=5)
        try:
            stream=tcp.makefile('rb')
            tcp.settimeout(5)
            def read(expected):
                end=time.monotonic()+5
                while time.monotonic()<end:
                    msg=json.loads(stream.readline())
                    if msg.get('type')==expected:return msg
                raise AssertionError('TCP timeout')
            def send(kind,**kw):
                tcp.sendall(json.dumps({'type':kind,**kw}).encode()+b'\n')
            read('hello')
            send('register',username='mixedTcp',password='mypassword08')
            self.assertTrue(read('register_result')['ok'])
            send('login',username='mixedTcp',password='mypassword08')
            self.assertTrue(read('login_result')['ok'])
            send('create_room',mode='coop')
            code=read('room_state')['code']
            browser.action('join_room',code=code)
            self.assertEqual(len(browser.expect('room_state')['players']),2)
            send('start_room')
            state=browser.expect('game_state')
            self.assertEqual(len(state['players']),2)
            current=read('room_state')
            if current['status']=='lobby':current=read('room_state')
            self.assertEqual(current['status'],'playing')
            browser.action('leave_room')
        finally:
            tcp.close()


    def test_07_solo_starts_immediately_without_party(self):
        player=self.make_player('soloHero_07')
        player.action('create_room',mode='solo')
        joined=player.expect('room_state')
        self.assertEqual(joined['status'],'playing')
        self.assertEqual(joined['min_players'],1)
        self.assertEqual(joined['max_players'],1)
        self.assertEqual(joined['players'],['soloHero_07'])
        snap=player.expect('game_state')
        self.assertEqual(snap['mode'],'solo')
        self.assertEqual(len(snap['players']),1)
        self.assertTrue(snap['enemies'])
        visitor=self.make_player('soloVisitor')
        visitor.action('join_room',code=joined['code'])
        self.assertIn('no admite',visitor.expect('error')['message'])
        # Superar los 3 pisos con el simulador del servidor bajo un unico lock;
        # esto verifica progresion, victoria y guardado real en la base SQLite.
        with self.game.lock:
            room=self.game.rooms[joined['code']]
            for floor in (1,2,3):
                self.assertEqual(room.floor,floor)
                room.enemies.clear()
                now=time.monotonic()+floor*10
                self.assertIsNone(room.tick(0,now))
                result=room.tick(0,now+3.1)
                if floor<3:self.assertIsNone(result)
                else:self.assertEqual(result,'victory')
            self.game._finish(room,'victory')
        finished=player.expect('game_over')
        self.assertEqual(finished['mode'],'solo')
        self.assertEqual(finished['winner'],'soloHero_07')
        player.action('ranking',mode='solo')
        ranking=player.expect('ranking')
        self.assertEqual(ranking['mode'],'solo')
        row=next(x for x in ranking['items'] if x['name']=='soloHero_07')
        self.assertEqual(row['wins'],1)
        self.assertGreater(row['points'],0)
        player.action('leave_room')

    def test_08_each_mode_has_its_own_ranking_and_invalid_modes_are_rejected(self):
        player=self.make_player('rankInspector')
        for mode in ('solo','coop','pvp'):
            player.action('ranking',mode=mode)
            answer=player.expect('ranking')
            self.assertEqual(answer['mode'],mode)
            names={row['name'] for row in answer['items']}
            if mode=='solo':
                self.assertIn('soloHero_07',names)
                self.assertNotIn('pvp_Alpha',names)
            elif mode=='pvp':
                self.assertIn('pvp_Alpha',names)
                self.assertNotIn('soloHero_07',names)
            else:
                self.assertNotIn('soloHero_07',names)
                self.assertNotIn('pvp_Alpha',names)
        player.action('ranking',mode='global')
        self.assertIn('Modo de ranking',player.expect('error')['message'])

    def test_09_solo_defeat_is_recorded_only_under_solo(self):
        player=self.make_player('soloDefeat')
        player.action('create_room',mode='solo')
        room_data=player.expect('room_state')
        with self.game.lock:
            room=self.game.rooms[room_data['code']]
            room.players[player.key]['hp']=0
        gameover=player.expect('game_over')
        self.assertEqual(gameover['reason'],'defeat')
        player.action('ranking',mode='solo')
        ranking=player.expect('ranking')['items']
        row=next(x for x in ranking if x['name']=='soloDefeat')
        self.assertEqual(row['wins'],0)
        self.assertEqual(row['games'],1)
        player.action('ranking',mode='coop')
        self.assertNotIn('soloDefeat',{x['name'] for x in player.expect('ranking')['items']})
        player.action('leave_room')


if __name__=='__main__':unittest.main()
