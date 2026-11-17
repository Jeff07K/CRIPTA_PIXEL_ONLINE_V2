"""Pruebas sin dependencias externas de sprites realmente cargados en el juego."""
import hashlib
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'


class KnightSpriteIntegrationTests(unittest.TestCase):
    def test_four_playable_variants_exist_and_are_rgba_48x48(self):
        for color in ('rojo', 'azul', 'verde', 'naranja'):
            with self.subTest(color=color):
                content = (ASSETS / f'knight_{color}.png').read_bytes()
                self.assertEqual(content[:8], b'\x89PNG\r\n\x1a\n')
                self.assertEqual(struct.unpack('>II', content[16:24]), (48, 48))
                self.assertEqual(content[25], 6)  # truecolor + alpha

    def test_variants_differ_and_original_reference_is_present(self):
        digests = [hashlib.sha256((ASSETS / f'knight_{c}.png').read_bytes()).digest()
                   for c in ('rojo', 'azul', 'verde', 'naranja')]
        self.assertEqual(len(set(digests)), 4)
        self.assertTrue((ASSETS / 'REFERENCIA_ORIGINAL_CABALLERO.png').is_file())

    def test_both_clients_load_the_playable_sprite_paths(self):
        js = (ROOT / 'web' / 'app.js').read_text(encoding='utf-8')
        html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        desktop = (ROOT / 'client.py').read_text(encoding='utf-8')
        self.assertIn("'knight_rojo'", js)
        self.assertIn("'knight_azul'", js)
        self.assertIn("'knight_verde'", js)
        self.assertIn("'knight_naranja'", js)
        self.assertIn('/assets/knight_rojo.png', html)
        self.assertIn("'knight_'+color", desktop)


if __name__ == '__main__':
    unittest.main()
