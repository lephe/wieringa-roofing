import cairo
import numpy as np
from math import *
from dataclasses import dataclass
import typing

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

@dataclass
class Tile:
    thick: bool
    index: int
    transform: np.matrix

    def get_point(self, lx: float, ly: float) -> tuple[float, float]:
        u = self.transform * np.matrix([[lx], [ly], [1]])
        return u[0].item(), u[1].item()

    def get_points(self) -> list[tuple[float, float]]:
        if self.thick:
            c, s = cos(54 * pi / 180), sin(54 * pi / 180)
            bot = self.get_point(0, 0)
            left = self.get_point(-c, s)
            right = self.get_point(c, s)
            top = self.get_point(0, 2 * s)
            return [bot, right, top, left]
        else:
            c, s = cos(72 * pi / 180), sin(72 * pi / 180)
            right = self.get_point(0, 0)
            top = self.get_point(-c, s)
            left = self.get_point(-2 * c, 0)
            bottom = self.get_point(-c, -s)
            return [right, top, left, bottom]

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

def subdivide_with_indices(t: Tile, n: int, origin_index: int) -> list[Tile]:
    if n == 0:
        t.index = origin_index
        return [t]

    # We have a forced index for all subdivisions
    next_forced_index = origin_index

    for sub in t.subdivide(): # lazy
        subdivide_with_indices(sub, n - 1, next_forced_index)

    ...

    t.subdivide_others()
    # propagate index

    return [sub1, ...]

def mkcolor(hex: int):
    r, g, b = (hex >> 16) & 0xff, (hex >> 8) & 0xff, (hex & 0xff)
    return r / 255, g / 255, b / 255

def mkcolor_darkened(hex: int, index: int):
    r, g, b = mkcolor(hex)
    darkening_amount = [0, 0.25, 0.5, 0.75][index - 1]
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
    ctx.scale(1, -1)

    tiles = [Tile(True, 1, mktransform(0, -400, 0, 430))]
    steps = 5

    for i in range(steps):
        tiles = subdivide_set(tiles)

    # Easiest path forward:
    # -> Construct adjacency graph by looking at point coordinates (approximately)
    # -> Solve for indices in a graph traversal manner

    for tile in tiles:
        draw_tile(ctx, tile)

    # gradient = cairo.LinearGradient(-100, 0, 100, 0)
    # gradient.add_color_stop_rgb(0, *mkcolor(0xff0000))
    # gradient.add_color_stop_rgb(1, *mkcolor(0x0000ff))
    # ctx.set_source(gradient)
    # ctx.move_to(-w / 2, -h / 2)
    # ctx.line_to(w / 2, -h / 2)
    # ctx.line_to(w / 2, h / 2)
    # ctx.line_to(-w / 2, h / 2)
    # ctx.close_path()
    # ctx.fill()

    surface.write_to_png("tiling.png")

main()
