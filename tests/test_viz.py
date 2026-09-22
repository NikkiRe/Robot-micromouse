import os
import struct
import tempfile
import unittest
import zlib

from sim.maze import Maze, generate
from sim.simulate import run
from sim.strategies import make_strategy
from sim.viz import (
    FONT_3X5, PALETTE, Canvas, GifWriter, Renderer, animate, encode_png, lzw_encode, render_ascii,
)


def lzw_decode(data: bytes, min_code_size: int) -> bytes:
    clear, eoi = 1 << min_code_size, (1 << min_code_size) + 1
    code_size = min_code_size + 1
    table = [bytes([i]) for i in range(clear)] + [b"", b""]
    acc = nbits = pos = 0
    out = bytearray()
    prev = None
    while True:
        while nbits < code_size:
            if pos >= len(data):
                raise ValueError("поток оборвался")
            acc |= data[pos] << nbits
            pos += 1
            nbits += 8
        code = acc & ((1 << code_size) - 1)
        acc >>= code_size
        nbits -= code_size
        if code == clear:
            table = table[: clear + 2]
            code_size = min_code_size + 1
            prev = None
            continue
        if code == eoi:
            return bytes(out)
        if code < len(table):
            entry = table[code]
            if prev is not None:
                table.append(prev + entry[:1])
        elif prev is not None and code == len(table):
            entry = prev + prev[:1]
            table.append(entry)
        else:
            raise ValueError(f"плохой код {code}")
        out += entry
        prev = entry
        if len(table) == (1 << code_size) and code_size < 12:
            code_size += 1


class LzwTest(unittest.TestCase):
    def test_roundtrip_patterns(self):
        cases = [
            b"",
            b"\x00",
            b"\x01\x01\x01\x01\x01\x01\x01\x01",
            bytes(range(16)) * 40,
            bytes((i * 7) % 16 for i in range(5000)),
            bytes((i // 3) % 16 for i in range(20000)),
        ]
        for data in cases:
            self.assertEqual(lzw_decode(lzw_encode(data, 4), 4), data)

    def test_roundtrip_8bit(self):
        import random
        rng = random.Random(3)
        data = bytes(rng.randrange(256) for _ in range(30000))
        self.assertEqual(lzw_decode(lzw_encode(data, 8), 8), data)


class PngTest(unittest.TestCase):
    def test_structure_and_pixels(self):
        cv = Canvas(5, 3, 1)
        cv.fill_rect(1, 1, 2, 1, 7)
        png = encode_png(cv)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        pos, chunks = 8, {}
        while pos < len(png):
            (length,) = struct.unpack(">I", png[pos:pos + 4])
            kind = png[pos + 4:pos + 8]
            data = png[pos + 8:pos + 8 + length]
            (crc,) = struct.unpack(">I", png[pos + 8 + length:pos + 12 + length])
            self.assertEqual(crc, zlib.crc32(kind + data) & 0xFFFFFFFF)
            chunks[kind] = data
            pos += 12 + length
        self.assertEqual(list(chunks), [b"IHDR", b"PLTE", b"IDAT", b"IEND"])
        self.assertEqual(struct.unpack(">IIBBBBB", chunks[b"IHDR"]), (5, 3, 8, 3, 0, 0, 0))
        self.assertEqual(len(chunks[b"PLTE"]), 3 * len(PALETTE))
        raw = zlib.decompress(chunks[b"IDAT"])
        self.assertEqual(raw, b"\x00\x01\x01\x01\x01\x01" b"\x00\x01\x07\x07\x01\x01" b"\x00\x01\x01\x01\x01\x01")


class GifTest(unittest.TestCase):
    def test_partial_frames_and_delays(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.gif")
            w = GifWriter(path, 8, 6)
            cv = Canvas(8, 6, 0)
            w.add_frame(cv, 5)
            w.add_frame(cv, 5)
            cv.fill_rect(2, 3, 3, 2, 9)
            w.add_frame(cv, 5)
            w.close(last_delay=100)
            self.assertEqual(w.frames, 2)
            data = open(path, "rb").read()
        self.assertTrue(data.startswith(b"GIF89a"))
        self.assertEqual(struct.unpack("<HH", data[6:10]), (8, 6))
        self.assertTrue(data.endswith(b"\x3B"))
        self.assertIn(b"NETSCAPE2.0", data)
        pos = data.index(b"\x21\xF9\x04")
        frames = []
        while data[pos] == 0x21 and data[pos + 1] == 0xF9:
            (delay,) = struct.unpack("<H", data[pos + 4:pos + 6])
            self.assertEqual(data[pos + 3] & 0x01, 1)
            transparent = data[pos + 6]
            pos += 8
            self.assertEqual(data[pos], 0x2C)
            x, y, fw, fh, _ = struct.unpack("<HHHHB", data[pos + 1:pos + 10])
            pos += 10
            min_code = data[pos]
            pos += 1
            stream = bytearray()
            while data[pos]:
                stream += data[pos + 1:pos + 1 + data[pos]]
                pos += 1 + data[pos]
            pos += 1
            frames.append((delay, (x, y, fw, fh), lzw_decode(bytes(stream), min_code), transparent))
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0][0], 10)
        self.assertEqual(frames[0][1], (0, 0, 8, 6))
        self.assertEqual(frames[0][2], bytes(48))
        self.assertEqual(frames[1][0], 100)
        self.assertEqual(frames[1][1], (2, 3, 3, 2))
        self.assertEqual(frames[1][2], bytes([9] * 6))
        self.assertEqual(frames[1][3], len(PALETTE))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "b.gif")
            w = GifWriter(path, 4, 1)
            cv = Canvas(4, 1, 0)
            w.add_frame(cv, 5)
            cv.fill_rect(0, 0, 1, 1, 3)
            cv.fill_rect(3, 0, 1, 1, 5)
            w.add_frame(cv, 5)
            w.close()
            data = open(path, "rb").read()
        pos = data.rindex(b"\x2C")
        x, y, fw, fh, _ = struct.unpack("<HHHHB", data[pos + 1:pos + 10])
        self.assertEqual((x, y, fw, fh), (0, 0, 4, 1))
        stream = data[pos + 12:pos + 12 + data[pos + 11]]
        t = len(PALETTE)
        self.assertEqual(lzw_decode(stream, data[pos + 10]), bytes([3, t, t, 5]))


class RendererTest(unittest.TestCase):
    def test_font_shape(self):
        for ch, rows in FONT_3X5.items():
            self.assertEqual(len(rows), 5, ch)
            self.assertTrue(all(len(r) == 3 for r in rows), ch)

    def test_render_and_animate(self):
        maze = Maze.load(os.path.join(os.path.dirname(__file__), "..", "sim", "mazes", "loop8.txt"))
        result = run(maze, make_strategy("flood_fill"), trace=True)
        with tempfile.TemporaryDirectory() as tmp:
            gif, png = os.path.join(tmp, "x.gif"), os.path.join(tmp, "x.png")
            info = animate(maze, result, gif_path=gif, png_path=png, cell=16, every=2)
            self.assertGreater(info["frames"], 5)
            self.assertGreater(os.path.getsize(gif), 100)
            self.assertGreater(os.path.getsize(png), 50)
        r = Renderer(maze, cell=20)
        cv = r.render((0, 0, 0), visited={(0, 1): "EXPLORE"}, text="TEST")
        self.assertEqual(len(cv.buf), r.width * r.height)
        self.assertIn(9, cv.buf)
        self.assertIn(2, cv.buf)

    def test_ascii(self):
        maze = generate(4, seed=1)
        text = render_ascii(maze, (0, 0, 1), visited={(0, 1)})
        lines = text.splitlines()
        self.assertEqual(len(lines), 9)
        self.assertIn(">", lines[-2])
        self.assertIn(".", lines[-4])
        self.assertIn("G", text)


if __name__ == "__main__":
    unittest.main()
