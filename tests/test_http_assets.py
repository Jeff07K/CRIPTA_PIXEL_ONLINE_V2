"""Verificación HTTP de imágenes realmente servidas al navegador."""
import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError

from server import GameServer
from server_web import BrowserGateway

ROOT=Path(__file__).resolve().parents[1]

class HttpAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.game=GameServer('127.0.0.1',0,str(Path(cls.tmp.name)/'test.sqlite'))
        cls.game.start()
        cls.web=BrowserGateway(cls.game,'127.0.0.1',0)
        cls.web.start()
        cls.base=f'http://127.0.0.1:{cls.web.port}'
    @classmethod
    def tearDownClass(cls):
        cls.web.stop();cls.game.stop();cls.tmp.cleanup()
    def test_game_serves_animated_atlases(self):
        for name in ['knight_rojo_sheet','knight_azul_sheet','knight_verde_sheet',
                     'knight_naranja_sheet','slime_sheet','boss_sheet',
                     'terrain_forest','terrain_ice','terrain_fire','terrain_arena',
                     'goblin_sheet','skeleton_sheet','fx_brutal_sheet','fx_distancia_sheet','fx_veneno_sheet','fx_paralisis_sheet']:
            with self.subTest(name=name):
                with urlopen(f'{self.base}/assets/{name}.png',timeout=3) as response:
                    self.assertEqual(response.status,200)
                    self.assertIn('image/png',response.headers['Content-Type'])
                    self.assertEqual(response.read(),(ROOT/'assets'/f'{name}.png').read_bytes())
    def test_http_and_status(self):
        with urlopen(self.base+'/',timeout=3) as response:
            html=response.read().decode('utf8')
            self.assertIn('EL VIAJE',html)
            self.assertIn('zoom-toggle',html)
            self.assertIn('minimap',html)
        with urlopen(self.base+'/api/status',timeout=3) as response:
            self.assertTrue(json.load(response)['ok'])

if __name__=='__main__':unittest.main()
