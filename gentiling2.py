#!/usr/bin/env -S uv run python3
import cairo
import numpy as np
from math import *
from dataclasses import dataclass, field
from typing import *
import z3.z3 as z3
import time

# Utility to get time for executing a block and print it later
class Timing():
    def __enter__(self):
        self.start_time = time.time()
        return self
    def __exit__(self, type, value, traceback):
        self.end_time = time.time()
        self.time = self.end_time - self.start_time
    def __str__(self):
        if self.time >= 1:
            return "%.3g s" % self.time
        elif self.time >= 1e-3:
            return "%.3g ms" % (self.time * 1e3)
        else:
            return "%d µs" % int(self.time * 1e6)

"""
Transformation that does
- scaling by × s
+ rotation by θ
- translation to (x,y)

[ s cos(θ)   -s sin(θ)   ox ] [ x ]
[ s sin(θ)    s cos(θ)   oy ] [ y ]
[    0            0       1 ] [ 1 ]
"""
def mktransform(x, y, theta, scale):
    theta = theta * pi / 180
    return np.matrix([
        [scale * cos(theta), -scale * sin(theta), x],
        [scale * sin(theta),  scale * cos(theta), y],
        [0, 0, 1],
    ])

def index_opp(i):
    return [3, 4, 1, 2][i - 1]
def index_nei(i):
    return [2, 3, 2, 3][i - 1]

float3: TypeAlias = tuple[float, float, float]

def cross_product(a, b) -> float3:
    return (a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0])

def norm(xyz: float3) -> float:
    x, y, z = xyz
    return (x * x + y * y + z * z) ** 0.5

def normalize(xyz) -> float3:
    x, y, z = xyz
    n = norm(xyz)
    return (x / n, y / n, z / n)

@dataclass
class Tile:
    thick: bool
    index: int
    transform: np.matrix
    point_indices: list[int] = field(default_factory=list)

    def get_point(self, lx: float, ly: float) -> tuple[float, float]:
        u = self.transform * np.matrix([[lx], [ly], [1]])
        return u[0].item(), u[1].item()

    def get_points(self) -> list[tuple[float, float]]:
        return [xy for xy, z in self.get_points_with_height()]

    def get_points_with_height(self) -> list[tuple[tuple[float, float], float]]:
        if self.thick:
            c, s = cos(54 * pi / 180), sin(54 * pi / 180)
            bot = self.get_point(0, 0)
            left = self.get_point(-c, s)
            right = self.get_point(c, s)
            top = self.get_point(0, 2 * s)

            i_bot = self.index
            i_top = index_opp(i_bot)
            i_mid = (i_bot + i_top) / 2
            return [(bot, self.index), (right, i_mid), (top, i_top), (left, i_mid)]
        else:
            c, s = cos(72 * pi / 180), sin(72 * pi / 180)
            right = self.get_point(0, 0)
            top = self.get_point(-c, s)
            left = self.get_point(-2 * c, 0)
            bottom = self.get_point(-c, -s)

            i_right = self.index
            i_left = index_opp(i_right)
            i_mid = (i_right + i_left) / 2
            return [(right, i_right), (top, i_mid), (left, i_left), (bottom, i_mid)]

    def normal(self) -> tuple[float, float, float]:
        p1, p2, p3, p4 = self.get_points_with_height()
        p1 = (p1[0][0], p1[0][1], p1[1])
        p2 = (p2[0][0], p2[0][1], p2[1])
        p3 = (p3[0][0], p3[0][1], p3[1])
        p4 = (p4[0][0], p4[0][1], p4[1])
        d1 = (p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2])
        d2 = (p4[0] - p2[0], p4[1] - p2[1], p4[2] - p2[2])
        return normalize(cross_product(d1, d2))

    def center(self) -> tuple[float, float]:
        p1, _, p2, _ = self.get_points()
        return (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2

    def subdivide(self) -> list["Tile"]:
        s = sin(54 * pi / 180)
        subscale = 1 / (2 * s)
        ind = self.index
        opp = index_opp(self.index)
        nei = index_nei(self.index)

        if self.thick:
            c = cos(54 * pi / 180)
            midx, midy = 0, 2 * s - 1 / (2 * s)
            T1 = Tile(True, opp, self.transform * mktransform(midx, midy, 180, subscale))
            T2 = Tile(True, opp, self.transform * mktransform(0, 2*s, 180-36, subscale))
            T3 = Tile(True, opp, self.transform * mktransform(0, 2*s, 180+36, subscale))
            t1 = Tile(False, nei, self.transform * mktransform(-c, s, 90+36, subscale))
            t2 = Tile(False, nei, self.transform * mktransform(c, s, 90-36, subscale))
            return [T1, T2, T3, t1, t2]
        else:
            c, s = cos(72 * pi / 180), sin(72 * pi / 180)
            T1 = Tile(True, ind, self.transform * mktransform(0, 0, 18, subscale))
            T2 = Tile(True, ind, self.transform * mktransform(0, 0, 180-18, subscale))
            t1 = Tile(False, opp, self.transform * mktransform(-2*c, 0, 270-18, subscale))
            t2 = Tile(False, opp, self.transform * mktransform(-2*c, 0, 90+18, subscale))
            return [T1, T2, t1, t2]

def mkcolor(hex: int):
    r, g, b = (hex >> 16) & 0xff, (hex >> 8) & 0xff, (hex & 0xff)
    return r / 255, g / 255, b / 255

def mkcolor_darkened(hex: int, index: int):
    r, g, b = mkcolor(hex)
    darkening_amount = [0.1, 0.4, 0.7, 1.0][index - 1]
    da = darkening_amount
    return r * da, g * da, b * da

def set_color(ctx: cairo.Context, hex: int):
    ctx.set_source_rgb(*mkcolor(hex))

def draw_tile(ctx: cairo.Context, t: Tile, color: int | None = None):
    ps = t.get_points()
    ctx.move_to(*ps[0])
    for xy in ps[1:]:
        ctx.line_to(*xy)
    ctx.close_path()

    if color is not None:
        set_color(ctx, color)
    elif t.thick:
        start, _, end, _ = t.get_points()
        gradient = cairo.LinearGradient(*start, *end)
        gradient.add_color_stop_rgb(0, *mkcolor_darkened(0x62ae19, t.index))
        gradient.add_color_stop_rgb(1, *mkcolor_darkened(0x62ae19, index_opp(t.index)))
        ctx.set_source(gradient)
    else:
        color = 0x80afe1
        # color = 0x62ae19
        start, _, end, _ = t.get_points()
        gradient = cairo.LinearGradient(*start, *end)
        gradient.add_color_stop_rgb(0, *mkcolor_darkened(color, t.index))
        gradient.add_color_stop_rgb(1, *mkcolor_darkened(color, index_opp(t.index)))
        ctx.set_source(gradient)

    ctx.fill_preserve()

    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_width(4.0)
    ctx.set_source_rgb(0, 0, 0)

    ctx.stroke()

def draw_text(ctx: cairo.Context, x: float, y: float, align: str, text: str) -> None:
    ext = ctx.text_extents(text)
    x -= ext.x_bearing
    y -= ext.y_bearing

    for c in align:
        if c == ">":
            x -= ext.width
        if c == "|":
            x -= ext.width / 2
        if c == "v":
            y -= ext.height
        if c == "-":
            y -= ext.height / 2

    ctx.move_to(x, y)
    ctx.text_path(text)
    ctx.set_source_rgb(1, 1, 1)
    ctx.fill_preserve()
    ctx.set_source_rgb(0, 0, 0)
    ctx.set_line_width(2.0)
    ctx.stroke()

def subdivide_set(tiles: list[Tile]) -> list[Tile]:
    new_tiles = []
    for t in tiles:
        new_tiles.extend(t.subdivide())
    return new_tiles

def main():
    w, h = 1080, 1080
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surface)
    ctx.translate(w / 2, h / 2)
    ctx.scale(1, 1)

    tiles = [Tile(True, 1, mktransform(0, -400, 0, 430))]
    steps = 5

    with Timing() as t:
        for i in range(steps):
            tiles = subdivide_set(tiles)
    print(f"subdivide: {t}")

    # Easiest path forward:
    # -> Construct adjacency graph by looking at point coordinates (approximately)
    # -> Solve for indices in a graph traversal manner

    points: list[tuple[tuple[float, float], list[Tile]]] = []

    def closest_point(target_x: float, target_y: float, points: Iterable[tuple[float, float]]) -> Optional[int]:
        EPSILON = 0.0001
        for i, (x, y) in enumerate(points):
            if abs(x - target_x) + abs(y - target_y) < EPSILON:
                return i
        return None

    # Filter tiles for uniqueness
    unique_tiles: list[Tile] = []
    unique_tile_centers: list[tuple[float, float]] = []

    print(f"{len(tiles)} tiles")

    with Timing() as t:
        for tile in tiles:
            x, y = tile.center()
            i = closest_point(x, y, unique_tile_centers)
            if i is None:
                unique_tiles.append(tile)
                unique_tile_centers.append((x, y))

        tiles = unique_tiles

        for tile in tiles:
            tile.point_indices = []
            for (x, y) in tile.get_points():
                i = closest_point(x, y, (p[0] for p in points))
                if i is None:
                    points.append(((x, y), []))
                    i = len(points) - 1
                points[i][1].append(tile)
                tile.point_indices.append(i)
    print(f"uniq: {t}")

    # For each i, points[i], make a height variable h_i
    # For each thick rhombus T with points (bot, right, top, left), constraint:
    #   h_right = h_left /\
    #   ((h_top = h_right + 1 /\ h_bot = h_right - 1)
    #    \/ (h_top = h_right - 1 /\ h_bot = h_right + 1))
    # For each thin rhombus t with points (right, top, left, bottom), constraint:
    #   h_top = h_bot /\
    #   ((h_right = h_top - 1 /\ h_left = h_top + 1)
    #    \/ (h_left = h_top - 1 /\ h_right = h_top + 1))

    h = [z3.Int(f"h_{i}") for i in range(len(points))]
    s = z3.Solver()

    for i in range(len(points)):
        s.add(h[i] >= 1, h[i] <= 4)

    for tile in tiles:
        if tile.thick:
            bot, right, top, left = tile.point_indices
            s.add(h[right] == h[left])
            s.add(z3.Or(z3.And(h[top] == h[right] + 1, h[bot] == h[right] - 1),
                        z3.And(h[top] == h[right] - 1, h[bot] == h[right] + 1)))
        else:
            right, top, left, bot = tile.point_indices
            s.add(h[top] == h[bot])
            s.add(z3.Or(z3.And(h[right] == h[top] - 1, h[left] == h[top] + 1),
                        z3.And(h[left] == h[top] - 1, h[right] == h[top] + 1)))

    with Timing() as t:
        if s.check() == z3.sat:
            m = s.model()
            print("sat")
            for tile in tiles:
                tile.index = m[h[tile.point_indices[0]]].py_value()
        else:
            print("unsat")
    print(f"solve: {t}")

    ctx.select_font_face("DejaVu Sans Mono", cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
    ctx.set_font_size(37)

    with Timing() as t:
        for tile in tiles:
            draw_tile(ctx, tile)

        if steps < 5:
            for ((x, y), adjacent_tiles) in points:
                radius = [4, 6, 8, 10, 12, 14, 16][len(adjacent_tiles) - 1]
                ctx.arc(x, y, radius, 0, 2*pi)
                ctx.set_source_rgb(1, 1, 1)
                ctx.fill_preserve()
                ctx.set_source_rgb(0, 0, 0)
                ctx.set_line_width(4.0)
                ctx.stroke()
    print(f"draw: {t}")

    # for i, ((x, y), _) in enumerate(points):
    #     draw_text(ctx, x + 16, y, "<-", f"{i}")

    surface.write_to_png("output/tiling.png")

    with open("output/autogen.scad", "w") as fp:
        fp.write("module autogen(thickness) {\n")
        for tile in tiles:
            nx, ny, nz = tile.normal()
            fp.write("  green() " if tile.thick else "blue() ")
            fp.write("hull() {\n")

            # fp.write("  green() " if tile.thick else "blue() ")
            fp.write("  polyhedron(points=[")
            for (x, y), z in tile.get_points_with_height():
                fp.write(f"    [{x}, {y}, {z}], ")
            fp.write("  ], faces=[[0, 1, 2, 3]]);\n")

            # fp.write("  red() " if tile.thick else "orange() ")
            fp.write("  polyhedron(points=[")
            for (x, y), z in tile.get_points_with_height():
                fp.write(f"    [{x}+{nx}*thickness, {y}+{ny}*thickness, {z}+{nz}*thickness], ")
            fp.write("  ], faces=[[0, 1, 2, 3]]);\n")
            fp.write("}\n")
        fp.write("}\n")

main()
