"""Cobertura de atlas, eventos de animación y movimiento autoritativo.
Ninguna de estas pruebas requiere Pygame ni conexión de red pública.
"""
import struct
import time
import unittest
from pathlib import Path

from server import Room, SPAWNS

ROOT=Path(__file__).resolve().parents[1]
AS=ROOT/'assets'

class FakePeer:
    def __init__(self,name):
        self.key=name
        self.username=name
        self.user_id=1
        self.special='veneno'
    def send(self,payload):pass

class AnimationAssetsTests(unittest.TestCase):
    def dimensions(self,path):
        data=path.read_bytes()
        self.assertEqual(data[:8],b'\x89PNG\r\n\x1a\n')
        self.assertEqual(data[25],6)
        return struct.unpack('>II',data[16:24])
    def test_player_spritesheets_and_legacy_menu_paths(self):
        for color in ('rojo','azul','verde','naranja'):
            with self.subTest(color=color):
                self.assertEqual(self.dimensions(AS/f'knight_{color}_sheet.png'),(192,1344))
                self.assertEqual(self.dimensions(AS/f'knight_{color}.png'),(48,48))
                self.assertGreater((AS/f'knight_{color}_sheet.png').stat().st_size,5000)
                self.assertTrue((AS/'maestros'/f'knight_{color}.png').exists())
    def test_enemy_sheets_and_environment_decor(self):
        for name in ('slime','bat','goblin','skeleton','flame','boss','ghost'):
            with self.subTest(name=name):self.assertEqual(self.dimensions(AS/f'{name}_sheet.png'),(160,640) if name in ('goblin','skeleton') else (160,120))
        for name in ('forest','ice','fire','arena'):
            with self.subTest(name=name):self.assertEqual(self.dimensions(AS/f'terrain_{name}.png'),(64,72))
    def test_javascript_and_pygame_load_real_sheets(self):
        js=(ROOT/'web/app.js').read_text('utf-8')
        py=(ROOT/'client.py').read_text('utf-8')
        self.assertIn("'knight_'+c+'_sheet'",js)
        self.assertIn("'terrain_'+c",js)
        self.assertIn('animatedPose(',js)
        self.assertIn("name+'_sheet.png'",py)
        self.assertIn('def animation_frame(',py)
    def test_four_unique_walk_frames_per_direction_and_scarf(self):
        try:from PIL import Image
        except ImportError:self.skipTest('Pillow optional (necessary only for visual regeneration)')
        for color in ('rojo','azul','verde','naranja'):
            im=Image.open(AS/f'knight_{color}_sheet.png')
            for direction in range(4):
                row=4+direction
                frames=[im.crop((f*48,row*48,(f+1)*48,(row+1)*48)).tobytes() for f in range(4)]
                with self.subTest(color=color,direction=direction):self.assertEqual(len(set(frames)),4)

class AnimationAuthoritativeTests(unittest.TestCase):
    def make_room(self):
        p=FakePeer('KnightA')
        r=Room('ABCDEF','solo',p)
        r.start()
        return r,r.players[p.key]
    def test_movement_and_attack_are_server_authorized(self):
        r,p=self.make_room();now=time.monotonic()+.25
        x0=p['x']
        p.update(dx=1,dy=0,last_input=now)
        r.tick(.10,now)
        self.assertGreater(p['x'],x0)
        self.assertTrue(p['moving'])
        self.assertEqual(p['face'],'right')
        snap=r.snapshot()['players'][0]
        self.assertIn('moving',snap)
        self.assertIn('attack_seq',snap)
        self.assertIn('special_seq',snap)
        self.assertIn('block_seq',snap)
        self.assertIn('hurt_seq',snap)
        p.update(dx=0,dy=0,last_input=now+.2)
        r.tick(.07,now+.2)
        self.assertFalse(p['moving'])
        self.assertEqual(p['attack_seq'],0)
        p['attack']=True
        r.tick(.04,now+.35)
        self.assertEqual(p['attack_seq'],1)
        p['defend']=True
        r.tick(.04,now+.40)
        self.assertEqual(p['block_seq'],1)
        self.assertTrue(r.snapshot()['players'][0]['blocking'])
        p['special_attack']=True
        r.tick(.04,now+.45)
        self.assertEqual(p['special_seq'],1)
        self.assertEqual(r.snapshot()['players'][0]['special'],'veneno')
    def test_hurt_events_and_enemy_behavior(self):
        r,p=self.make_room()
        now=time.monotonic()+.2
        r.enemies=[dict(id=111,kind='slime',x=p['x']+45,y=p['y']+10,hp=50,max_hp=50,
                hit_at=0.,attack_until=0.,attack_seq=0,hurt_seq=0,hurt_until=0.,
                moving=False,face='left',paralyzed_until=0.,poison_ticks=0,poison_next=0.,poison_source=None)]
        e=r.enemies[0]
        old_x=e['x']
        r.tick(.1,now)
        self.assertTrue(e['moving'])
        self.assertLess(e['x'],old_x)
        r._damage_enemy(e,11,p)
        self.assertEqual(e['hurt_seq'],1)
        self.assertTrue(r.snapshot()['enemies'][0]['hurt'])
        r._damage_player(p,5,None,now)
        self.assertEqual(p['hurt_seq'],1)
        self.assertTrue(r.snapshot()['players'][0]['hurt'])

if __name__=='__main__': unittest.main()
