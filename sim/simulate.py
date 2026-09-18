import random
from dataclasses import dataclass, field

from .maze import Cell, Maze
from .robot import Robot, Sensors
from .strategies import PHASE_SPEED, Action, Strategy

Pose = tuple[int, int, int]


@dataclass
class Frame:
    index: int
    pose: Pose
    action: Action | None
    ok: bool
    sensors: Sensors | None
    phase: str
    steps: int
    turns: int
    uturns: int
    bumps: int
    time: float
    dist: tuple | None = None
    known: tuple | None = None


@dataclass
class RunResult:
    strategy: str
    size: int
    max_steps: int
    solved: bool = False
    finished: bool = False
    steps_to_goal: int | None = None
    turns_to_goal: int | None = None
    uturns_to_goal: int | None = None
    bumps_to_goal: int | None = None
    time_to_goal: float | None = None
    total_steps: int = 0
    total_turns: int = 0
    total_uturns: int = 0
    total_bumps: int = 0
    total_time: float = 0.0
    speed_len: int | None = None
    speed_turns: int | None = None
    speed_time: float | None = None
    optimum: int | None = None
    explore_runs: int = 0
    phase: str = ""
    visited: set[Cell] = field(default_factory=set)
    frames: list[Frame] = field(default_factory=list)

    @property
    def speed_ratio(self) -> float | None:
        if self.speed_len is None or not self.optimum:
            return None
        return self.speed_len / self.optimum


def apply(robot: Robot, action: Action) -> bool:
    if action is Action.FORWARD:
        return robot.forward()
    if action is Action.LEFT:
        robot.turn_left()
    elif action is Action.RIGHT:
        robot.turn_right()
    elif action is Action.AROUND:
        robot.turn_around()
    return True


def _snapshot(grid) -> tuple:
    return tuple(tuple(row) for row in grid)


def run(
    maze: Maze,
    strategy: Strategy,
    *,
    max_steps: int | None = None,
    noise: float = 0.0,
    seed: int = 0,
    trace: bool = False,
    robot_kwargs: dict | None = None,
    reset_strategy: bool = True,
) -> RunResult:
    n = maze.n
    if max_steps is None:
        max_steps = 4 * n * n
    total_budget = 3 * max_steps
    action_budget = 4 * total_budget

    robot = Robot(maze, noise=noise, rng=random.Random(seed), **(robot_kwargs or {}))
    if reset_strategy:
        strategy.reset(n, maze.start, maze.goals)
    result = RunResult(strategy=strategy.name, size=n, max_steps=max_steps, optimum=maze.shortest_len())
    result.visited.add(robot.cell)

    speed_steps = speed_turns = 0
    speed_time = 0.0
    speed_started = False
    last_version: int | None = None

    def snap(index: int, action: Action | None, ok: bool, sensors: Sensors | None):
        nonlocal last_version
        state = strategy.debug_state()
        dist = known = None
        if state.get("version") != last_version:
            last_version = state.get("version")
            if state.get("dist") is not None:
                dist = _snapshot(state["dist"])
            if state.get("known") is not None:
                known = _snapshot(state["known"]._walls)
        result.frames.append(
            Frame(
                index, robot.pose, action, ok, sensors, strategy.phase,
                robot.steps, robot.turns, robot.uturns, robot.bumps, robot.time, dist, known,
            )
        )

    if trace:
        snap(0, None, True, None)

    actions = 0
    goal_reached = False
    while True:
        if robot.at_goal and not goal_reached:
            goal_reached = True
            result.solved = robot.steps <= max_steps
            result.steps_to_goal = robot.steps
            result.turns_to_goal = robot.turns
            result.uturns_to_goal = robot.uturns
            result.bumps_to_goal = robot.bumps
            result.time_to_goal = robot.time
            if strategy.stops_at_goal:
                result.finished = True
                break
        if not goal_reached and robot.steps >= max_steps:
            break
        if robot.steps >= total_budget or actions >= action_budget:
            break

        sensors = robot.sense()
        action = strategy.decide(robot.pose, sensors)
        if action is Action.STOP:
            result.finished = True
            if trace:
                snap(actions + 1, action, True, sensors)
            break
        phase = strategy.phase
        before = (robot.steps, robot.turns, robot.time)
        ok = apply(robot, action)
        if not ok:
            strategy.on_bump(robot.pose)
        actions += 1
        result.visited.add(robot.cell)
        if phase == PHASE_SPEED:
            speed_started = True
            speed_steps += robot.steps - before[0]
            speed_turns += robot.turns - before[1]
            speed_time += robot.time - before[2]
        if trace:
            snap(actions, action, ok, sensors)

    result.total_steps = robot.steps
    result.total_turns = robot.turns
    result.total_uturns = robot.uturns
    result.total_bumps = robot.bumps
    result.total_time = robot.time
    result.phase = strategy.phase
    result.explore_runs = getattr(strategy, "explore_runs", 0)
    if speed_started and result.finished:
        result.speed_len = speed_steps
        result.speed_turns = speed_turns
        result.speed_time = speed_time
    return result
