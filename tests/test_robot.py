import random
import unittest

from sim.maze import EAST, NORTH, SOUTH, WEST, Maze
from sim.robot import Robot, Sensors


def _cell_maze():
    m = Maze(3)
    m.set_wall(1, 1, NORTH)
    m.set_wall(1, 1, EAST)
    return m


class SensorsTest(unittest.TestCase):
    def test_four_orientations(self):
        m = _cell_maze()
        expected = {
            NORTH: Sensors(front=True, left=False, right=True),
            EAST: Sensors(front=True, left=True, right=False),
            SOUTH: Sensors(front=False, left=True, right=False),
            WEST: Sensors(front=False, left=False, right=True),
        }
        for heading, want in expected.items():
            r = Robot(m, x=1, y=1, heading=heading)
            self.assertEqual(r.sense(), want, f"heading={heading}")
            self.assertEqual(r.sense_true(), want)

    def test_noise_flips_readings(self):
        m = _cell_maze()
        r = Robot(m, x=1, y=1, heading=NORTH, noise=0.5, rng=random.Random(1))
        truth = r.sense_true()
        flipped = sum(1 for _ in range(300) if r.sense() != truth)
        self.assertGreater(flipped, 150)
        r0 = Robot(m, x=1, y=1, heading=NORTH, noise=0.0)
        self.assertTrue(all(r0.sense() == truth for _ in range(50)))

    def test_noise_deterministic_by_seed(self):
        m = _cell_maze()
        a = Robot(m, x=1, y=1, noise=0.3, rng=random.Random(7))
        b = Robot(m, x=1, y=1, noise=0.3, rng=random.Random(7))
        self.assertEqual([a.sense() for _ in range(50)], [b.sense() for _ in range(50)])


class ActionsTest(unittest.TestCase):
    def test_forward_and_bump(self):
        m = _cell_maze()
        r = Robot(m, x=1, y=1, heading=NORTH)
        self.assertFalse(r.forward())
        self.assertEqual((r.x, r.y, r.bumps, r.steps), (1, 1, 1, 0))
        self.assertAlmostEqual(r.time, 0.5)
        r.turn_left()
        self.assertEqual(r.heading, WEST)
        self.assertTrue(r.forward())
        self.assertEqual((r.x, r.y), (0, 1))
        self.assertAlmostEqual(r.time, 0.5 + 0.5 + 1.0)

    def test_turns_and_counters(self):
        r = Robot(Maze(4), heading=NORTH)
        r.turn_right()
        self.assertEqual(r.heading, EAST)
        r.turn_right()
        self.assertEqual(r.heading, SOUTH)
        r.turn_around()
        self.assertEqual(r.heading, NORTH)
        r.turn_left()
        self.assertEqual(r.heading, WEST)
        self.assertEqual((r.turns, r.uturns), (3, 1))
        self.assertAlmostEqual(r.time, 3 * 0.5 + 1.0)

    def test_custom_times(self):
        r = Robot(Maze(4), cell_time=2.0, turn_time=0.25, uturn_time=3.0)
        r.forward()
        r.turn_left()
        r.turn_around()
        self.assertAlmostEqual(r.time, 5.25)

    def test_reset(self):
        r = Robot(Maze(4))
        r.forward()
        r.turn_right()
        r.reset()
        self.assertEqual((r.x, r.y, r.heading, r.steps, r.turns, r.time), (0, 0, NORTH, 0, 0, 0.0))


if __name__ == "__main__":
    unittest.main()
