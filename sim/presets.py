import os
import random

from .maze import DX, DY, EAST, NORTH, SOUTH, WEST, Maze, carve_tree, generate, open_goal_area

MAZES_DIR = os.path.join(os.path.dirname(__file__), "mazes")


def _carve_path(maze: Maze, path: list[tuple[int, int]]):
    for (x, y), (nx, ny) in zip(path, path[1:]):
        for d in range(4):
            if (x + DX[d], y + DY[d]) == (nx, ny):
                maze.set_wall(x, y, d, False)
                break
        else:
            raise ValueError(f"клетки {(x, y)} и {(nx, ny)} не соседние")


def corridor5() -> Maze:
    maze = Maze(5, walls_everywhere=True)
    _carve_path(
        maze,
        [(0, 0), (0, 1), (1, 1), (2, 1), (2, 0), (3, 0), (4, 0), (4, 1), (4, 2), (3, 2), (2, 2)],
    )
    return maze


def loop8(seed: int = 1) -> Maze:
    n = 8
    rng = random.Random(seed)
    maze = Maze(n, walls_everywhere=True)
    ring = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (1, 2), (0, 2), (0, 1), (0, 0)]
    _carve_path(maze, ring)
    rest = set(maze.cells()) - set(ring) - {(1, 1)}
    carve_tree(maze, rest, (3, 1), rng)
    maze.set_wall(2, 1, EAST, False)
    open_goal_area(maze)
    return maze


def island16(seed: int = 3) -> Maze:
    n = 16
    rng = random.Random(seed)
    maze = Maze(n, walls_everywhere=True)
    lo, hi = 4, 11
    ring = {(x, y) for x in range(lo, hi + 1) for y in range(lo, hi + 1) if x in (lo, hi) or y in (lo, hi)}
    island = {(x, y) for x in range(lo + 1, hi) for y in range(lo + 1, hi)}
    outer = {(x, y) for x in range(n) for y in range(n)} - ring - island

    carve_tree(maze, outer, maze.start, rng)
    outer_edges = [
        (x, y, d) for x, y in outer for d in (NORTH, EAST)
        if (x + DX[d], y + DY[d]) in outer and maze.has_wall(x, y, d)
    ]
    rng.shuffle(outer_edges)
    for edge in outer_edges[:12]:
        maze.set_wall(*edge, False)

    for x, y in ring:
        for d in range(4):
            if (x + DX[d], y + DY[d]) in ring:
                maze.set_wall(x, y, d, False)
    maze.set_wall(lo, lo, WEST, False)
    maze.set_wall(hi, hi, NORTH, False)

    carve_tree(maze, island, (hi - 1, 7), rng)
    maze.set_wall(hi, 7, WEST, False)
    open_goal_area(maze)
    return maze


def random16() -> Maze:
    return generate(16, seed=7, loops=16)


PRESETS = {
    "corridor5": (corridor5, "5x5 коридор-змейка: стендовый тест, реактивный алгоритм проходит"),
    "loop8": (loop8, "8x8 кольцо: реактивный алгоритм зацикливается, правая рука и flood fill доходят"),
    "island16": (island16, "16x16 цель на острове: правило правой руки не находит цель"),
    "random16": (random16, "16x16 случайный лабиринт (seed 7, 16 циклов)"),
}


def write_all(directory: str = MAZES_DIR) -> list[str]:
    os.makedirs(directory, exist_ok=True)
    paths = []
    for name, (builder, comment) in PRESETS.items():
        path = os.path.join(directory, f"{name}.txt")
        builder().save(path, comment)
        paths.append(path)
    return paths


if __name__ == "__main__":
    for p in write_all():
        print(p)
