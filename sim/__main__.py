import argparse
import os
import sys

from . import bench as bench_mod
from .maze import Maze, generate
from .simulate import run
from .strategies import STRATEGIES, make_strategy
from .viz import animate, render_ascii, replay_frames, status_line


def _load_maze(args: argparse.Namespace) -> Maze:
    if args.maze:
        return Maze.load(args.maze)
    loops = args.loops if args.loops is not None else args.size
    return generate(args.size, seed=args.seed, loops=loops)


def _add_maze_args(p: argparse.ArgumentParser):
    p.add_argument("--maze", help="файл лабиринта (иначе случайный)")
    p.add_argument("--size", type=int, default=16, help="размер случайного лабиринта")
    p.add_argument("--seed", type=int, default=1, help="seed лабиринта и шума")
    p.add_argument("--loops", type=int, default=None, help="снятых стен в случайном лабиринте (по умолчанию = size)")
    p.add_argument("--strategy", choices=list(STRATEGIES), default="flood_fill")
    p.add_argument("--noise", type=float, default=0.0, help="вероятность ложного показания датчика")
    p.add_argument("--max-steps", type=int, default=None, help="лимит шагов до цели (по умолчанию 4·N²)")


def cmd_bench(args: argparse.Namespace) -> int:
    rows = bench_mod.bench(
        n=args.n, size=args.size, seed=args.seed, noise=args.noise, loops=args.loops,
        strategies=args.strategies, jobs=args.jobs,
    )
    merged = bench_mod.write_csv(rows, args.csv)
    bench_mod.write_markdown(merged, args.md)
    print(bench_mod.format_markdown([{k: bench_mod._fmt(v) for k, v in r.items()} for r in rows]))
    print(f"CSV: {args.csv}\nMarkdown: {args.md}\nвремя: {rows[0]['wall_time_s']:.1f} с")
    return 0


def _print_summary(result):
    print(f"стратегия: {result.strategy}, лабиринт {result.size}×{result.size}, лимит шагов {result.max_steps}")
    if result.solved:
        print(
            f"цель достигнута: шагов {result.steps_to_goal}, поворотов {result.turns_to_goal}, "
            f"разворотов {result.uturns_to_goal}, ударов {result.bumps_to_goal}, время {result.time_to_goal:.1f}"
        )
    else:
        print(f"цель НЕ достигнута за {result.total_steps} шагов (посещено клеток: {len(result.visited)})")
    print(f"оптимум (BFS по полному лабиринту): {result.optimum}")
    if result.speed_len is not None:
        print(
            f"скоростной заезд: {result.speed_len} шагов, поворотов {result.speed_turns}, "
            f"время {result.speed_time:.1f}; кругов разведки {result.explore_runs}; "
            f"заезд / оптимум = {result.speed_ratio:.3f}"
        )
    print(f"итого: шагов {result.total_steps}, поворотов {result.total_turns}, разворотов {result.total_uturns}, "
          f"ударов {result.total_bumps}, время {result.total_time:.1f}, фаза {result.phase}")


def cmd_show(args: argparse.Namespace) -> int:
    maze = _load_maze(args)
    result = run(maze, make_strategy(args.strategy), max_steps=args.max_steps, noise=args.noise, seed=args.seed, trace=True)
    frames = list(replay_frames(result))
    for i, (frame, visited, dist, known) in enumerate(frames):
        last = i == len(frames) - 1
        if not (last or (args.every and i % args.every == 0)):
            continue
        action = frame.action.name if frame.action else "START"
        print(f"--- кадр {frame.index}: {action}{'' if frame.ok else ' (стена!)'}  {status_line(result, frame)}")
        print(render_ascii(maze, frame.pose, visited=visited, dist=dist if args.dist else None, known=known if args.known else None))
    print()
    _print_summary(result)
    if args.log:
        print("действия:", "".join(f.action.value for f in result.frames if f.action))
    return 0


def cmd_viz(args: argparse.Namespace) -> int:
    maze = _load_maze(args)
    result = run(maze, make_strategy(args.strategy), max_steps=args.max_steps, noise=args.noise, seed=args.seed, trace=True)
    out = args.out
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    root, ext = os.path.splitext(out)
    gif_path = out if ext.lower() == ".gif" else None
    png_path = args.png or (root + ".png")
    info = animate(
        maze, result, gif_path=gif_path, png_path=png_path,
        cell=args.cell, every=args.every, delay=args.delay, max_frames=args.max_frames,
    )
    if args.ascii:
        last = list(replay_frames(result))[-1]
        print(render_ascii(maze, last[0].pose, visited=last[1], dist=last[2], known=last[3]))
    _print_summary(result)
    print(f"кадров: {info['frames']}, размер {info['width']}×{info['height']} px")
    if gif_path:
        print(f"GIF: {gif_path} ({info['gif_bytes']} байт)")
    print(f"PNG: {png_path} ({info['png_bytes']} байт)")
    return 0


def cmd_gen(args: argparse.Namespace) -> int:
    loops = args.loops if args.loops is not None else args.size
    maze = generate(args.size, seed=args.seed, loops=loops)
    comment = f"{args.size}x{args.size} случайный лабиринт, seed {args.seed}, снято стен {loops}"
    if args.out:
        maze.save(args.out, comment)
        print(args.out)
    else:
        print(maze.to_text(), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sim", description="Симулятор Micromouse")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("bench", help="серия случайных лабиринтов, таблица по стратегиям")
    p.add_argument("--n", type=int, default=500, help="число лабиринтов")
    p.add_argument("--size", type=int, default=16)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--noise", type=float, default=0.0)
    p.add_argument("--loops", type=int, default=None, help="снятых стен в лабиринте (по умолчанию = size)")
    p.add_argument("--strategies", nargs="+", choices=list(STRATEGIES), default=None)
    p.add_argument("--jobs", type=int, default=None, help="число процессов (по умолчанию все ядра)")
    p.add_argument("--csv", default=bench_mod.CSV_PATH)
    p.add_argument("--md", default=bench_mod.MD_PATH)
    p.set_defaults(func=cmd_bench)

    p = sub.add_parser("show", help="ASCII-трасса одного прогона")
    _add_maze_args(p)
    p.add_argument("--every", type=int, default=0, help="печатать каждый k-й кадр (0 — только итог)")
    p.add_argument("--dist", action="store_true", help="печатать расстояния flood fill")
    p.add_argument("--known", action="store_true", help="рисовать только известные роботу стены")
    p.add_argument("--log", action="store_true", help="печатать строку действий (F/L/R/U)")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("viz", help="GIF-анимация и PNG последнего кадра")
    _add_maze_args(p)
    p.add_argument("--out", required=True, help="путь к .gif (или .png — тогда только кадр)")
    p.add_argument("--png", default=None, help="путь к PNG последнего кадра (по умолчанию рядом с GIF)")
    p.add_argument("--cell", type=int, default=20, help="размер клетки в пикселях")
    p.add_argument("--every", type=int, default=1, help="брать каждый k-й кадр")
    p.add_argument("--delay", type=int, default=6, help="задержка кадра, сотые доли секунды")
    p.add_argument("--max-frames", type=int, default=None)
    p.add_argument("--ascii", action="store_true", help="дополнительно напечатать итоговую ASCII-картинку")
    p.set_defaults(func=cmd_viz)

    p = sub.add_parser("gen", help="сгенерировать лабиринт")
    p.add_argument("--size", type=int, default=16)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--loops", type=int, default=None)
    p.add_argument("--out", default=None, help="файл для сохранения (иначе печать в stdout)")
    p.set_defaults(func=cmd_gen)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
