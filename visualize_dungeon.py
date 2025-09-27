"""
visualize_dungeon.py

Standalone script to render dungeon generation stages to PNGs.

Provides:
    visualize_stage(grid, metadata, stage_name, output_file)

Metadata accepted formats (any of):
    - 2D array/list of same shape as grid with per-cell tags:
        e.g. metadata[y][x] in {"rect","prefab","bfs","wall", "empty"}
    - list of room-like records where each entry is either:
        * an object/dict with keys: x,y,w,h,room_type
        * a tuple/list: (x,y,w,h,room_type)
        This will mark the rectangular bbox with room_type.
    - list of records with explicit tile lists:
        * dict with keys: "tiles" -> iterable of (x,y) and "room_type"
          (useful for irregular prefab shapes)
If metadata is None the function will color floors '.' as blue (rect) and walls '#'
as dark gray.

Usage:
    import matplotlib
    from visualize_dungeon import visualize_stage
    visualize_stage(grid, metadata, "Stage 1", "stage1.png")

This file also runs a small demo when executed directly and writes stage1.png..stage4.png
"""

from typing import List, Any, Iterable, Tuple, Dict, Optional
import numpy as np
import matplotlib.pyplot as plt


# Color map (RGB tuples 0-1)
COLOR_MAP = {
    "wall": (0.27, 0.27, 0.27),     # dark gray
    "rect": (0.12, 0.46, 0.70),     # blue
    "bfs": (0.18, 0.63, 0.18),      # green
    "prefab": (0.84, 0.18, 0.15),   # red
    "empty": (1.0, 1.0, 1.0),       # white
    "floor_unknown": (0.85, 0.85, 0.85)  # light gray fallback for non-typed floors
}


def _ensure_numpy_grid(grid: List[List[str]]) -> np.ndarray:
    """Convert grid (list of lists) to numpy array of chars."""
    arr = np.array(grid, dtype="U1")
    # shape (H,W)
    return arr


def _metadata_to_tag_array(grid_arr: np.ndarray, metadata: Any) -> np.ndarray:
    """
    Produce a tag array (strings) of same shape as grid_arr describing each cell's semantic type.

    Returns array of dtype object with values in {"wall","rect","prefab","bfs","empty","floor_unknown"}.
    """
    h, w = grid_arr.shape
    tags = np.full((h, w), "empty", dtype=object)

    # mark walls first
    for y in range(h):
        for x in range(w):
            if grid_arr[y, x] == "#":
                tags[y, x] = "wall"
            elif grid_arr[y, x] == ".":
                tags[y, x] = "floor_unknown"
            else:
                # anything else treat as empty/unused
                tags[y, x] = "empty"

    if metadata is None:
        return tags

    # If metadata is a 2D array/list of same shape, copy values per-cell
    if isinstance(metadata, (list, np.ndarray)):
        # check if it's a 2D grid-like of tags
        try:
            md_arr = np.array(metadata, dtype=object)
            if md_arr.shape == (h, w):
                for y in range(h):
                    for x in range(w):
                        val = md_arr[y, x]
                        if val is None:
                            continue
                        sval = str(val).lower()
                        if sval in COLOR_MAP:
                            # override floor or empty with tag
                            tags[y, x] = sval
                return tags
        except Exception:
            # fall through to try list-of-records interpretation
            pass

    # If metadata is a list (rooms or tile lists)
    if isinstance(metadata, list):
        for entry in metadata:
            # dict-like with 'tiles' and 'room_type'
            if isinstance(entry, dict) and "tiles" in entry and "room_type" in entry:
                rtype = str(entry["room_type"]).lower()
                for (tx, ty) in entry["tiles"]:
                    if 0 <= ty < h and 0 <= tx < w:
                        tags[ty, tx] = rtype if rtype in COLOR_MAP else tags[ty, tx]
                continue

            # rect-like: dict with x,y,w,h,room_type
            if isinstance(entry, dict) and {"x", "y", "w", "h", "room_type"}.issubset(entry.keys()):
                x0 = int(entry["x"]); y0 = int(entry["y"]); ww = int(entry["w"]); hh = int(entry["h"])
                rtype = str(entry["room_type"]).lower()
                for yy in range(y0, y0 + hh):
                    for xx in range(x0, x0 + ww):
                        if 0 <= yy < h and 0 <= xx < w:
                            tags[yy, xx] = rtype if rtype in COLOR_MAP else tags[yy, xx]
                continue

            # tuple-like (x,y,w,h,room_type)
            if isinstance(entry, (tuple, list)) and len(entry) == 5:
                x0, y0, ww, hh, rtype = entry
                rtype = str(rtype).lower()
                for yy in range(int(y0), int(y0) + int(hh)):
                    for xx in range(int(x0), int(x0) + int(ww)):
                        if 0 <= yy < h and 0 <= xx < w:
                            tags[yy, xx] = rtype if rtype in COLOR_MAP else tags[yy, xx]
                continue

            # fallback: skip unknown entry
            continue

    return tags


def _tags_to_rgb_image(tags: np.ndarray) -> np.ndarray:
    """Convert tag array into an HxWx3 RGB float array (0..1)."""
    h, w = tags.shape
    img = np.zeros((h, w, 3), dtype=float)
    for y in range(h):
        for x in range(w):
            t = tags[y, x]
            if t not in COLOR_MAP:
                # fallback mapping for unknown floor vs wall
                if t == "floor_unknown":
                    col = COLOR_MAP["floor_unknown"]
                elif t == "wall":
                    col = COLOR_MAP["wall"]
                else:
                    col = COLOR_MAP["empty"]
            else:
                col = COLOR_MAP[t]
            img[y, x, :] = col
    return img


def visualize_stage(grid: List[List[str]],
                    metadata: Optional[Any],
                    stage_name: str,
                    output_file: str,
                    dpi: int = 150) -> None:
    """
    Render a single generation stage to a PNG.

    Args:
        grid: 2D list/array of characters ('#' wall, '.' floor, other = empty).
        metadata: room metadata as described in module docstring.
        stage_name: short title drawn on the image (will be placed above the map).
        output_file: filename to save (PNG).
        dpi: image dpi for saving (controls size).
    """
    grid_arr = _ensure_numpy_grid(grid)
    tags = _metadata_to_tag_array(grid_arr, metadata)
    img = _tags_to_rgb_image(tags)

    # Render using matplotlib
    fig_h = max(2.5, img.shape[0] / 10)
    fig_w = max(3.5, img.shape[1] / 10)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    ax.imshow(img, origin="upper", interpolation="nearest")
    ax.set_title(stage_name)
    ax.axis("off")
    plt.tight_layout()
    fig.savefig(output_file, bbox_inches="tight")
    plt.close(fig)


def plot_dungeon(dungeon, title="Dungeon"):
    """
    Render a dungeon grid (2D list or string rows).
    """
    height = len(dungeon)
    width = len(dungeon[0])

    fig, ax = plt.subplots(figsize=(width/5, height/5))
    cmap = {"#": "black", ".": "white"}  # walls vs floor
    for y, row in enumerate(dungeon):
        for x, ch in enumerate(row):
            ax.add_patch(
                plt.Rectangle((x, height-y-1), 1, 1, color=cmap.get(ch, "red"))
            )
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.set_aspect("equal")
    ax.axis("off")
    plt.title(title)
    plt.show()


# ---------------- Demo example (writes stage1.png .. stage4.png) -----------
def _build_demo_stage(width: int = 60, height: int = 30):
    """Create a canonical blank grid of walls."""
    grid = [[ "#" for _ in range(width)] for _ in range(height)]
    return grid


def _stamp_rect(grid: List[List[str]], x: int, y: int, w: int, h: int):
    H = len(grid); W = len(grid[0])
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if 0 <= yy < H and 0 <= xx < W:
                grid[yy][xx] = "."


def _stamp_tiles(grid: List[List[str]], tiles: Iterable[Tuple[int,int]]):
    H = len(grid); W = len(grid[0])
    for (x,y) in tiles:
        if 0 <= y < H and 0 <= x < W:
            grid[y][x] = "."


def _demo():
    # sizes
    W, H = 60, 30

    # Stage 1: base rooms + prefabs
    stage1 = _build_demo_stage(W, H)
    md1 = []  # list of room-like dicts

    # three rect rooms
    rects = [(4,4,10,6), (20,3,12,8), (38,6,14,10)]
    for (x,y,w,h) in rects:
        _stamp_rect(stage1, x, y, w, h)
        md1.append({"x": x, "y": y, "w": w, "h": h, "room_type": "rect"})

    # one prefab (irregular shape) - create a plus-shape
    prefab_tiles = []
    cx, cy = 14, 18
    for dx in range(-2,3):
        prefab_tiles.append((cx+dx, cy))
    for dy in range(-2,3):
        prefab_tiles.append((cx, cy+dy))
    _stamp_tiles(stage1, prefab_tiles)
    md1.append({"tiles": prefab_tiles, "room_type": "prefab"})

    visualize_stage(stage1, md1, "Stage 1: Rooms + Prefabs", "stage1.png")

    # Stage 2: BFS expansion (organic growth) - copy stage1 and add cave region
    stage2 = [row[:] for row in stage1]
    md2 = list(md1)  # copy existing metadata
    # carve a cave-like blob
    cave_tiles = []
    import random
    random.seed(1234)
    sx, sy = 30, 20
    frontier = [(sx, sy)]
    seen = set(frontier)
    for _ in range(220):
        if not frontier:
            break
        x,y = frontier.pop(random.randrange(len(frontier)))
        stage2[y][x] = "."
        cave_tiles.append((x,y))
        for nx,ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if 0 <= nx < W and 0 <= ny < H and (nx,ny) not in seen and random.random() < 0.55:
                frontier.append((nx,ny))
                seen.add((nx,ny))
    md2.append({"tiles": cave_tiles, "room_type": "bfs"})

    visualize_stage(stage2, md2, "Stage 2: BFS Expansion (connected regions)", "stage2.png")

    # Stage 3: extra prefabs insertion - add 2 small prefabs far from existing floors
    stage3 = [row[:] for row in stage2]
    md3 = list(md2)
    # place two small prefabs
    pf1 = [(46,2),(47,2),(46,3),(47,3),(47,4)]
    pf2 = [(2,24),(3,24),(4,24),(3,23)]
    _stamp_tiles(stage3, pf1); md3.append({"tiles": pf1, "room_type": "prefab"})
    _stamp_tiles(stage3, pf2); md3.append({"tiles": pf2, "room_type": "prefab"})
    visualize_stage(stage3, md3, "Stage 3: Extra Prefabs", "stage3.png")

    # Stage 4: Final dungeon (connect some things - simple corridors)
    stage4 = [row[:] for row in stage3]
    md4 = list(md3)

    # simple L-shaped corridor connecting center of first rect to cave center
    def carve_line(grid, x1,y1,x2,y2):
        x,y = x1,y1
        while x != x2:
            grid[y][x] = "."
            x += 1 if x2 > x1 else -1
        while y != y2:
            grid[y][x] = "."
            y += 1 if y2 > y1 else -1
        grid[y][x] = "."

    # choose centers
    r0 = rects[0]; rcx = r0[0] + r0[2]//2; rcy = r0[1] + r0[3]//2
    # approximate cave center from cave_tiles
    cave_center = cave_tiles[len(cave_tiles)//2] if cave_tiles else (30,20)
    carve_line(stage4, rcx, rcy, cave_center[0], cave_center[1])

    visualize_stage(stage4, md4, "Stage 4: Final Dungeon", "stage4.png")

    print("Demo images saved: stage1.png, stage2.png, stage3.png, stage4.png")


if __name__ == "__main__":
    _demo()