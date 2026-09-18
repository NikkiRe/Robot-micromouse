import os
import unittest

from sim.bench import _fmt, bench, maze_seed
from sim.maze import Maze, generate
from sim.robot import Sensors
from sim.simulate import run
from sim.strategies import Action, FloodFill, Reactive, RightHand, make_strategy

MAZES = os.path.join(os.path.dirname(__file__), "..", "sim", "mazes")


def load(name):
    return Maze.load(os.path.join(MAZES, f"{name}.txt"))


class ReactiveTest(unittest.TestCase):
    def test_truth_table_matches_firmware(self):
        s = Reactive()
        s.reset(4, (0, 0), frozenset())
        pose = (0, 0, 0)
        cases = {
            (False, False, False): Action.FORWARD,
            (False, True, True): Action.FORWARD,
            (True, False, True): Action.LEFT,
            (True, True, False): Action.RIGHT,
            (True, False, False): Action.RIGHT,
            (True, True, True): Action.AROUND,
        }
        for (front, left, right), want in cases.items():
            self.assertIs(s.decide(pose, Sensors(front, left, right)), want)

    def test_solves_corridor(self):
        r = run(load("corridor5"), Reactive())
        self.assertTrue(r.solved)
        self.assertEqual(r.steps_to_goal, 10)

    def test_loops_forever_on_loop8(self):
        maze = load("loop8")
        r = run(maze, Reactive(), trace=True)
        self.assertFalse(r.solved)
        self.assertEqual(r.total_steps, r.max_steps)
        starts = sum(1 for f in r.frames if (f.pose[0], f.pose[1]) == maze.start and f.action is Action.FORWARD)
        self.assertGreaterEqual(starts, 3, "робот должен многократно возвращаться на старт")
        self.assertLessEqual(len(r.visited), 10)


class RightHandTest(unittest.TestCase):
    def test_solves_loop8(self):
        r = run(load("loop8"), RightHand())
        self.assertTrue(r.solved)

    def test_fails_on_island(self):
        r = run(load("island16"), RightHand())
        self.assertFalse(r.solved)

    def test_no_spinning_in_open_area(self):
        maze = Maze(4, goals={(3, 3)})
        r = run(maze, RightHand())
        self.assertGreater(r.total_steps, 0)


class FloodFillTest(unittest.TestCase):
    def test_reaches_goal_on_200_random_mazes(self):
        for i in range(200):
            maze = generate(16, seed=maze_seed(100, i), loops=i % 20)
            r = run(maze, FloodFill())
            self.assertTrue(r.solved, f"лабиринт {i}")
            self.assertTrue(r.finished, f"лабиринт {i}: заезд не завершён")
            self.assertIsNotNone(r.speed_len)

    def test_solves_island_and_loop(self):
        for name in ("corridor5", "loop8", "island16", "random16"):
            r = run(load(name), FloodFill())
            self.assertTrue(r.solved, name)
            self.assertEqual(r.speed_len, r.optimum, name)

    def test_speed_run_equals_shortest_path_on_full_map(self):
        for i in range(30):
            maze = generate(16, seed=maze_seed(200, i), loops=12)
            strategy = FloodFill()
            strategy.load_full_map(maze)
            r = run(maze, strategy, reset_strategy=False)
            self.assertTrue(r.finished)
            self.assertEqual(r.speed_len, maze.shortest_len(), f"лабиринт {i}")
            self.assertEqual(r.total_steps, r.speed_len)

    def test_speed_run_equals_optimum_after_exploration(self):
        for i in range(50):
            maze = generate(16, seed=maze_seed(300, i), loops=16)
            r = run(maze, FloodFill())
            self.assertEqual(r.speed_len, r.optimum, f"лабиринт {i}")

    def test_noise_still_solves(self):
        solved = 0
        for i in range(40):
            maze = generate(16, seed=maze_seed(400, i), loops=16)
            r = run(maze, FloodFill(), noise=0.05, seed=i)
            solved += r.solved
        self.assertGreaterEqual(solved, 38)

    def test_phases(self):
        r = run(load("loop8"), FloodFill(), trace=True)
        phases = [f.phase for f in r.frames]
        self.assertEqual(phases[0], "EXPLORE")
        self.assertIn("RETURN", phases)
        self.assertIn("SPEED_RUN", phases)
        self.assertEqual(phases[-1], "DONE")
        self.assertEqual(phases.index("RETURN") < phases.index("SPEED_RUN"), True)


class DeterminismTest(unittest.TestCase):
    def test_run_deterministic(self):
        maze = generate(16, seed=5, loops=10)
        a = run(maze, make_strategy("flood_fill"), noise=0.05, seed=11, trace=True)
        b = run(maze, make_strategy("flood_fill"), noise=0.05, seed=11, trace=True)
        self.assertEqual([f.pose for f in a.frames], [f.pose for f in b.frames])
        self.assertEqual(a.total_time, b.total_time)

    def test_bench_deterministic(self):
        rows_a = bench(n=10, size=8, seed=3, noise=0.05, jobs=1)
        rows_b = bench(n=10, size=8, seed=3, noise=0.05, jobs=1)
        skip = {"wall_time_s"}
        for a, b in zip(rows_a, rows_b):
            self.assertEqual(
                {k: _fmt(v) for k, v in a.items() if k not in skip},
                {k: _fmt(v) for k, v in b.items() if k not in skip},
            )


if __name__ == "__main__":
    unittest.main()
