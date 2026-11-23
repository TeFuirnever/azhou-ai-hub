import math
import plistlib
import struct
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1] / 'assets/cursors/azhou-double-hug'
CG = 'com.apple.coregraphics.'
NS = 'com.apple.cursor.'
CORE_ROLES = ('Arrow', 'ArrowCtx', 'ArrowS', 'IBeam', 'IBeamS', 'IBeamXOR', 'Move', 'Wait')
NATIVE_ROLES = (2, 3, 4, 5, 7, *range(11, 24), *range(26, 41))
DIRECTIONAL = {CG+'Arrow', CG+'ArrowCtx', CG+'ArrowS', *(NS+str(n) for n in (2, 4, 5, 13, 40))}
GRAB = {NS+'11', NS+'12'}
ANIMATED = {
    CG+'IBeam': .05*32/24, CG+'IBeamS': .05*32/24, CG+'IBeamXOR': .05*32/24,
    CG+'Wait': 1/24, NS+'4': 1/24, NS+'11': .12, NS+'13': .05,
    NS+'14': 1/24, NS+'15': 1/24, NS+'16': 1/24, NS+'26': .05*32/24,
}


class AzhouDoubleHugPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = sorted(p.name for p in PACKAGE.glob('*.cape'))
        with (PACKAGE / 'Azhou-Double-Hug-3.6.1.cape').open('rb') as src:
            cls.cape = plistlib.load(src)
        cls.roles = cls.cape['Cursors']

    def test_release_identity_and_complete_role_set(self):
        self.assertEqual(self.files, ['Azhou-Double-Hug-3.6.1.cape'])
        self.assertEqual(self.cape['Identifier'], 'lab.azhou.cursors.doublehug.v361')
        self.assertEqual(self.cape['CapeVersion'], 3.61)
        self.assertTrue(self.cape['HiDPI'])
        self.assertEqual(set(self.roles), {
            *(CG+name for name in CORE_ROLES),
            *(NS+str(n) for n in NATIVE_ROLES),
        })

    def test_frames_hotspots_and_dimensions(self):
        for key, cursor in self.roles.items():
            with self.subTest(role=key):
                hotspot = (cursor['HotSpotX'], cursor['HotSpotY'])
                if key in DIRECTIONAL:
                    self.assertEqual(hotspot, (2.5, 2.5))
                elif key in GRAB:
                    self.assertEqual(hotspot, (16, 21))
                else:
                    self.assertEqual(hotspot, (16, 16))
                self.assertEqual((cursor['PointsWide'], cursor['PointsHigh']), (32, 32))
                frame_count = 24 if key in ANIMATED else 1
                self.assertEqual(cursor['FrameCount'], frame_count)
                self.assertTrue(math.isclose(cursor['FrameDuration'], ANIMATED.get(key, 1)))
                self.assertEqual(len(cursor['Representations']), 2)
                for n, data in zip((32, 64), cursor['Representations']):
                    self.assertEqual(data[:16], b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR')
                    self.assertEqual(struct.unpack('>II', data[16:24]), (n, n*frame_count))
        self.assertEqual(self.roles[CG+'Arrow'], self.roles[CG+'ArrowS'])


if __name__ == '__main__':
    unittest.main()
