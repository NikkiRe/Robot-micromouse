import csv
import multiprocessing
import os
import statistics
import time
from collections import defaultdict
from typing import Iterable

from .maze import generate
from .simulate import run
from .strategies import STRATEGIES, make_strategy

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
CSV_PATH = os.path.join(RESULTS_DIR, "bench.csv")
MD_PATH = os.path.join(RESULTS_DIR, "bench.md")

KEY_FIELDS = ("size", "noise", "loops", "n", "seed", "strategy")
FIELDS = KEY_FIELDS + (
    "solved_rate", "steps_median", "steps_mean", "steps_p90",
    "turns_mean", "uturns_mean", "bumps_mean", "time_mean",
    "speed_mean", "optimum_mean", "speed_ratio", "explore_runs_mean", "wall_time_s",
)


def maze_seed(seed: int, index: int) -> int:
    return seed * 1_000_003 + index


def _run_one(args: tuple) -> list[dict]:
    seed, index, size, loops, noise, names = args
    maze = generate(size, seed=maze_seed(seed, index), loops=loops)
    rows = []
    for k, name in enumerate(names):
        result = run(maze, make_strategy(name), noise=noise, seed=maze_seed(seed, index) * 7 + k)
        rows.append({
            "strategy": name,
            "solved": result.solved,
            "steps": result.steps_to_goal,
            "turns": result.turns_to_goal,
            "uturns": result.uturns_to_goal,
            "bumps": result.bumps_to_goal,
            "time": result.time_to_goal,
            "speed": result.speed_len,
            "optimum": result.optimum,
            "explore_runs": result.explore_runs,
        })
    return rows


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    k = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[k]


def _mean(values: Iterable[float | None]) -> float:
    vals = [v for v in values if v is not None]
    return statistics.fmean(vals) if vals else float("nan")


def bench(
    n: int = 500,
    size: int = 16,
    seed: int = 1,
    noise: float = 0.0,
    loops: int | None = None,
    strategies: Iterable[str] | None = None,
    jobs: int | None = None,
) -> list[dict]:
    names = list(strategies or STRATEGIES)
    if loops is None:
        loops = size
    started = time.time()
    tasks = [(seed, i, size, loops, noise, names) for i in range(n)]
    jobs = jobs if jobs is not None else (os.cpu_count() or 1)
    if jobs > 1 and n >= 8:
        with multiprocessing.Pool(jobs) as pool:
            per_maze = pool.map(_run_one, tasks, chunksize=max(1, n // (jobs * 4)))
    else:
        per_maze = [_run_one(t) for t in tasks]
    wall = time.time() - started

    by_strategy: dict[str, list[dict]] = defaultdict(list)
    for rows in per_maze:
        for row in rows:
            by_strategy[row["strategy"]].append(row)

    aggregated = []
    for name in names:
        rows = by_strategy[name]
        solved = [r for r in rows if r["solved"]]
        steps = [r["steps"] for r in solved]
        speed = [r["speed"] for r in solved if r["speed"] is not None]
        optimum_for_speed = [r["optimum"] for r in solved if r["speed"] is not None]
        aggregated.append({
            "size": size, "noise": noise, "loops": loops, "n": n, "seed": seed, "strategy": name,
            "solved_rate": len(solved) / max(1, len(rows)),
            "steps_median": statistics.median(steps) if steps else float("nan"),
            "steps_mean": _mean(steps),
            "steps_p90": _percentile(steps, 0.9),
            "turns_mean": _mean(r["turns"] for r in solved),
            "uturns_mean": _mean(r["uturns"] for r in solved),
            "bumps_mean": _mean(r["bumps"] for r in solved),
            "time_mean": _mean(r["time"] for r in solved),
            "speed_mean": _mean(speed),
            "optimum_mean": _mean(r["optimum"] for r in rows),
            "speed_ratio": (sum(speed) / sum(optimum_for_speed)) if speed else float("nan"),
            "explore_runs_mean": _mean(r["explore_runs"] for r in solved) if name == "flood_fill" else float("nan"),
            "wall_time_s": wall,
        })
    return aggregated


def _row_key(row: dict) -> tuple:
    return tuple(str(row[k]) for k in KEY_FIELDS)


def read_csv(path: str = CSV_PATH) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(rows: list[dict], path: str = CSV_PATH) -> list[dict]:
    merged: dict[tuple, dict] = {}
    for row in read_csv(path) + [{k: _fmt(v) for k, v in r.items()} for r in rows]:
        merged[_row_key(row)] = row
    ordered = sorted(merged.values(), key=lambda r: (int(r["size"]), float(r["noise"]), int(r["loops"]), r["strategy"]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(ordered)
    return ordered


def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.4g}" if v == v else "nan"
    return str(v)


def _num(s: str) -> float:
    try:
        return float(s)
    except (TypeError, ValueError):
        return float("nan")


def _cell(v: float, digits: int = 1) -> str:
    return "—" if v != v else f"{v:.{digits}f}"


def format_markdown(rows: list[dict]) -> str:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[(int(row["size"]), float(row["noise"]), int(row["loops"]), int(row["n"]), int(row["seed"]))].append(row)
    out = ["# Результаты bench", ""]
    out.append(
        "Шаги, повороты, развороты и время считаются до первого попадания в цель "
        "и только по решённым прогонам. «Заезд / оптимум» — суммарная длина "
        "скоростного заезда flood fill, делённая на суммарную длину кратчайшего пути "
        "(BFS по полному лабиринту)."
    )
    out.append("")
    for (size, noise, loops, n, seed), group in sorted(groups.items()):
        out.append(f"## {size}×{size}, шум {noise:g}, циклов {loops}, лабиринтов {n}, seed {seed}")
        out.append("")
        out.append("| стратегия | решено | шаги: медиана | среднее | p90 | повороты | развороты | удары | время | заезд | оптимум | заезд / оптимум |")
        out.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in sorted(group, key=lambda r: list(STRATEGIES).index(r["strategy"]) if r["strategy"] in STRATEGIES else 99):
            out.append(
                f"| {row['strategy']} | {100 * _num(row['solved_rate']):.1f} % "
                f"| {_cell(_num(row['steps_median']), 0)} | {_cell(_num(row['steps_mean']))} | {_cell(_num(row['steps_p90']), 0)} "
                f"| {_cell(_num(row['turns_mean']))} | {_cell(_num(row['uturns_mean']))} | {_cell(_num(row['bumps_mean']))} "
                f"| {_cell(_num(row['time_mean']))} | {_cell(_num(row['speed_mean']))} | {_cell(_num(row['optimum_mean']))} "
                f"| {_cell(_num(row['speed_ratio']), 3)} |"
            )
        out.append("")
    return "\n".join(out)


def write_markdown(rows: list[dict], path: str = MD_PATH):
    with open(path, "w", encoding="utf-8") as f:
        f.write(format_markdown(rows))
