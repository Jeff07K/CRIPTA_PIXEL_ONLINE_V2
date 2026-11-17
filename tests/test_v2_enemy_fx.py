"""Verifica que la entrega v2 contiene sprites jugables y FX con fotogramas únicos."""
import unittest
from pathlib import Path
try:
    from PIL import Image
except ImportError:
    Image=None

ROOT=Path(__file__).resolve().parents[1]
AS=ROOT/'assets'

class EnemyV2Tests(unittest.TestCase):
    @unittest.skipUnless(Image is not None, "Pillow solo es necesario para verificación de píxeles y regeneración")
    def test_enemies_have_4_directions_and_action_rows(self):
        for name in ('goblin','skeleton'):
            im=Image.open(AS/(name+'_sheet.png'))
            self.assertEqual(im.size,(160,640))
            for state in range(4):
                for facing in range(4):
                    row=state*4+facing
                    frames=[im.crop((40*i,40*row,40*(i+1),40*(row+1))).tobytes() for i in range(4)]
                    with self.subTest(name=name,state=state,face=facing):
                        self.assertTrue(any(px!=frames[0] for px in frames[1:]),'No hay animación real')
                        self.assertGreater(len(set(frames)),1)
            self.assertNotEqual(im.crop((0,0,40,40)).tobytes(),im.crop((0,3*40,40,4*40)).tobytes(),'El reverso debe ser distinto')
    @unittest.skipUnless(Image is not None, "Pillow solo es necesario para verificación de píxeles y regeneración")
    def test_q_has_4_distinct_visual_atlases(self):
        fingerprints=[]
        for name in ('brutal','distancia','veneno','paralisis'):
            im=Image.open(AS/f'fx_{name}_sheet.png')
            self.assertEqual(im.size,(768,96))
            frames=[im.crop((96*i,0,96*(i+1),96)).tobytes() for i in range(8)]
            self.assertGreater(len(set(frames)),5)
            fingerprints.append(frames[4])
        self.assertEqual(len(set(fingerprints)),4)
    def test_js_uses_fx_atlases_only_for_visuals(self):
        js=(ROOT/'web/app.js').read_text()
        self.assertIn('function drawSpecialEffects',js)
        self.assertIn('app.effectSeq.set(id,sequence)',js)
        self.assertIn('function processCombatFeedback',js)
        self.assertIn("obj.kind==='goblin'||obj.kind==='skeleton'",js)
        self.assertIn('drawSpecialEffects(step)',js)
        self.assertIn('Math.max(0,enemyState)*4',js)
    def test_pygame_and_server_support_enemy_directions(self):
        py=(ROOT/'client.py').read_text()
        srv=(ROOT/'server.py').read_text()
        self.assertIn("16 if name in ('goblin','skeleton')",py)
        self.assertIn('def draw_special_effects',py)
        self.assertIn('abs(delta_x) >= abs(delta_y)',srv)
    def test_v2_assets_generated_in_project(self):
        generator=ROOT/'generar_enemigos_y_efectos.py'
        self.assertTrue(generator.is_file())
        self.assertIn('def generate_fx',generator.read_text())

if __name__=='__main__':unittest.main()
