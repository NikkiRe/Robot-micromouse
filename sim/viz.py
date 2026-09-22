import os
import struct
import zlib
from typing import Iterable, Sequence

from .maze import DIR_CHARS, DX, DY, EAST, INF, NORTH, SOUTH, WEST, Maze, left_of, right_of
from .robot import Sensors
from .simulate import RunResult
from .strategies import PHASE_EXPLORE, PHASE_RETURN, PHASE_SPEED


PALETTE: list[tuple[int, int, int]] = [
    (0x1B, 0x1B, 0x24),
    (0x27, 0x27, 0x36),
    (0x2E, 0x52, 0x80),
    (0x5C, 0x3F, 0x80),
    (0x8C, 0x7A, 0x1E),
    (0x1F, 0x5E, 0x38),
    (0x3C, 0x3C, 0x6C),
    (0xF2, 0xEC, 0xD8),
    (0x4C, 0x4A, 0x60),
    (0xFF, 0x7A, 0x2A),
    (0xFF, 0xF2, 0xA6),
    (0xB4, 0xBC, 0xCC),
    (0xFF, 0xFF, 0xFF),
    (0xE4, 0x44, 0x44),
    (0x44, 0xE0, 0x74),
    (0x70, 0x70, 0x84),
]
C_BG, C_CELL, C_EXPLORE, C_RETURN, C_SPEED, C_GOAL, C_START, C_WALL, C_WALL_DIM = range(9)
C_BODY, C_ARROW, C_DIGIT, C_TEXT, C_SENS_WALL, C_SENS_FREE, C_POST = range(9, 16)

PHASE_COLORS = {PHASE_EXPLORE: C_EXPLORE, PHASE_RETURN: C_RETURN, PHASE_SPEED: C_SPEED}


_FONT_SRC = {
    "0": "### #.# #.# #.# ###", "1": ".#. ##. .#. .#. ###", "2": "### ..# ### #.. ###",
    "3": "### ..# ### ..# ###", "4": "#.# #.# ### ..# ..#", "5": "### #.. ### ..# ###",
    "6": "### #.. ### #.# ###", "7": "### ..# ..# ..# ..#", "8": "### #.# ### #.# ###",
    "9": "### #.# ### ..# ###",
    "A": ".#. #.# ### #.# #.#", "B": "##. #.# ##. #.# ##.", "C": "### #.. #.. #.. ###",
    "D": "##. #.# #.# #.# ##.", "E": "### #.. ##. #.. ###", "F": "### #.. ##. #.. #..",
    "G": "### #.. #.# #.# ###", "H": "#.# #.# ### #.# #.#", "I": "### .#. .#. .#. ###",
    "J": "..# ..# ..# #.# ###", "K": "#.# #.# ##. #.# #.#", "L": "#.. #.. #.. #.. ###",
    "M": "#.# ### ### #.# #.#", "N": "##. #.# #.# #.# #.#", "O": "### #.# #.# #.# ###",
    "P": "### #.# ### #.. #..", "Q": "### #.# #.# ### ..#", "R": "##. #.# ##. #.# #.#",
    "S": "### #.. ### ..# ###", "T": "### .#. .#. .#. .#.", "U": "#.# #.# #.# #.# ###",
    "V": "#.# #.# #.# #.# .#.", "W": "#.# #.# ### ### #.#", "X": "#.# #.# .#. #.# #.#",
    "Y": "#.# #.# .#. .#. .#.", "Z": "### ..# .#. #.. ###",
    ":": "... .#. ... .#. ...", "-": "... ... ### ... ...", ".": "... ... ... ... .#.",
    "/": "..# ..# .#. #.. #..", "_": "... ... ... ... ###", "%": "#.# ..# .#. #.. #.#",
    "=": "... ### ... ### ...", "?": "### ..# .#. ... .#.", " ": "... ... ... ... ...",
}
FONT_3X5: dict[str, list[str]] = {ch: rows.split(" ") for ch, rows in _FONT_SRC.items()}


class Canvas:
    def __init__(self, width: int, height: int, color: int = 0):
        self.width = width
        self.height = height
        self.buf = bytearray([color]) * (width * height)

    def copy(self) -> "Canvas":
        c = Canvas.__new__(Canvas)
        c.width, c.height, c.buf = self.width, self.height, bytearray(self.buf)
        return c

    def fill_rect(self, x: int, y: int, w: int, h: int, color: int):
        x0, y0 = max(x, 0), max(y, 0)
        x1, y1 = min(x + w, self.width), min(y + h, self.height)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes([color]) * (x1 - x0)
        stride = self.width
        for yy in range(y0, y1):
            off = yy * stride + x0
            self.buf[off:off + (x1 - x0)] = row

    def blit_sprite(self, x: int, y: int, sprite: Sequence[str], colors: dict[str, int]):
        for dy, row in enumerate(sprite):
            yy = y + dy
            if not 0 <= yy < self.height:
                continue
            for dx, ch in enumerate(row):
                color = colors.get(ch)
                if color is None:
                    continue
                xx = x + dx
                if 0 <= xx < self.width:
                    self.buf[yy * self.width + xx] = color

    def text(self, x: int, y: int, s: str, color: int, scale: int = 1) -> int:
        for ch in s.upper():
            glyph = FONT_3X5.get(ch, FONT_3X5["?"])
            for dy, row in enumerate(glyph):
                for dx, bit in enumerate(row):
                    if bit == "#":
                        self.fill_rect(x + dx * scale, y + dy * scale, scale, scale, color)
            x += 4 * scale
        return x


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode_png(canvas: Canvas, palette: Sequence[tuple[int, int, int]] = PALETTE) -> bytes:
    w, h = canvas.width, canvas.height
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += canvas.buf[y * w:(y + 1) * w]
    plte = b"".join(bytes(c) for c in palette)
    return b"".join([
        b"\x89PNG\r\n\x1a\n",
        _png_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 3, 0, 0, 0)),
        _png_chunk(b"PLTE", plte),
        _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9)),
        _png_chunk(b"IEND", b""),
    ])


def write_png(path: str, canvas: Canvas, palette: Sequence[tuple[int, int, int]] = PALETTE):
    with open(path, "wb") as f:
        f.write(encode_png(canvas, palette))


# GIF89a, таблица кодов до 4096, сброс по переполнению
def lzw_encode(data: bytes, min_code_size: int) -> bytes:
    clear = 1 << min_code_size
    eoi = clear + 1
    out = bytearray()
    acc = 0
    nbits = 0

    def emit(code: int, size: int):
        nonlocal acc, nbits
        acc |= code << nbits
        nbits += size
        while nbits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            nbits -= 8

    code_size = min_code_size + 1
    table: dict[int, int] = {}
    next_code = eoi + 1
    emit(clear, code_size)
    if not data:
        emit(eoi, code_size)
    else:
        prefix = data[0]
        for k in data[1:]:
            key = (prefix << 8) | k
            code = table.get(key)
            if code is not None:
                prefix = code
                continue
            emit(prefix, code_size)
            if next_code < 4096:
                table[key] = next_code
                next_code += 1
                if next_code - 1 == (1 << code_size) and code_size < 12:
                    code_size += 1
            else:
                emit(clear, code_size)
                table.clear()
                next_code = eoi + 1
                code_size = min_code_size + 1
            prefix = k
        emit(prefix, code_size)
        emit(eoi, code_size)
    if nbits:
        out.append(acc & 0xFF)
    return bytes(out)


def _sub_blocks(data: bytes) -> bytes:
    parts = [bytes([len(data[i:i + 255])]) + data[i:i + 255] for i in range(0, len(data), 255)]
    return b"".join(parts) + b"\x00"


class GifWriter:
    def __init__(
        self,
        path: str,
        width: int,
        height: int,
        palette: Sequence[tuple[int, int, int]] = PALETTE,
        loop: int = 0,
    ):
        if not 2 <= len(palette) <= 255:
            raise ValueError("палитра должна содержать от 2 до 255 цветов")
        self.width, self.height = width, height
        self.frames = 0
        self._file = open(path, "wb")
        self._transparent = len(palette)
        bits = max(2, len(palette).bit_length())
        self._min_code_size = bits
        table = b"".join(bytes(c) for c in palette) + b"\x00\x00\x00" * ((1 << bits) - len(palette))
        self._file.write(b"GIF89a")
        self._file.write(struct.pack("<HHBBB", width, height, 0x80 | (7 << 4) | (bits - 1), 0, 0))
        self._file.write(table)
        self._file.write(b"\x21\xFF\x0BNETSCAPE2.0\x03\x01" + struct.pack("<H", loop) + b"\x00")
        self._prev: bytearray | None = None
        self._pending: tuple[tuple[int, int, int, int], bytes, int] | None = None

    def _diff_bbox(self, cur: bytearray) -> tuple[int, int, int, int] | None:
        prev, w = self._prev, self.width
        if prev is None:
            return 0, 0, self.width, self.height
        rows = [y for y in range(self.height) if prev[y * w:(y + 1) * w] != cur[y * w:(y + 1) * w]]
        if not rows:
            return None
        x0, x1 = w, -1
        for y in rows:
            a, b = prev[y * w:(y + 1) * w], cur[y * w:(y + 1) * w]
            for i in range(x0):
                if a[i] != b[i]:
                    x0 = i
                    break
            for i in range(w - 1, x1, -1):
                if a[i] != b[i]:
                    x1 = i
                    break
        return x0, rows[0], x1 - x0 + 1, rows[-1] - rows[0] + 1

    def add_frame(self, canvas: Canvas, delay: int = 5):
        cur = canvas.buf
        bbox = self._diff_bbox(cur)
        if bbox is None:
            if self._pending is not None:
                b, d, dl = self._pending
                self._pending = (b, d, dl + delay)
            return
        self._flush()
        x, y, w, h = bbox
        prev, stride, t = self._prev, self.width, self._transparent
        blank = bytes([t]) * w
        region = bytearray()
        for yy in range(y, y + h):
            off = yy * stride + x
            row = cur[off:off + w]
            if prev is None:
                region += row
                continue
            old = prev[off:off + w]
            if old == row:
                region += blank
            else:
                region += bytes(t if a == b else b for a, b in zip(old, row))
        self._pending = (bbox, lzw_encode(bytes(region), self._min_code_size), delay)
        self._prev = bytearray(cur)

    def _flush(self):
        if self._pending is None:
            return
        (x, y, w, h), data, delay = self._pending
        f = self._file
        f.write(b"\x21\xF9\x04" + bytes([0x04 | 0x01]) + struct.pack("<H", delay) + bytes([self._transparent, 0]))
        f.write(b"\x2C" + struct.pack("<HHHHB", x, y, w, h, 0))
        f.write(bytes([self._min_code_size]) + _sub_blocks(data))
        self.frames += 1
        self._pending = None

    def close(self, last_delay: int | None = None):
        if self._pending is not None and last_delay is not None:
            b, d, _ = self._pending
            self._pending = (b, d, last_delay)
        self._flush()
        self._file.write(b"\x3B")
        self._file.close()


ROBOT_SPRITE_NORTH = [
    ".....A.....",
    "....AAA....",
    "...AAAAA...",
    "..AAAAAAA..",
    ".AAA.A.AAA.",
    "...BBBBB...",
    "...BBBBB...",
    "...BBBBB...",
    "...BBBBB...",
    "...BBBBB...",
    "..BBBBBBB..",
]


def _rotate_cw(sprite: Sequence[str]) -> list[str]:
    h, w = len(sprite), len(sprite[0])
    return ["".join(sprite[h - 1 - x][y] for x in range(h)) for y in range(w)]


ROBOT_SPRITES = [ROBOT_SPRITE_NORTH]
for _ in range(3):
    ROBOT_SPRITES.append(_rotate_cw(ROBOT_SPRITES[-1]))


class Renderer:
    def __init__(
        self,
        maze: Maze,
        *,
        cell: int = 20,
        wall: int = 3,
        margin: int = 6,
        status: int = 14,
        dim_true_walls: bool = False,
    ):
        if not 8 <= cell <= 64:
            raise ValueError("размер клетки должен быть от 8 до 64 px")
        self.maze = maze
        self.cell = cell
        self.wall = wall
        self.half = wall // 2
        self.margin = margin
        self.status = status
        self.dim_true_walls = dim_true_walls
        self.inner = cell - wall
        n = maze.n
        self.width = 2 * margin + n * cell + wall
        self.height = 2 * margin + n * cell + wall + status
        self._base = self._make_base()

    def line_x(self, i: int) -> int:
        return self.margin + self.half + i * self.cell

    def line_y(self, j: int) -> int:
        return self.margin + self.half + j * self.cell

    def cell_origin(self, x: int, y: int) -> tuple[int, int]:
        return self.line_x(x) + self.half + 1, self.line_y(self.maze.n - 1 - y) + self.half + 1

    def _draw_wall(self, cv: Canvas, x: int, y: int, d: int, color: int):
        j = self.maze.n - 1 - y
        if d == NORTH:
            cv.fill_rect(self.line_x(x) - self.half, self.line_y(j) - self.half, self.cell + self.wall, self.wall, color)
        elif d == SOUTH:
            cv.fill_rect(self.line_x(x) - self.half, self.line_y(j + 1) - self.half, self.cell + self.wall, self.wall, color)
        elif d == WEST:
            cv.fill_rect(self.line_x(x) - self.half, self.line_y(j) - self.half, self.wall, self.cell + self.wall, color)
        else:
            cv.fill_rect(self.line_x(x + 1) - self.half, self.line_y(j) - self.half, self.wall, self.cell + self.wall, color)

    def draw_walls(self, cv: Canvas, has_wall, color: int):
        n = self.maze.n
        for y in range(n):
            for x in range(n):
                if has_wall(x, y, NORTH):
                    self._draw_wall(cv, x, y, NORTH, color)
                if has_wall(x, y, WEST):
                    self._draw_wall(cv, x, y, WEST, color)
                if y == 0 and has_wall(x, y, SOUTH):
                    self._draw_wall(cv, x, y, SOUTH, color)
                if x == n - 1 and has_wall(x, y, EAST):
                    self._draw_wall(cv, x, y, EAST, color)

    def _make_base(self) -> Canvas:
        cv = Canvas(self.width, self.height, C_BG)
        n = self.maze.n
        for y in range(n):
            for x in range(n):
                color = C_GOAL if (x, y) in self.maze.goals else C_START if (x, y) == self.maze.start else C_CELL
                px, py = self.cell_origin(x, y)
                cv.fill_rect(px, py, self.inner, self.inner, color)
        for i in range(n + 1):
            for j in range(n + 1):
                cv.fill_rect(self.line_x(i) - self.half, self.line_y(j) - self.half, self.wall, self.wall, C_POST)
        self.draw_walls(cv, self.maze.has_wall, C_WALL_DIM if self.dim_true_walls else C_WALL)
        return cv

    def render(
        self,
        pose: tuple[int, int, int] | None = None,
        *,
        visited: dict[tuple[int, int], str] | None = None,
        dist: Sequence[Sequence[int]] | None = None,
        known: Sequence[Sequence[int]] | None = None,
        sensors: Sensors | None = None,
        text: str = "",
    ) -> Canvas:
        cv = self._base.copy()
        n = self.maze.n
        if visited:
            for (x, y), phase in visited.items():
                if (x, y) in self.maze.goals or (x, y) == self.maze.start:
                    continue
                px, py = self.cell_origin(x, y)
                cv.fill_rect(px, py, self.inner, self.inner, PHASE_COLORS.get(phase, C_EXPLORE))
        if known is not None:
            self.draw_walls(cv, lambda x, y, d: bool(known[y][x] & (1 << d)), C_WALL)
        if dist is not None and self.cell >= 14:
            for y in range(n):
                for x in range(n):
                    v = dist[y][x]
                    if v >= INF:
                        continue
                    px, py = self.cell_origin(x, y)
                    cv.text(px + 1, py + 1, str(v), C_DIGIT)
        if pose is not None:
            x, y, h = pose
            px, py = self.cell_origin(x, y)
            sprite = ROBOT_SPRITES[h]
            size = len(sprite)
            ox, oy = px + (self.inner - size) // 2, py + (self.inner - size) // 2
            cv.blit_sprite(ox, oy, sprite, {"A": C_ARROW, "B": C_BODY})
            if sensors is not None:
                for d, seen in ((h, sensors.front), (left_of(h), sensors.left), (right_of(h), sensors.right)):
                    self._draw_sensor(cv, px, py, d, C_SENS_WALL if seen else C_SENS_FREE)
        if text and self.status >= 7:
            cv.fill_rect(0, self.height - self.status, self.width, self.status, C_BG)
            cv.text(self.margin, self.height - self.status + (self.status - 5) // 2, text, C_TEXT)
        return cv

    def _draw_sensor(self, cv: Canvas, px: int, py: int, d: int, color: int):
        c = self.inner // 2 - 1
        if d == NORTH:
            cv.fill_rect(px + c, py, 3, 2, color)
        elif d == SOUTH:
            cv.fill_rect(px + c, py + self.inner - 2, 3, 2, color)
        elif d == WEST:
            cv.fill_rect(px, py + c, 2, 3, color)
        else:
            cv.fill_rect(px + self.inner - 2, py + c, 2, 3, color)


def render_ascii(
    maze: Maze,
    pose: tuple[int, int, int] | None = None,
    *,
    visited: Iterable[tuple[int, int]] | None = None,
    dist: Sequence[Sequence[int]] | None = None,
    known: Sequence[Sequence[int]] | None = None,
) -> str:
    n = maze.n
    visited = set(visited or ())

    def wall(x: int, y: int, d: int) -> bool:
        if known is None:
            return maze.has_wall(x, y, d)
        return bool(known[y][x] & (1 << d))

    def body(x: int, y: int) -> str:
        if pose is not None and (x, y) == (pose[0], pose[1]):
            return f" {DIR_CHARS[pose[2]]} "
        if dist is not None and dist[y][x] < INF:
            return f"{dist[y][x]:>3d}"
        if (x, y) in maze.goals:
            return " G "
        if (x, y) == maze.start:
            return " S "
        return " . " if (x, y) in visited else "   "

    lines = []
    for r in range(n):
        y = n - 1 - r
        lines.append("+" + "".join(("---" if wall(x, y, NORTH) else "   ") + "+" for x in range(n)))
        row = ""
        for x in range(n):
            row += ("|" if wall(x, y, WEST) else " ") + body(x, y)
        lines.append(row + ("|" if wall(n - 1, y, EAST) else " "))
    lines.append("+" + "".join(("---" if wall(x, 0, SOUTH) else "   ") + "+" for x in range(n)))
    return "\n".join(lines)


def replay_frames(result: RunResult):
    visited: dict[tuple[int, int], str] = {}
    dist = known = None
    for frame in result.frames:
        if frame.dist is not None:
            dist = frame.dist
        if frame.known is not None:
            known = frame.known
        visited[(frame.pose[0], frame.pose[1])] = frame.phase
        yield frame, dict(visited), dist, known


def status_line(result: RunResult, frame) -> str:
    return f"{result.strategy} {frame.phase} STEP {frame.steps} TURN {frame.turns} U {frame.uturns} T {frame.time:.1f}"


def animate(
    maze: Maze,
    result: RunResult,
    *,
    gif_path: str | None = None,
    png_path: str | None = None,
    cell: int = 20,
    every: int = 1,
    delay: int = 6,
    max_frames: int | None = None,
) -> dict:
    if not result.frames:
        raise ValueError("в результате нет трассы: запустите run(..., trace=True)")
    has_map = any(f.dist is not None for f in result.frames)
    renderer = Renderer(maze, cell=cell, dim_true_walls=has_map)
    writer = GifWriter(gif_path, renderer.width, renderer.height) if gif_path else None
    frames = list(replay_frames(result))
    last_index = len(frames) - 1
    chosen = [i for i in range(len(frames)) if i % max(1, every) == 0 or i == last_index]
    if max_frames is not None and len(chosen) > max_frames:
        step = len(chosen) / max_frames
        chosen = [chosen[int(i * step)] for i in range(max_frames)]
        if chosen[-1] != last_index:
            chosen.append(last_index)
    canvas = None
    for i in chosen:
        frame, visited, dist, known = frames[i]
        canvas = renderer.render(
            frame.pose, visited=visited, dist=dist, known=known,
            sensors=frame.sensors, text=status_line(result, frame),
        )
        if writer is not None:
            writer.add_frame(canvas, delay)
    info = {"frames": len(chosen), "width": renderer.width, "height": renderer.height}
    if writer is not None:
        writer.close(last_delay=200)
        info["gif_bytes"] = os.path.getsize(gif_path)
    if png_path and canvas is not None:
        write_png(png_path, canvas)
        info["png_bytes"] = os.path.getsize(png_path)
    return info
