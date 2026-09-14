import os
import unittest

from sim.maze import EAST, INF, NORTH, SOUTH, WEST, Maze, default_goals, generate

MAZES = os.path.join(os.path.dirname(__file__), "..", "sim", "mazes")


class MazeBasicsTest(unittest.TestCase):
    def test_boundary_walls(self):
        m = Maze(4)
        for i in range(4):
            self.assertTrue(m.has_wall(i, 0, SOUTH))
            self.assertTrue(m.has_wall(i, 3, NORTH))
            self.assertTrue(m.has_wall(0, i, WEST))
            self.assertTrue(m.has_wall(3, i, EAST))
        self.assertFalse(m.has_wall(1, 1, NORTH))

    def test_set_wall_is_symmetric(self):
        m = Maze(4)
        m.set_wall(1, 1, EAST)
        self.assertTrue(m.has_wall(2, 1, WEST))
        m.set_wall(2, 1, WEST, False)
        self.assertFalse(m.has_wall(1, 1, EAST))
        with self.assertRaises(ValueError):
            m.set_wall(0, 0, WEST, False)

    def test_default_goals(self):
        self.assertEqual(default_goals(16), {(7, 7), (7, 8), (8, 7), (8, 8)})
        self.assertEqual(default_goals(5), {(2, 2)})

    def test_bfs_and_shortest_path(self):
        m = Maze(3, goals={(2, 2)})
        m.set_wall(0, 0, EAST)
        m.set_wall(1, 1, EAST)
        dist = m.bfs(m.goals)
        self.assertEqual(dist[2][2], 0)
        self.assertEqual(dist[0][0], 4)
        path = m.shortest_path((0, 0), m.goals)
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (2, 2))
        self.assertEqual(len(path) - 1, 4)
        m.set_wall(2, 2, SOUTH)
        m.set_wall(2, 2, WEST)
        self.assertIsNone(m.shortest_path((0, 0), m.goals))
        self.assertEqual(m.bfs(m.goals)[0][0], INF)


class GeneratorTest(unittest.TestCase):
    def test_connected_for_many_seeds(self):
        for size in (5, 8, 16):
            for seed in range(30):
                m = generate(size, seed=seed, loops=seed % 5)
                self.assertTrue(m.is_connected(), f"size={size} seed={seed}")
                self.assertIsNotNone(m.shortest_len())

    def test_perfect_maze_edge_count(self):
        for seed in range(5):
            m = generate(8, seed=seed, loops=0, open_goal=False)
            open_edges = sum(1 for e in m.internal_edges() if not m.has_wall(*e))
            self.assertEqual(open_edges, 8 * 8 - 1)

    def test_loops_add_edges(self):
        base = generate(8, seed=3, loops=0)
        looped = generate(8, seed=3, loops=10)
        count = lambda m: sum(1 for e in m.internal_edges() if not m.has_wall(*e))
        self.assertEqual(count(looped), count(base) + 10)

    def test_goal_area_open(self):
        m = generate(16, seed=1)
        self.assertFalse(m.has_wall(7, 7, EAST))
        self.assertFalse(m.has_wall(7, 7, NORTH))
        self.assertFalse(m.has_wall(8, 8, WEST))
        self.assertFalse(m.has_wall(8, 8, SOUTH))

    def test_deterministic_by_seed(self):
        self.assertEqual(generate(16, seed=42, loops=8), generate(16, seed=42, loops=8))
        self.assertNotEqual(generate(16, seed=42, loops=8), generate(16, seed=43, loops=8))


class TextFormatTest(unittest.TestCase):
    def test_roundtrip_random(self):
        for seed in range(5):
            m = generate(16, seed=seed, loops=5)
            self.assertEqual(Maze.from_text(m.to_text()), m)

    def test_roundtrip_presets(self):
        for name in ("corridor5", "loop8", "island16", "random16"):
            m = Maze.load(os.path.join(MAZES, f"{name}.txt"))
            self.assertEqual(Maze.from_text(m.to_text()), m)

    def test_marks_and_comments(self):
        text = (
            "# комментарий\n"
            "+---+---+\n"
            "| G     |\n"
            "+   +---+\n"
            "| S |   |\n"
            "+---+---+\n"
        )
        m = Maze.from_text(text)
        self.assertEqual(m.n, 2)
        self.assertEqual(m.start, (0, 0))
        self.assertEqual(m.goals, {(0, 1)})
        self.assertTrue(m.has_wall(0, 0, EAST))
        self.assertFalse(m.has_wall(0, 0, NORTH))
        self.assertTrue(m.has_wall(1, 0, NORTH))

    def test_bad_text(self):
        with self.assertRaises(ValueError):
            Maze.from_text("+---+\n|   |\n")


if __name__ == "__main__":
    unittest.main()
