import collections
from collections import deque, Counter
from typing import List, Dict, Tuple


def connectivity_ratio(grid: List[List[str]]) -> float:
    """Return ratio of reachable floor tiles vs total floor tiles.

    Uses BFS from the first floor tile found (scanning top-left → bottom-right).
    If there are no floor tiles returns 0.0.
    """
    height = len(grid)
    width = len(grid[0]) if height else 0

    total = 0
    start = None
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == ".":
                total += 1
                if start is None:
                    start = (x, y)

    if total == 0 or start is None:
        return 0.0

    dq = deque([start])
    visited = {start}
    reachable = 0
    while dq:
        x, y = dq.popleft()
        if grid[y][x] != ".":
            continue
        reachable += 1
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited and grid[ny][nx] == ".":
                visited.add((nx, ny))
                dq.append((nx, ny))

    return reachable / total if total else 0.0


def path_metrics(grid: List[List[str]]) -> Dict:
    """Compute BFS distances from the first '.' found.

    Returns a dict with:
      - "max_distance": int
      - "average_distance": float
      - "histogram": dict(distance -> count)

    Only reachable tiles are included in results (histogram sum == reachable count).
    """
    height = len(grid)
    width = len(grid[0]) if height else 0

    start = None
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == ".":
                start = (x, y)
                break
        if start is not None:
            break

    if start is None:
        return {"max_distance": 0, "average_distance": 0.0, "histogram": {}}

    dq = deque([start])
    distances = {start: 0}
    while dq:
        x, y = dq.popleft()
        d = distances[(x, y)]
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < width and 0 <= ny < height and grid[ny][nx] == "." and (nx, ny) not in distances:
                distances[(nx, ny)] = d + 1
                dq.append((nx, ny))

    if not distances:
        return {"max_distance": 0, "average_distance": 0.0, "histogram": {}}

    counter = Counter(distances.values())
    max_distance = max(counter.keys())
    avg_distance = sum(distances.values()) / len(distances)

    return {
        "max_distance": int(max_distance),
        "average_distance": float(avg_distance),
        "histogram": dict(sorted(counter.items()))
    }


def room_variety(rooms: List) -> Dict:
    """Return percentages (0.0-1.0) of 'rect', 'prefab', 'bfs' room types and counts.

    Returns:
      {
        "rect": 0.5,
        "prefab": 0.25,
        "bfs": 0.25,
        "counts": {"rect": 6, "prefab": 3, "bfs": 3},
        "total": 12
      }
    """
    total = len(rooms)
    counter = collections.Counter()
    for r in rooms:
        t = getattr(r, "room_type", None)
        if t is None:
            # fallback: treat unknown as 'rect'
            t = "rect"
        counter[t] += 1

    result = {}
    for key in ("rect", "prefab", "bfs"):
        cnt = counter.get(key, 0)
        result[key] = (cnt / total) if total > 0 else 0.0

    result["counts"] = {k: counter.get(k, 0) for k in ("rect", "prefab", "bfs")}
    result["total"] = total
    return result
