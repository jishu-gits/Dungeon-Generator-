"""
Visualize experiment results saved by run_experiments.py

Creates:
 - connectivity_boxplot.png
 - path_length_histogram.png
 - room_variety_barchart.png

Usage:
    python visualize_results.py [--csv results.csv]
"""
from typing import Optional
import argparse
import sys

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


def load_results(path: str) -> pd.DataFrame:
    """Load results CSV into a DataFrame, validating required columns."""
    df = pd.read_csv(path)
    required = {
        "generator",
        "run",
        "connectivity",
        "longest_path",
        "avg_path",
        "rect_rooms",
        "prefab_rooms",
        "bfs_rooms",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in {path}: {missing}")
    return df


def print_summary(df: pd.DataFrame) -> None:
    """Print mean/std summary per generator for key metrics and room variety."""
    grp = df.groupby("generator")
    metrics = ["connectivity", "longest_path", "avg_path"]
    print("Summary statistics (mean ± std) per generator:")
    for gen, sub in grp:
        means = sub[metrics].mean()
        stds = sub[metrics].std()
        print(f"\nGenerator: {gen}")
        for m in metrics:
            print(f"  {m}: {means[m]:.3f} ± {stds[m]:.3f}")
        # room variety averages
        rect = sub["rect_rooms"].mean()
        prefab = sub["prefab_rooms"].mean()
        bfs = sub["bfs_rooms"].mean()
        print(f"  Avg rooms - Rect: {rect:.2f}, Prefab: {prefab:.2f}, BFS: {bfs:.2f}")


def connectivity_boxplot(df: pd.DataFrame, out_path: str) -> None:
    """Create a boxplot of connectivity by generator and save it."""
    plt.figure(figsize=(8, 6))
    ax = df.boxplot(column="connectivity", by="generator", grid=False, patch_artist=True)
    plt.title("Connectivity by Generator")
    plt.suptitle("")  # remove automatic subplot title
    plt.xlabel("Generator")
    plt.ylabel("Connectivity ratio")
    plt.ylim(0.0, 1.05)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def path_length_histogram(df: pd.DataFrame, out_path: str, bins: int = 30) -> None:
    """Overlay histograms of avg_path for each generator and save figure."""
    plt.figure(figsize=(8, 6))
    gens = df["generator"].unique()
    colors = plt.cm.tab10.colors
    for i, gen in enumerate(sorted(gens)):
        sub = df[df["generator"] == gen]
        plt.hist(sub["avg_path"].dropna(), bins=bins, alpha=0.5, label=str(gen), color=colors[i % len(colors)])
    plt.xlabel("Average path length")
    plt.ylabel("Frequency")
    plt.title("Distribution of average path length by generator")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def room_variety_barchart(df: pd.DataFrame, out_path: str) -> None:
    """Create grouped bar chart of average room counts (Rect/Prefab/BFS) per generator."""
    grp = df.groupby("generator")[["rect_rooms", "prefab_rooms", "bfs_rooms"]].mean()
    labels = ["Rect", "Prefab", "BFS"]
    gens = grp.index.tolist()
    counts = grp.values  # shape: (n_generators, 3)
    n_gen = len(gens)
    x = np.arange(len(labels))
    width = 0.8 / max(1, n_gen)  # bar width per group

    plt.figure(figsize=(10, 6))
    for i, gen in enumerate(gens):
        offsets = x - 0.4 + (i + 0.5) * width
        plt.bar(offsets, counts[i], width=width, label=str(gen))
    plt.xticks(x, labels)
    plt.ylabel("Average count")
    plt.title("Average room counts by type and generator")
    plt.legend(title="Generator")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def main(csv_path: str) -> None:
    try:
        df = load_results(csv_path)
    except Exception as e:
        print(f"Failed to load results file '{csv_path}': {e}", file=sys.stderr)
        sys.exit(1)

    # Print console summary
    print_summary(df)

    # Plots
    connectivity_boxplot(df, "connectivity_boxplot.png")
    print("Saved connectivity_boxplot.png")

    path_length_histogram(df, "path_length_histogram.png")
    print("Saved path_length_histogram.png")

    room_variety_barchart(df, "room_variety_barchart.png")
    print("Saved room_variety_barchart.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize dungeon experiment results")
    parser.add_argument("--csv", default="results.csv", help="Path to results.csv produced by run_experiments.py")
    args = parser.parse_args()
    main(args.csv)