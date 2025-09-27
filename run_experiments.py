"""
Run experiments across generators and collect metrics into results.csv.

Usage:
    python run_experiments.py [--runs N] [--out results.csv]

This script is defensive: it tries to import generator names used in your workspace
and falls back to alternative names if available.
"""
import argparse
import importlib
import sys
from collections import defaultdict

import pandas as pd

# Import evaluation functions
from evaluation import connectivity_ratio, path_metrics, room_variety

# Try to import generator classes from room_accretion.py (robust to naming)
try:
    mod = importlib.import_module("room_accretion")
except Exception as e:
    print("ERROR: could not import room_accretion module:", e, file=sys.stderr)
    raise

# Resolve generator class names (support both DungeonGenerator and RoomAccretionGenerator)
RoomAccretionGenerator = getattr(mod, "RoomAccretionGenerator", None)
if RoomAccretionGenerator is None:
    RoomAccretionGenerator = getattr(mod, "DungeonGenerator", None)

BFSDungeonGenerator = getattr(mod, "BFSDungeonGenerator", None)
HybridDungeonGenerator = getattr(mod, "HybridDungeonGenerator", None)

if RoomAccretionGenerator is None or BFSDungeonGenerator is None or HybridDungeonGenerator is None:
    missing = []
    if RoomAccretionGenerator is None:
        missing.append("RoomAccretionGenerator/DungeonGenerator")
    if BFSDungeonGenerator is None:
        missing.append("BFSDungeonGenerator")
    if HybridDungeonGenerator is None:
        missing.append("HybridDungeonGenerator")
    raise ImportError(f"Missing required generator classes in room_accretion.py: {', '.join(missing)}")

# Optional config class
ConfigClass = getattr(mod, "DungeonConfig", None)


def make_config(seed: int = None):
    """Create a config instance if DungeonConfig exists, otherwise return None."""
    if ConfigClass is None:
        return None
    try:
        # Try to pass seed if dataclass supports it
        return ConfigClass() if seed is None else ConfigClass(seed=seed)
    except TypeError:
        # Fallback: call without args and then set attribute if present
        cfg = ConfigClass()
        try:
            setattr(cfg, "seed", seed)
        except Exception:
            pass
        return cfg


def run_one(gen_cls, run_idx: int):
    """Instantiate generator, run generation, and return (grid, rooms)."""
    cfg = make_config(seed=run_idx)
    gen = gen_cls(cfg) if cfg is not None else gen_cls(None)  # some constructors accept None
    result = gen.generate()
    # generator.generate may return (grid, rooms) or write to gen.map / gen.rooms
    if isinstance(result, tuple) and len(result) >= 1:
        # Expect (grid, rooms) or (grid, rooms, ...)
        grid = result[0]
        rooms = result[1] if len(result) > 1 else getattr(gen, "rooms", [])
    else:
        grid = getattr(gen, "map", None)
        rooms = getattr(gen, "rooms", [])
    if grid is None:
        raise RuntimeError(f"Generator {gen_cls.__name__} did not produce a grid (run {run_idx})")
    return grid, rooms


def collect_metrics(gen_name: str, grid, rooms):
    """Compute required metrics and return a dict row for the DataFrame."""
    conn = connectivity_ratio(grid)
    p = path_metrics(grid)
    maxd = p.get("max_distance", 0)
    avgd = p.get("average_distance", 0.0)

    rv = room_variety(rooms) if rooms is not None else {}
    counts = rv.get("counts", {}) if isinstance(rv, dict) else {}
    rect = counts.get("rect", 0)
    prefab = counts.get("prefab", 0)
    bfs = counts.get("bfs", 0)

    return {
        "generator": gen_name,
        "connectivity": float(conn),
        "longest_path": int(maxd),
        "avg_path": float(avgd),
        "rect_rooms": int(rect),
        "prefab_rooms": int(prefab),
        "bfs_rooms": int(bfs),
    }


def main(runs: int, out_csv: str):
    rows = []
    generators = [
        ("room_accretion", RoomAccretionGenerator),
        ("bfs", BFSDungeonGenerator),
        ("hybrid", HybridDungeonGenerator),
    ]

    for gen_name, gen_cls in generators:
        print(f"Running generator: {gen_name} ({runs} runs)")
        for i in range(runs):
            try:
                grid, rooms = run_one(gen_cls, i)
            except Exception as e:
                print(f"Error running {gen_name} run {i}: {e}", file=sys.stderr)
                raise
            row = collect_metrics(gen_name, grid, rooms)
            row["run"] = i
            rows.append(row)

    df = pd.DataFrame(rows, columns=[
        "generator", "run", "connectivity", "longest_path", "avg_path",
        "rect_rooms", "prefab_rooms", "bfs_rooms"
    ])
    df.to_csv(out_csv, index=False)
    print(f"Saved results to {out_csv}")

    # Print summary: mean/std per generator
    numeric_cols = ["connectivity", "longest_path", "avg_path", "rect_rooms", "prefab_rooms", "bfs_rooms"]
    summary = df.groupby("generator")[numeric_cols].agg(["mean", "std"])
    pd.set_option("display.width", 200)
    print("\nSummary (mean / std):")
    print(summary)
    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=100, help="Number of runs per generator")
    parser.add_argument("--out", type=str, default="results.csv", help="Output CSV file")
    args = parser.parse_args()
    main(args.runs, args.out)