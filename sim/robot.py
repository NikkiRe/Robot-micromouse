import random
from typing import NamedTuple

from .maze import DX, DY, NORTH, Maze, left_of, opposite, right_of


class Sensors(NamedTuple):
    front: bool
    left: bool
    right: bool


class Robot:
    def __init__(
        self,
        maze: Maze,
        *,
        x: int | None = None,
        y: int | None = None,
        heading: int = NORTH,
        noise: float = 0.0,
        rng: random.Random | None = None,
        cell_time: float = 1.0,
        turn_time: float = 0.5,
        uturn_time: float = 1.0,
        bump_time: float = 0.5,
    ):
        if not 0.0 <= noise < 1.0:
            raise ValueError("noise должен лежать в [0, 1)")
        self.maze = maze
        self.start = (maze.start[0] if x is None else x, maze.start[1] if y is None else y)
        self.start_heading = heading
        self.noise = noise
        self.rng = rng if rng is not None else random.Random(0)
        self.cell_time = cell_time
        self.turn_time = turn_time
        self.uturn_time = uturn_time
        self.bump_time = bump_time
        self.reset()

    def reset(self):
        self.x, self.y = self.start
        self.heading = self.start_heading
        self.steps = 0
        self.turns = 0
        self.uturns = 0
        self.bumps = 0
        self.time = 0.0


    @property
    def pose(self) -> tuple[int, int, int]:
        return self.x, self.y, self.heading

    @property
    def cell(self) -> tuple[int, int]:
        return self.x, self.y

    @property
    def at_goal(self) -> bool:
        return (self.x, self.y) in self.maze.goals


    def sense_true(self) -> Sensors:
        m, x, y, h = self.maze, self.x, self.y, self.heading
        return Sensors(m.has_wall(x, y, h), m.has_wall(x, y, left_of(h)), m.has_wall(x, y, right_of(h)))

    def sense(self) -> Sensors:
        true = self.sense_true()
        if self.noise <= 0.0:
            return true
        rnd = self.rng.random
        return Sensors(*(v ^ (rnd() < self.noise) for v in true))


    def forward(self) -> bool:
        if self.maze.has_wall(self.x, self.y, self.heading):
            self.bumps += 1
            self.time += self.bump_time
            return False
        self.x += DX[self.heading]
        self.y += DY[self.heading]
        self.steps += 1
        self.time += self.cell_time
        return True

    def turn_left(self):
        self.heading = left_of(self.heading)
        self.turns += 1
        self.time += self.turn_time

    def turn_right(self):
        self.heading = right_of(self.heading)
        self.turns += 1
        self.time += self.turn_time

    def turn_around(self):
        self.heading = opposite(self.heading)
        self.uturns += 1
        self.time += self.uturn_time

    def __repr__(self) -> str:
        return f"Robot(x={self.x}, y={self.y}, heading={self.heading}, steps={self.steps})"
