import random
from collections import deque
from typing import Callable, Iterable, Iterator

NORTH, EAST, SOUTH, WEST = 0, 1, 2, 3
DX = (0, 1, 0, -1)
DY = (1, 0, -1, 0)
DIR_NAMES = ("N", "E", "S", "W")
DIR_CHARS = "^>v<"

INF = 10 ** 9

Cell = tuple[int, int]
Edge = tuple[int, int, int]


def opposite(d: int) -> int:
    return (d + 2) & 3


def left_of(d: int) -> int:
    return (d + 3) & 3


def right_of(d: int) -> int:
    return (d + 1) & 3


def default_goals(n: int) -> frozenset[Cell]:
    c = n // 2
    if n % 2 == 0:
        return frozenset((x, y) for x in (c - 1, c) for y in (c - 1, c))
    return frozenset({(c, c)})


class Maze:
    def __init__(
        self,
        n: int = 16,
        *,
        start: Cell = (0, 0),
        goals: Iterable[Cell] | None = None,
        walls_everywhere: bool = False,
    ):
        if n < 2:
            raise ValueError("размер лабиринта должен быть не меньше 2")
        self.n = n
        self.start: Cell = (int(start[0]), int(start[1]))
        self.goals: frozenset[Cell] = (
            frozenset(tuple(g) for g in goals) if goals is not None else default_goals(n)
        )
        fill = 0b1111 if walls_everywhere else 0
        self._walls = [[fill] * n for _ in range(n)]
        if not walls_everywhere:
            for i in range(n):
                self._walls[0][i] |= 1 << SOUTH
                self._walls[n - 1][i] |= 1 << NORTH
                self._walls[i][0] |= 1 << WEST
                self._walls[i][n - 1] |= 1 << EAST


    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.n and 0 <= y < self.n

    def has_wall(self, x: int, y: int, d: int) -> bool:
        return bool(self._walls[y][x] & (1 << d))

    def cell_mask(self, x: int, y: int) -> int:
        return self._walls[y][x]

    def set_wall(self, x: int, y: int, d: int, present: bool = True):
        nx, ny = x + DX[d], y + DY[d]
        if not self.in_bounds(nx, ny):
            if not present:
                raise ValueError(f"внешнюю стену клетки {(x, y)} снять нельзя")
            self._walls[y][x] |= 1 << d
            return
        bit, obit = 1 << d, 1 << opposite(d)
        if present:
            self._walls[y][x] |= bit
            self._walls[ny][nx] |= obit
        else:
            self._walls[y][x] &= ~bit
            self._walls[ny][nx] &= ~obit

    def passable(self, x: int, y: int, d: int) -> bool:
        return self.in_bounds(x + DX[d], y + DY[d]) and not self.has_wall(x, y, d)

    def neighbors(self, x: int, y: int) -> Iterator[Cell]:
        for d in range(4):
            if self.passable(x, y, d):
                yield x + DX[d], y + DY[d]

    def cells(self) -> Iterator[Cell]:
        for y in range(self.n):
            for x in range(self.n):
                yield x, y

    def internal_edges(self) -> list[Edge]:
        edges: list[Edge] = []
        for x, y in self.cells():
            if y + 1 < self.n:
                edges.append((x, y, NORTH))
            if x + 1 < self.n:
                edges.append((x, y, EAST))
        return edges

    def fill_walls(self):
        for row in self._walls:
            for x in range(self.n):
                row[x] = 0b1111

    def copy(self) -> "Maze":
        m = Maze(self.n, start=self.start, goals=self.goals)
        m._walls = [row[:] for row in self._walls]
        return m

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Maze):
            return NotImplemented
        return (
            self.n == other.n
            and self.start == other.start
            and self.goals == other.goals
            and self._walls == other._walls
        )

    def __hash__(self) -> int:
        raise TypeError("Maze нельзя хешировать")


    def bfs(
        self,
        targets: Iterable[Cell],
        *,
        allowed: Callable[[int, int], bool] | None = None,
    ) -> list[list[int]]:
        n = self.n
        dist = [[INF] * n for _ in range(n)]
        queue: deque[Cell] = deque()
        for x, y in targets:
            dist[y][x] = 0
            queue.append((x, y))
        while queue:
            x, y = queue.popleft()
            nd = dist[y][x] + 1
            mask = self._walls[y][x]
            for d in range(4):
                if mask & (1 << d):
                    continue
                nx, ny = x + DX[d], y + DY[d]
                if dist[ny][nx] != INF:
                    continue
                if allowed is not None and not allowed(nx, ny):
                    continue
                dist[ny][nx] = nd
                queue.append((nx, ny))
        return dist

    def shortest_path(
        self,
        start: Cell,
        targets: Iterable[Cell],
        *,
        allowed: Callable[[int, int], bool] | None = None,
    ) -> list[Cell] | None:
        targets = set(targets)
        dist = self.bfs(targets, allowed=allowed)
        x, y = start
        if dist[y][x] == INF:
            return None
        path = [(x, y)]
        while (x, y) not in targets:
            for d in range(4):
                if self.has_wall(x, y, d):
                    continue
                nx, ny = x + DX[d], y + DY[d]
                if dist[ny][nx] == dist[y][x] - 1:
                    x, y = nx, ny
                    path.append((x, y))
                    break
            else:
                raise RuntimeError("не удалось спуститься по расстояниям")
        return path

    def shortest_len(self) -> int | None:
        path = self.shortest_path(self.start, self.goals)
        return None if path is None else len(path) - 1

    def is_connected(self) -> bool:
        dist = self.bfs([self.start])
        return all(dist[y][x] != INF for x, y in self.cells())


    def to_text(self) -> str:
        n = self.n
        lines: list[str] = []
        for r in range(n):
            y = n - 1 - r
            lines.append(
                "+" + "".join(("---" if self.has_wall(x, y, NORTH) else "   ") + "+" for x in range(n))
            )
            body = ""
            for x in range(n):
                body += "|" if self.has_wall(x, y, WEST) else " "
                mark = "S" if (x, y) == self.start else "G" if (x, y) in self.goals else " "
                body += f" {mark} "
            body += "|" if self.has_wall(n - 1, y, EAST) else " "
            lines.append(body)
        lines.append("+" + "".join(("---" if self.has_wall(x, 0, SOUTH) else "   ") + "+" for x in range(n)))
        return "\n".join(lines) + "\n"

    @classmethod
    def from_text(cls, text: str) -> "Maze":
        lines = [ln.rstrip("\n") for ln in text.splitlines()]
        lines = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
        if not lines:
            raise ValueError("пустой лабиринт")
        n = (len(lines[0].rstrip()) - 1) // 4
        if n < 2 or len(lines) != 2 * n + 1:
            raise ValueError(f"ожидалось {2 * n + 1} строк для лабиринта {n}×{n}, получено {len(lines)}")
        width = 4 * n + 1
        lines = [ln.ljust(width) for ln in lines]
        start: Cell | None = None
        goals: set[Cell] = set()
        maze = cls(n, walls_everywhere=True)
        maze.fill_walls()
        for r in range(n):
            y = n - 1 - r
            top, body = lines[2 * r], lines[2 * r + 1]
            for x in range(n):
                if y + 1 < n and top[4 * x + 2] != "-":
                    maze.set_wall(x, y, NORTH, False)
                if x > 0 and body[4 * x] != "|":
                    maze.set_wall(x, y, WEST, False)
                mark = body[4 * x + 2]
                if mark == "S":
                    start = (x, y)
                elif mark == "G":
                    goals.add((x, y))
        maze.start = start if start is not None else (0, 0)
        maze.goals = frozenset(goals) if goals else default_goals(n)
        return maze

    def save(self, path: str, comment: str | None = None):
        with open(path, "w", encoding="utf-8") as f:
            if comment:
                for line in comment.splitlines():
                    f.write(f"# {line}\n")
            f.write(self.to_text())

    @classmethod
    def load(cls, path: str) -> "Maze":
        with open(path, encoding="utf-8") as f:
            return cls.from_text(f.read())

    def __str__(self) -> str:
        return self.to_text()


def carve_tree(maze: Maze, cells: Iterable[Cell], start: Cell, rng: random.Random):
    area = set(cells)
    if start not in area:
        raise ValueError("стартовая клетка не входит в область")
    visited = {start}
    stack = [start]
    while stack:
        x, y = stack[-1]
        options = [
            d for d in range(4) if (x + DX[d], y + DY[d]) in area and (x + DX[d], y + DY[d]) not in visited
        ]
        if not options:
            stack.pop()
            continue
        d = rng.choice(options)
        maze.set_wall(x, y, d, False)
        nxt = (x + DX[d], y + DY[d])
        visited.add(nxt)
        stack.append(nxt)


def open_goal_area(maze: Maze):
    for x, y in maze.goals:
        for d in range(4):
            if (x + DX[d], y + DY[d]) in maze.goals:
                maze.set_wall(x, y, d, False)


def generate(n: int = 16, seed: int | None = None, loops: int = 0, open_goal: bool = True) -> Maze:
    rng = random.Random(seed)
    maze = Maze(n, walls_everywhere=True)
    carve_tree(maze, maze.cells(), maze.start, rng)
    if open_goal:
        open_goal_area(maze)
    candidates = [e for e in maze.internal_edges() if maze.has_wall(*e)]
    rng.shuffle(candidates)
    for edge in candidates[: max(0, loops)]:
        maze.set_wall(*edge, False)
    return maze
