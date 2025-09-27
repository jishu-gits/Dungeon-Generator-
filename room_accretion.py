import random
import collections
from dataclasses import dataclass
from typing import List, Optional
from evaluation import connectivity_ratio, path_metrics, room_variety

# Tile definitions
WALL = "#"
FLOOR = "."


@dataclass
class DungeonConfig:
    """Configuration for dungeon generation.

    Attributes:
        map_width: Width of the dungeon map in tiles.
        map_height: Height of the dungeon map in tiles.
        num_rooms: Target number of rooms to generate (including the seed room).
        room_min_size: Minimum size (both width and height) of a generated room.
        room_max_size: Maximum size (both width and height) of a generated room.
        corridor_width: Thickness of corridors in tiles (1 = single-tile corridors).
        seed: Optional RNG seed for reproducible output.
    """
    # map_width: int = 60
    # map_height: int = 30
    # num_rooms: int = 12
    # room_min_size: int = 4
    # room_max_size: int = 8
    # corridor_width: int = 1
    # seed: Optional[int] = None

    def __init__(self, valdict):
        self.map_width=valdict["map_width"]
        self.map_height=valdict["map_height"]
        self.num_rooms=valdict["num_rooms"]
        self.room_min_size=valdict["room_min_size"]
        self.room_max_size=valdict["room_max_size"]
        self.corridor_width=valdict["corridor_width"]
        self.seed =valdict["seed"]


class Room:
    """Simple axis-aligned rectangular room.

    Attributes:
        x, y: Top-left corner of the room (tile coordinates).
        w, h: Width and height of the room in tiles.
        room_type: classification ("rect" by default)
    """

    def __init__(self, x: int, y: int, w: int, h: int) -> None:
        # Initialize room with position (x,y) and dimensions (width,height)
        self.x, self.y, self.w, self.h = x, y, w, h
        # New: tag room type for later statistics ("rect" for normal rooms)
        self.room_type = "rect"

    def intersects(self, other: "Room") -> bool:
        """Return True if this room overlaps (intersects) with another room."""
        return not (
            self.x + self.w < other.x
            or self.x > other.x + other.w
            or self.y + self.h < other.y
            or self.y > other.y + other.h
        )


# Prefab room layouts: list of layouts where each layout is a list of strings
# '#' represents wall, '.' represents floor. Layouts are small patterns that
# can be stamped into the dungeon map.
PREFABS = [
    # Cross-shaped prefab (floor arms with walls around)
    [
        "#####",
        "#...#",
        "#.#.#",
        "#...#",
        "#####",
    ],
    # T-junction prefab (a T-shaped open area)
    [
        "#.#.#",
        "#...#",
        ".#..#",
        "#...#",
        ".#.#.",
    ],
    # Rounded-ish room approximation
    [
        " #### ",
        "#....#",
        "#....#",
        "#....#",
        " #### ",
    ],
]


class PrefabRoom(Room):
    """Room defined by a prefab layout (list of strings).

    The width and height are derived from the layout dimensions. The layout
    itself is kept so it can be stamped into the dungeon map when carving.
    """

    def __init__(self, x: int, y: int, layout: List[str]) -> None:
        h = len(layout)
        w = max((len(row) for row in layout), default=0)
        super().__init__(x, y, w, h)
        self.layout = layout
        # New: mark this as a prefab room for variety tracking
        self.room_type = "prefab"


class DungeonGenerator:
    """Dungeon generator that uses a DungeonConfig to control generation.

    Methods mirror the original script but use configuration values and
    provide docstrings for clarity.
    """

    def __init__(self, config) -> None:
        """Initialize generator state and RNG.

        Args:
            config: DungeonConfig instance with generation parameters.
        """
        self.config = config
        if config.seed is not None:
            random.seed(config.seed)

        self.width = config.map_width
        self.height = config.map_height
        # Initialize map full of walls
        self.map: List[List[str]] = [[WALL for _ in range(self.width)] for _ in range(self.height)]
        # Keep track of rooms placed (rectangular and prefabs)
        self.rooms: List[Room] = []

    def carve_room(self, room: Room) -> None:
        """Carve out a rectangular room by setting floor tiles inside its bounds.

        Ensures carving stays within map bounds.
        """
        for y in range(room.y, room.y + room.h):
            for x in range(room.x, room.x + room.w):
                if 0 <= x < self.width and 0 <= y < self.height:
                    self.map[y][x] = FLOOR

    def carve_prefab(self, prefab_room: PrefabRoom) -> None:
        """Carve a prefab layout into the dungeon map.

        Only '.' tiles from the prefab are copied into the map; '#' are left
        as existing tiles (usually walls).
        """
        for row_idx, row in enumerate(prefab_room.layout):
            for col_idx, ch in enumerate(row):
                if ch == '.':
                    x = prefab_room.x + col_idx
                    y = prefab_room.y + row_idx
                    if 0 <= x < self.width and 0 <= y < self.height:
                        self.map[y][x] = FLOOR

    def carve_line(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Carve a straight corridor between (x1,y1) and (x2,y2).

        Corridors are axis-aligned in this implementation. corridor_width
        from the config is used to make corridors thicker than one tile.
        """
        cw = max(1, self.config.corridor_width)
        half = cw // 2

        if y1 == y2:
            # Horizontal corridor
            for x in range(min(x1, x2), max(x1, x2) + 1):
                for dy in range(-half, cw - half):
                    y = y1 + dy
                    if 0 <= x < self.width and 0 <= y < self.height:
                        self.map[y][x] = FLOOR
        elif x1 == x2:
            # Vertical corridor
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for dx in range(-half, cw - half):
                    x = x1 + dx
                    if 0 <= x < self.width and 0 <= y < self.height:
                        self.map[y][x] = FLOOR
        else:
            # Should not happen for L-shaped corridor segments, but handle gracefully
            # by drawing a simple straight line using Bresenham-like stepping.
            dx = 1 if x2 > x1 else -1
            dy = 1 if y2 > y1 else -1
            x, y = x1, y1
            while x != x2 or y != y2:
                if 0 <= x < self.width and 0 <= y < self.height:
                    self.map[y][x] = FLOOR
                if x != x2:
                    x += dx
                if y != y2:
                    y += dy

    def carve_hallway(self, r1: Room, r2: Room) -> None:
        """Connect two rooms with an L-shaped corridor between their centers.

        The corridor is created as two axis-aligned carve_line calls. The order
        (horizontal first or vertical first) is chosen randomly to add variety.
        """
        x1, y1 = r1.x + r1.w // 2, r1.y + r1.h // 2
        x2, y2 = r2.x + r2.w // 2, r2.y + r2.h // 2

        if random.choice([True, False]):
            self.carve_line(x1, y1, x2, y1)
            self.carve_line(x2, y1, x2, y2)
        else:
            self.carve_line(x1, y1, x1, y2)
            self.carve_line(x1, y2, x2, y2)

    def generate(self) -> None:
        """Run the dungeon generation process using the provided config.

        The algorithm starts with a seed room in the center and grows additional
        rooms outward by selecting an existing room as a parent and placing a
        new room adjacent to it in a random cardinal direction. Rooms that
        intersect existing rooms are discarded.
        """
        cfg = self.config

        # Create a seed room near the center
        seed_w = min(cfg.room_max_size, max(cfg.room_min_size, 6))
        seed_h = min(cfg.room_max_size, max(cfg.room_min_size, 4))
        seed = Room(self.width // 2, self.height // 2, seed_w, seed_h)
        # seed.room_type already "rect" from Room __init__
        self.rooms.append(seed)
        self.carve_room(seed)

        # Add rooms until target reached
        while len(self.rooms) < cfg.num_rooms:
            parent = random.choice(self.rooms)
            # Decide whether to place a prefab (25% chance) or a rectangular room
            if random.random() < 0.25:
                # Choose a random prefab layout
                layout = random.choice(PREFABS)
                w = max(len(r) for r in layout)
                h = len(layout)
            else:
                w = random.randint(cfg.room_min_size, cfg.room_max_size)
                h = random.randint(cfg.room_min_size, cfg.room_max_size)

            dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
            x = parent.x + dx * (parent.w + w)
            y = parent.y + dy * (parent.h + h)

            # Create either a PrefabRoom or a normal Room depending on choice
            if 'layout' in locals():
                new_room = PrefabRoom(x, y, layout)
                del layout  # clean up local so subsequent iterations don't reuse it
            else:
                new_room = Room(x, y, w, h)

            # Accept the new room only if it doesn't intersect any existing room
            if not any(new_room.intersects(r) for r in self.rooms):
                self.rooms.append(new_room)
                # Carve using the appropriate method
                if isinstance(new_room, PrefabRoom):
                    self.carve_prefab(new_room)
                else:
                    self.carve_room(new_room)
                # Connect the new room to its parent
                self.carve_hallway(parent, new_room)

    def display(self) -> None:
        """Print the dungeon map to stdout."""
        for row in self.map:
            print("".join(row))


# BFSDungeonGenerator: carve floors using BFS expansion
class BFSDungeonGenerator:
    """BFS-based dungeon generator.

    Starts from a start position (default center) and expands using BFS until
    a target coverage ratio of the map is carved into floor tiles.
    """

    def __init__(self, config: DungeonConfig) -> None:
        """Initialize BFS generator with the same config structure.

        Args:
            config: DungeonConfig with map dimensions and optional seed.
        """
        self.config = config
        if config.seed is not None:
            random.seed(config.seed)

        self.width = config.map_width
        self.height = config.map_height
        # Initialize map full of walls
        self.map: List[List[str]] = [[WALL for _ in range(self.width)] for _ in range(self.height)]
        # New: record bfs-derived room regions as bounding boxes for variety stats
        self.rooms: List[Room] = []

    def in_bounds(self, x: int, y: int) -> bool:
        """Return True if (x,y) is inside the map bounds."""
        return 0 <= x < self.width and 0 <= y < self.height

    def neighbors(self, x: int, y: int):
        """Yield 4-directional neighbor coordinates for (x,y)."""
        yield (x + 1, y)
        yield (x - 1, y)
        yield (x, y + 1)
        yield (x, y - 1)

    def generate(self, start: tuple = None, coverage_ratio: float = 0.25) -> None:
        """Perform BFS carving starting at `start` until coverage ratio reached.

        Args:
            start: Optional (x,y) start position. Defaults to map center.
            coverage_ratio: Fraction of total tiles to carve (0 < coverage_ratio <= 1).
        """
        if start is None:
            start = (self.width // 2, self.height // 2)

        total_tiles = self.width * self.height
        target = max(1, int(total_tiles * max(0.0, min(1.0, coverage_ratio))))

        dq = collections.deque()
        visited = set()

        sx, sy = start
        if not self.in_bounds(sx, sy):
            # If provided start is out of bounds, fall back to center
            sx, sy = self.width // 2, self.height // 2

        dq.append((sx, sy))

        carved = 0
        while dq and carved < target:
            x, y = dq.popleft()
            if (x, y) in visited:
                continue
            visited.add((x, y))

            if not self.in_bounds(x, y):
                continue

            # Carve this tile
            if self.map[y][x] != FLOOR:
                self.map[y][x] = FLOOR
                carved += 1

            # Collect neighbors, shuffle for variety, then enqueue
            nbrs = [n for n in self.neighbors(x, y) if self.in_bounds(n[0], n[1]) and n not in visited]
            random.shuffle(nbrs)
            for nx, ny in nbrs:
                dq.append((nx, ny))

        # After carving, compute connected floor components and record each as a Room-like bbox
        self.rooms = []
        seen = set()
        for y in range(self.height):
            for x in range(self.width):
                if self.map[y][x] == FLOOR and (x, y) not in seen:
                    # flood component
                    q = collections.deque([(x, y)])
                    seen.add((x, y))
                    minx = maxx = x
                    miny = maxy = y
                    comp = [(x, y)]
                    while q:
                        cx, cy = q.popleft()
                        for nx, ny in self.neighbors(cx, cy):
                            if 0 <= nx < self.width and 0 <= ny < self.height and (nx, ny) not in seen and self.map[ny][nx] == FLOOR:
                                seen.add((nx, ny))
                                q.append((nx, ny))
                                comp.append((nx, ny))
                                minx = min(minx, nx)
                                maxx = max(maxx, nx)
                                miny = min(miny, ny)
                                maxy = max(maxy, ny)
                    # create bbox room for this component
                    bbox = Room(minx, miny, maxx - minx + 1, maxy - miny + 1)
                    bbox.room_type = "bfs"
                    self.rooms.append(bbox)

    def display(self) -> None:
        """Print the BFS-carved map to stdout."""
        for row in self.map:
            print("".join(row))


class HybridDungeonGenerator:
    """Hybrid multi-stage dungeon generator.

    Pipeline:
      1) Room stage (DungeonGenerator) — rectangular rooms + prefabs.
      2) BFS stage (BFSDungeonGenerator) — organic expansion, merged only where connected.
      3) Prefab stage — place a few additional prefabs and connect them.

    The class maintains a single self.map that all stages write into.
    """

    def __init__(self, config: DungeonConfig) -> None:
        self.config = config
        if config.seed is not None:
            random.seed(config.seed)
        self.width = config.map_width
        self.height = config.map_height
        # Shared map initialized to walls
        self.map: List[List[str]] = [[WALL for _ in range(self.width)] for _ in range(self.height)]
        # Track rooms placed across stages for variety statistics
        self.rooms: List[Room] = []

    # --- Helper utilities -------------------------------------------------
    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def _neighbors4(self, x: int, y: int):
        yield (x + 1, y)
        yield (x - 1, y)
        yield (x, y + 1)
        yield (x, y - 1)

    def _merge_room_map(self, src_map: List[List[str]]) -> None:
        """Merge floors from a source map into self.map (rooms stage).
        Simple: copy any FLOOR cells from src_map into self.map.
        """
        for y in range(self.height):
            for x in range(self.width):
                if src_map[y][x] == FLOOR:
                    self.map[y][x] = FLOOR

    def _merge_bfs_map_connected(self, bfs_map: List[List[str]]) -> None:
        """Merge BFS-carved floors but only those that are connected to existing floors.

        Strategy:
          - Collect BFS floor tiles.
          - Find BFS floor tiles that are adjacent (4-dir) to current self.map floors.
          - Flood-fill across BFS floor tiles starting from those frontier tiles,
            copying them into self.map as we visit them.
        """
        bfs_floors = {(x, y) for y in range(self.height) for x in range(self.width) if bfs_map[y][x] == FLOOR}
        if not bfs_floors:
            return

        # frontier: BFS floor tiles adjacent to existing hybrid floors
        frontier = collections.deque()
        visited = set()
        for (x, y) in list(bfs_floors):
            for nx, ny in self._neighbors4(x, y):
                if self._in_bounds(nx, ny) and self.map[ny][nx] == FLOOR:
                    frontier.append((x, y))
                    visited.add((x, y))
                    break

        # Flood from frontier across bfs_floors, copying into hybrid map
        while frontier:
            x, y = frontier.popleft()
            self.map[y][x] = FLOOR
            for nx, ny in self._neighbors4(x, y):
                if (nx, ny) in bfs_floors and (nx, ny) not in visited:
                    visited.add((nx, ny))
                    frontier.append((nx, ny))

    def _can_place_prefab(self, prefab: List[str], x: int, y: int) -> bool:
        """Return True if prefab's floor tiles would all land on walls inside hybrid map."""
        for ry, row in enumerate(prefab):
            for rx, ch in enumerate(row):
                if ch == '.':
                    px, py = x + rx, y + ry
                    if not self._in_bounds(px, py) or self.map[py][px] == FLOOR:
                        return False
        return True

    def _place_prefab(self, prefab: List[str], x: int, y: int) -> PrefabRoom:
        """Carve prefab floor tiles into hybrid map and return a PrefabRoom instance."""
        pr = PrefabRoom(x, y, prefab)
        for ry, row in enumerate(prefab):
            for rx, ch in enumerate(row):
                if ch == '.':
                    px, py = x + rx, y + ry
                    if self._in_bounds(px, py):
                        self.map[py][px] = FLOOR
        return pr

    # --- Corridor carving helpers (operate on self.map) ------------------
    def _carve_line(self, x1: int, y1: int, x2: int, y2: int) -> None:
        cw = max(1, self.config.corridor_width)
        half = cw // 2
        if y1 == y2:
            for x in range(min(x1, x2), max(x1, x2) + 1):
                for dy in range(-half, cw - half):
                    y = y1 + dy
                    if self._in_bounds(x, y):
                        self.map[y][x] = FLOOR
        elif x1 == x2:
            for y in range(min(y1, y2), max(y1, y2) + 1):
                for dx in range(-half, cw - half):
                    x = x1 + dx
                    if self._in_bounds(x, y):
                        self.map[y][x] = FLOOR
        else:
            dx = 1 if x2 > x1 else -1
            dy = 1 if y2 > y1 else -1
            x, y = x1, y1
            while x != x2 or y != y2:
                if self._in_bounds(x, y):
                    self.map[y][x] = FLOOR
                if x != x2:
                    x += dx
                if y != y2:
                    y += dy

    def _carve_hallway(self, r1: Room, r2: Room) -> None:
        x1, y1 = r1.x + r1.w // 2, r1.y + r1.h // 2
        x2, y2 = r2.x + r2.w // 2, r2.y + r2.h // 2
        if random.choice([True, False]):
            self._carve_line(x1, y1, x2, y1)
            self._carve_line(x2, y1, x2, y2)
        else:
            self._carve_line(x1, y1, x1, y2)
            self._carve_line(x1, y2, x2, y2)

    # --- Pipeline stages -------------------------------------------------
    def run_room_stage(self) -> None:
        """Run DungeonGenerator to create rooms + prefabs, merge into hybrid map."""
        dg = DungeonGenerator(self.config)
        dg.generate()
        # Merge room floors
        self._merge_room_map(dg.map)
        # Record rooms (preserve their room_type attributes)
        self.rooms.extend(dg.rooms)

    def run_bfs_stage(self, coverage_ratio: float = 0.2) -> None:
        """Run BFSDungeonGenerator and merge only the portion connected to current floors."""
        bfs = BFSDungeonGenerator(self.config)
        # Start in center; BFS will carve an organic region in its own map.
        bfs.generate(start=(self.width // 2, self.height // 2), coverage_ratio=coverage_ratio)
        # Merge only BFS floor tiles connected to existing rooms/paths
        self._merge_bfs_map_connected(bfs.map)
        # Record BFS-derived rooms (bboxes) for variety stats
        # Only include BFS rooms that actually contributed tiles by checking overlap with hybrid map
        for br in bfs.rooms:
            # if the bbox contains any floor in the hybrid map, consider it part of hybrid
            contributed = False
            for yy in range(br.y, br.y + br.h):
                for xx in range(br.x, br.x + br.w):
                    if 0 <= xx < self.width and 0 <= yy < self.height and self.map[yy][xx] == FLOOR:
                        contributed = True
                        break
                if contributed:
                    break
            if contributed:
                self.rooms.append(br)

    def run_prefab_stage(self, count_min: int = 2, count_max: int = 3, tries_per_prefab: int = 80) -> None:
        """Attempt to place extra prefabs in empty regions and connect them to the dungeon."""
        to_place = random.randint(count_min, count_max)
        placed_rooms: List[PrefabRoom] = []
        prefab_choices = PREFABS[:]
        for _ in range(to_place):
            random.shuffle(prefab_choices)
            placed = False
            for prefab in prefab_choices:
                h = len(prefab)
                w = max((len(r) for r in prefab), default=0)
                for _try in range(tries_per_prefab):
                    x = random.randint(1, max(1, self.width - w - 2))
                    y = random.randint(1, max(1, self.height - h - 2))
                    if self._can_place_prefab(prefab, x, y):
                        pr = self._place_prefab(prefab, x, y)
                        # record to hybrid rooms and placed_rooms
                        self.rooms.append(pr)
                        placed_rooms.append(pr)
                        placed = True
                        break
                if placed:
                    break
        # Connect each placed prefab to the nearest existing floor tile (if any)
        existing_floors = [(x, y) for y in range(self.height) for x in range(self.width) if self.map[y][x] == FLOOR]
        for pr in placed_rooms:
            # find center of prefab
            cx = pr.x + pr.w // 2
            cy = pr.y + pr.h // 2
            # find nearest existing floor tile (by Manhattan distance)
            if not existing_floors:
                continue
            nearest = min(existing_floors, key=lambda p: abs(p[0] - cx) + abs(p[1] - cy))
            # carve an L-shaped corridor between prefab center and nearest tile
            dummy_r1 = Room(cx, cy, 1, 1)
            dummy_r2 = Room(nearest[0], nearest[1], 1, 1)
            self._carve_hallway(dummy_r1, dummy_r2)

    # --- Orchestration --------------------------------------------------
    def generate(self, debug: bool = False) -> None:
        """Run all stages in order. If debug True print the map after each stage."""
        # Stage 1: rooms + prefabs
        self.run_room_stage()
        if debug:
            print("=== Hybrid Stage: Rooms only ===")
            self.display()
            print()

        # Stage 2: BFS organic expansion (merge only connected expansion)
        self.run_bfs_stage(coverage_ratio=0.20)
        if debug:
            print("=== Hybrid Stage: Rooms + BFS expansion ===")
            self.display()
            print()

        # Stage 3: additional prefabs + connections
        self.run_prefab_stage()
        if debug:
            print("=== Hybrid Stage: Rooms + BFS + Prefabs ===")
            self.display()
            print()

    def display(self) -> None:
        for row in self.map:
            print("".join(row))


def check_connectivity(dungeon_map: List[List[str]]):
    """Check connectivity of floor tiles in a dungeon map.

    Returns:
        (reachable_count, total_count, connectivity_ratio)

    Prints a short summary message. Uses BFS from the first found floor tile.
    """
    # Find total floor tiles and a start tile
    total = 0
    start = None
    for y, row in enumerate(dungeon_map):
        for x, ch in enumerate(row):
            if ch == FLOOR:
                total += 1
                if start is None:
                    start = (x, y)

    if total == 0:
        print("No floor tiles found.")
        return 0, 0, 0.0

    # BFS from start to count reachable floor tiles
    dq = collections.deque([start])
    visited = {start}
    reachable = 0
    while dq:
        x, y = dq.popleft()
        if dungeon_map[y][x] != FLOOR:
            continue
        reachable += 1
        for nx, ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if 0 <= nx < len(dungeon_map[0]) and 0 <= ny < len(dungeon_map):
                if (nx, ny) not in visited and dungeon_map[ny][nx] == FLOOR:
                    visited.add((nx, ny))
                    dq.append((nx, ny))

    ratio = reachable / total if total else 0.0

    # Print summary message per requirements
    if ratio == 1.0:
        print("Dungeon is fully connected ✅")
    else:
        print(f"Dungeon has {reachable}/{total} connected tiles (ratio: {ratio:.3f})")

    return reachable, total, ratio


def compute_path_length_distribution(dungeon_map: List[List[str]]):
    """Compute distances from the first floor tile to all reachable floor tiles.

    Returns a dict with:
      - "max_distance": int, maximum distance found
      - "average_distance": float, average distance over reachable tiles
      - "histogram": dict mapping distance -> count

    Uses BFS for distance calculation. If no floor tiles exist returns zeros and empty histogram.
    """
    # Find start floor tile and total floor count
    height = len(dungeon_map)
    width = len(dungeon_map[0]) if height else 0
    start = None
    total_floor = 0
    for y, row in enumerate(dungeon_map):
        for x, ch in enumerate(row):
            if ch == FLOOR:
                total_floor += 1
                if start is None:
                    start = (x, y)

    if total_floor == 0 or start is None:
        return {"max_distance": 0, "average_distance": 0.0, "histogram": {}}

    # BFS to compute distances
    dq = collections.deque([start])
    distances = {start: 0}
    while dq:
        x, y = dq.popleft()
        d = distances[(x, y)]
        for nx, ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if 0 <= nx < width and 0 <= ny < height:
                if dungeon_map[ny][nx] == FLOOR and (nx, ny) not in distances:
                    distances[(nx, ny)] = d + 1
                    dq.append((nx, ny))

    if not distances:
        return {"max_distance": 0, "average_distance": 0.0, "histogram": {}}

    # Build histogram and stats
    counter = collections.Counter(distances.values())
    max_distance = max(counter.keys())
    avg_distance = sum(distances.values()) / len(distances)

    return {
        "max_distance": int(max_distance),
        "average_distance": float(avg_distance),
        "histogram": dict(sorted(counter.items()))
    }


def print_path_stats(stats: dict) -> None:
    """Print human-friendly path length statistics.

    Prints:
      - Longest path (max distance)
      - Average path length
      - First 10 histogram entries
    """
    if not stats or "histogram" not in stats:
        print("No path stats available.")
        return

    print(f"Longest path: {stats['max_distance']} steps")
    print(f"Average path length: {stats['average_distance']:.2f}")
    # Show first 10 histogram entries (sorted by distance)
    hist_items = list(stats["histogram"].items())[:10]
    preview = dict(hist_items)
    print(f"Histogram (first 10): {preview}")


# --- New: room variety analysis ---------------------------------------
def compute_room_variety(rooms: List[Room]) -> dict:
    """Compute counts and ratios of room types.

    Returns a dict mapping room_type -> {"count": int, "ratio": float}.
    """
    total = len(rooms)
    counter = collections.Counter(r.room_type for r in rooms)
    result = {}
    for t, cnt in counter.items():
        result[t] = {"count": cnt, "ratio": cnt / total if total > 0 else 0.0}
    # Ensure common keys are present even if zero
    for key in ("rect", "prefab", "bfs"):
        if key not in result:
            result[key] = {"count": 0, "ratio": 0.0}
    result["_total"] = total
    return result


def print_room_variety(stats: dict) -> None:
    """Print a short summary of room variety stats."""
    total = stats.get("_total", 0)
    print("Room Variety:")
    print(f"Total rooms recorded: {total}")
    # Print each type with counts and percentage
    for key in ("rect", "prefab", "bfs"):
        entry = stats.get(key, {"count": 0, "ratio": 0.0})
        cnt = entry["count"]
        pct = entry["ratio"] * 100
        label = "Rect" if key == "rect" else ("Prefab" if key == "prefab" else "BFS")
        print(f"{label}: {cnt} ({pct:.0f}%)")


if __name__ == "__main__":
    # Create a configuration dictionary with default values
    config_dict = {
        "map_width": 60,
        "map_height": 30,
        "num_rooms": 12,
        "room_min_size": 4,
        "room_max_size": 8,
        "corridor_width": 1,
        "seed": None
    }
    cfg = DungeonConfig(config_dict)

    print("=== DungeonGenerator (room accretion) ===")
    dg = DungeonGenerator(cfg)
    dg.generate()
    dg.display()

    # Use evaluation.py for metrics
    ratio = connectivity_ratio(dg.map)
    # Use path_metrics to derive reachable count and distances
    pstats = path_metrics(dg.map)
    reachable = sum(pstats["histogram"].values()) if pstats and "histogram" in pstats else 0
    total = sum(row.count(FLOOR) for row in dg.map)

    if ratio == 1.0:
        print("Dungeon is fully connected ✅")
    else:
        print(f"Dungeon has {reachable}/{total} connected tiles (ratio: {ratio:.3f})")

    print_path_stats(pstats)

    rv = room_variety(dg.rooms)
    # print similar style as before
    print("Room Variety:")
    print(f"Total rooms recorded: {rv.get('total', 0)}")
    counts = rv.get("counts", {})
    for label, key in (("Rect", "rect"), ("Prefab", "prefab"), ("BFS", "bfs")):
        cnt = counts.get(key, 0)
        pct = int(round((rv.get(key, 0.0) * 100))) if rv.get("total", 0) > 0 else 0
        print(f"{label}: {cnt} ({pct}%)")

    print()  # blank line between outputs
    print("=== BFSDungeonGenerator (BFS expansion) ===")
    bfs = BFSDungeonGenerator(cfg)
    # carve ~25% of the map by default
    bfs.generate(coverage_ratio=0.25)
    bfs.display()

    ratio = connectivity_ratio(bfs.map)
    pstats = path_metrics(bfs.map)
    reachable = sum(pstats["histogram"].values()) if pstats and "histogram" in pstats else 0
    total = sum(row.count(FLOOR) for row in bfs.map)
    if ratio == 1.0:
        print("Dungeon is fully connected ✅")
    else:
        print(f"Dungeon has {reachable}/{total} connected tiles (ratio: {ratio:.3f})")
    print_path_stats(pstats)

    rv = room_variety(bfs.rooms)
    print("Room Variety:")
    print(f"Total rooms recorded: {rv.get('total', 0)}")
    counts = rv.get("counts", {})
    for label, key in (("Rect", "rect"), ("Prefab", "prefab"), ("BFS", "bfs")):
        cnt = counts.get(key, 0)
        pct = int(round((rv.get(key, 0.0) * 100))) if rv.get("total", 0) > 0 else 0
        print(f"{label}: {cnt} ({pct}%)")

    print()  # blank line between outputs
    print("=== HybridDungeonGenerator (rooms → BFS → prefabs) ===")
    hybrid = HybridDungeonGenerator(cfg)
    # Pass debug=True to print intermediary stages
    hybrid.generate(debug=True)
    # final display (also printed during debug)
    print("=== Hybrid final map ===")
    hybrid.display()

    ratio = connectivity_ratio(hybrid.map)
    pstats = path_metrics(hybrid.map)
    reachable = sum(pstats["histogram"].values()) if pstats and "histogram" in pstats else 0
    total = sum(row.count(FLOOR) for row in hybrid.map)
    if ratio == 1.0:
        print("Dungeon is fully connected ✅")
    else:
        print(f"Dungeon has {reachable}/{total} connected tiles (ratio: {ratio:.3f})")
    print_path_stats(pstats)

    rv = room_variety(hybrid.rooms)
    print("Room Variety:")
    print(f"Total rooms recorded: {rv.get('total', 0)}")
    counts = rv.get("counts", {})
    for label, key in (("Rect", "rect"), ("Prefab", "prefab"), ("BFS", "bfs")):
        cnt = counts.get(key, 0)
        pct = int(round((rv.get(key, 0.0) * 100))) if rv.get("total", 0) > 0 else 0
        print(f"{label}: {cnt} ({pct}%)")


def generate_dungeon(width=60, height=30, num_rooms=10, seed=None, stage="final"):
    """
    Generate a dungeon at a specific stage and return it as a 2D grid.
    stage = "rooms", "bfs", "prefabs", "final"
    """
    import random
    if seed is not None:
        random.seed(seed)

    # Create configuration dictionary
    config_dict = {
        "map_width": width,
        "map_height": height,
        "num_rooms": num_rooms,
        "room_min_size": 4,
        "room_max_size": 8,
        "corridor_width": 1,
        "seed": seed
    }
    cfg = DungeonConfig(config_dict)

    # Choose generator based on stage
    if stage == "rooms":
        gen = DungeonGenerator(cfg)
        gen.generate()
        return gen.map
    elif stage == "bfs":
        gen = BFSDungeonGenerator(cfg)
        gen.generate()
        return gen.map
    elif stage == "prefabs" or stage == "final":
        gen = HybridDungeonGenerator(cfg)
        gen.generate()
        return gen.map
    else:
        raise ValueError(f"Unknown stage: {stage}")