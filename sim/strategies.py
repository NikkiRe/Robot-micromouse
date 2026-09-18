from enum import Enum

from .maze import DX, DY, INF, Cell, Edge, Maze, left_of, opposite, right_of
from .robot import Sensors

Pose = tuple[int, int, int]


class Action(Enum):
    FORWARD = "F"
    LEFT = "L"
    RIGHT = "R"
    AROUND = "U"
    STOP = "."


PHASE_RUN = "RUN"
PHASE_EXPLORE = "EXPLORE"
PHASE_RETURN = "RETURN"
PHASE_SPEED = "SPEED_RUN"
PHASE_DONE = "DONE"


class Strategy:
    name = "base"
    stops_at_goal = True

    def __init__(self):
        self.phase = PHASE_RUN

    def reset(self, n: int, start: Cell, goals: frozenset[Cell]):
        self.phase = PHASE_RUN

    def decide(self, pose: Pose, sensors: Sensors) -> Action:
        raise NotImplementedError

    def on_bump(self, pose: Pose):
        pass

    def debug_state(self) -> dict:
        return {"version": 0, "dist": None, "known": None}


class Reactive(Strategy):
    # порядок проверок как в main.c базовой прошивки
    name = "reactive"

    def decide(self, pose: Pose, s: Sensors) -> Action:
        if not s.front:
            return Action.FORWARD
        if not s.left and s.right:
            return Action.LEFT
        if not s.right and s.left:
            return Action.RIGHT
        if not s.left and not s.right:
            return Action.RIGHT
        return Action.AROUND


class RightHand(Strategy):
    name = "right_hand"

    def __init__(self):
        super().__init__()
        self._step_pending = False

    def reset(self, n: int, start: Cell, goals: frozenset[Cell]):
        super().reset(n, start, goals)
        self._step_pending = False

    def decide(self, pose: Pose, s: Sensors) -> Action:
        # после поворота направо обязательно шаг, иначе крутится на месте
        if self._step_pending:
            self._step_pending = False
            if not s.front:
                return Action.FORWARD
        if not s.right:
            self._step_pending = True
            return Action.RIGHT
        if not s.front:
            return Action.FORWARD
        if not s.left:
            return Action.LEFT
        return Action.AROUND


CERTAIN = 1000


class FloodFill(Strategy):
    name = "flood_fill"
    stops_at_goal = False

    def __init__(self, max_explore_runs: int = 3):
        super().__init__()
        self.max_explore_runs = max_explore_runs
        self.n = 0
        self.start: Cell = (0, 0)
        self.goals: frozenset[Cell] = frozenset()
        self.known = Maze(2)
        self.votes: dict[Edge, list[int]] = {}
        self.visited: set[Cell] = set()
        self.targets: frozenset[Cell] = frozenset()
        self.allowed: set[Cell] | None = None
        self.dist: list[list[int]] | None = None
        self.level = 0
        self.version = 0
        self.explore_runs = 0
        self._last_cell: Cell | None = None

    def reset(self, n: int, start: Cell, goals: frozenset[Cell]):
        self.n = n
        self.start = start
        self.goals = goals
        self.known = Maze(n, start=start, goals=goals)
        self.votes = {}
        self.visited = set()
        self.phase = PHASE_EXPLORE
        self.targets = goals
        self.allowed = None
        self.dist = None
        self.level = 0
        self.version = 0
        self.explore_runs = 0
        self._last_cell = None


    def _edge(self, x: int, y: int, d: int) -> Edge | None:
        nx, ny = x + DX[d], y + DY[d]
        if not self.known.in_bounds(nx, ny):
            return None
        if d in (0, 1):
            return (x, y, d)
        return (nx, ny, opposite(d))

    def _is_wall(self, votes: list[int]) -> bool:
        wall, free = votes
        if self.level == 0:
            return wall > 0 and wall >= free
        if self.level == 1:
            return wall >= free + 2
        return wall >= CERTAIN and wall > free

    def _vote(self, x: int, y: int, d: int, wall: bool, weight: int = 1):
        edge = self._edge(x, y, d)
        if edge is None:
            return
        votes = self.votes.setdefault(edge, [0, 0])
        votes[0 if wall else 1] += weight
        present = self._is_wall(votes)
        if self.known.has_wall(*edge) != present:
            self.known.set_wall(*edge, present)
            self._invalidate()

    def _rebuild_known(self):
        for edge, votes in self.votes.items():
            self.known.set_wall(*edge, self._is_wall(votes))
        self._invalidate()

    def _invalidate(self):
        self.dist = None
        self.version += 1

    def _observe(self, x: int, y: int, h: int, s: Sensors):
        self._vote(x, y, h, s.front)
        self._vote(x, y, left_of(h), s.left)
        self._vote(x, y, right_of(h), s.right)

    def on_bump(self, pose: Pose):
        x, y, h = pose
        self._vote(x, y, h, True, CERTAIN)

    def load_full_map(self, maze: Maze):
        self.reset(maze.n, maze.start, maze.goals)
        for x, y, d in maze.internal_edges():
            self._vote(x, y, d, maze.has_wall(x, y, d), CERTAIN)
        self.visited = set(maze.cells())
        self.explore_runs = self.max_explore_runs
        self._start_speed_run()


    def _set_phase(self, phase: str, targets: frozenset[Cell], allowed: set[Cell] | None = None):
        self.phase = phase
        self.targets = targets
        self.allowed = allowed
        self.level = 0
        self._rebuild_known()

    def _start_speed_run(self):
        safe = self.known.shortest_path(self.start, self.goals, allowed=self._is_visited)
        self._set_phase(PHASE_SPEED, self.goals, set(self.visited) if safe is not None else None)

    def _is_visited(self, x: int, y: int) -> bool:
        return (x, y) in self.visited

    def _update_phase(self, cell: Cell):
        if self.phase == PHASE_EXPLORE and cell in self.goals:
            self.explore_runs += 1
            self._set_phase(PHASE_RETURN, frozenset({self.start}))
        elif self.phase == PHASE_RETURN and cell == self.start:
            safe = self.known.shortest_path(self.start, self.goals, allowed=self._is_visited)
            optimistic = self.known.shortest_path(self.start, self.goals)
            need_more = (
                safe is None or optimistic is None or len(optimistic) < len(safe)
            ) and self.explore_runs < self.max_explore_runs
            if need_more:
                self._set_phase(PHASE_EXPLORE, self.goals)
            else:
                self._start_speed_run()
        elif self.phase == PHASE_SPEED and cell in self.goals:
            self.phase = PHASE_DONE


    def _ensure_dist(self) -> list[list[int]]:
        if self.dist is None:
            allowed = None
            if self.allowed is not None:
                allowed_set = self.allowed

                def allowed(x: int, y: int) -> bool:
                    return (x, y) in allowed_set

            self.dist = self.known.bfs(self.targets, allowed=allowed)
        return self.dist

    def _choose_direction(self, x: int, y: int, h: int) -> int | None:
        while True:
            dist = self._ensure_dist()
            best_d, best = None, INF
            for d in (h, right_of(h), left_of(h), opposite(h)):
                if self.known.has_wall(x, y, d):
                    continue
                nx, ny = x + DX[d], y + DY[d]
                if self.allowed is not None and (nx, ny) not in self.allowed and (nx, ny) not in self.targets:
                    continue
                if dist[ny][nx] < best:
                    best, best_d = dist[ny][nx], d
            if best_d is not None:
                return best_d
            if self.level >= 2:
                return None
            self.level += 1
            self._rebuild_known()

    def decide(self, pose: Pose, s: Sensors) -> Action:
        x, y, h = pose
        cell = (x, y)
        if self._last_cell is not None and cell != self._last_cell:
            self._vote(x, y, opposite(h), False, CERTAIN)
        self._last_cell = cell
        self.visited.add(cell)
        self._observe(x, y, h, s)
        self._update_phase(cell)
        if self.phase == PHASE_DONE:
            return Action.STOP
        d = self._choose_direction(x, y, h)
        if d is None:
            return Action.AROUND
        if d == h:
            return Action.FORWARD
        if d == right_of(h):
            return Action.RIGHT
        if d == left_of(h):
            return Action.LEFT
        return Action.AROUND

    def debug_state(self) -> dict:
        return {"version": self.version, "dist": self.dist, "known": self.known, "phase": self.phase}


STRATEGIES: dict[str, type[Strategy]] = {
    Reactive.name: Reactive,
    RightHand.name: RightHand,
    FloodFill.name: FloodFill,
}


def make_strategy(name: str) -> Strategy:
    try:
        return STRATEGIES[name]()
    except KeyError:
        raise ValueError(f"неизвестная стратегия {name!r}; доступны: {', '.join(STRATEGIES)}") from None
