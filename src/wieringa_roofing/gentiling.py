#!/usr/bin/env -S uv run
# Script to generate penrose tilings by subdivision.
# References:
# - https://preshing.com/20110831/penrose-tiling-explained/
from dataclasses import dataclass, field
from numbers import Rational
from fractions import Fraction
from math import sqrt, cos, sin
import math
import cairo


# quadratic extension field Q(sqrt(5)),
@dataclass
class QQuad:
    a: Fraction = Fraction(0)
    b: Fraction = Fraction(0)
    sq: int = 5  # square root of this number is adjoined to the rationals

    # TODO: I want anything that can be coerced to a fraction.
    def __init__(self,
        a : int | float | Rational  | Fraction = Fraction(0),
        b: int | float | Rational | Fraction = Fraction(0), sq: int = 5):
        self.a = Fraction(a)
        self.b = Fraction(b)
        self.sq = sq

    def __str__(self) -> str:
        if self.b == 0:
            return f"{self.a}"
        elif self.a == 0:
            return f"{self.b}√{self.sq}"
        else:
            return f"({self.a} + {self.b}√{self.sq})"

    def compatible(self, other: "QQuad") -> bool:
        return self.sq == other.sq

    def add(self, other: "QQuad") -> "QQuad":
        assert self.compatible(other)
        return QQuad(self.a + other.a, self.b + other.b, self.sq)

    def mul(self, other: "QQuad") -> "QQuad":
        assert self.compatible(other)
        # (a + b√sq)(c + d√sq) = (ac + bd*sq) + (ad + bc)√sq
        return QQuad(
            self.a * other.a + self.b * other.b * self.sq,
            self.a * other.b + self.b * other.a,
            self.sq
        )

    def neg(self) -> "QQuad":
        return QQuad(-self.a, -self.b, self.sq)

    def reciprocal(self) -> "QQuad":
        # 1 / (a + b√sq) = (a - b√sq) / (a^2 - b^2*sq)
        denom = self.a * self.a - self.b * self.b * self.sq
        if denom == 0:
            raise ZeroDivisionError("Cannot take reciprocal of zero")
        return QQuad(self.a / denom, -self.b / denom, self.sq)

    def sub(self, other: "QQuad") -> "QQuad":
        return self.add(other.neg())

    def div(self, other: "QQuad") -> "QQuad":
        return self.mul(other.reciprocal())

    def __add__(self, other: "QQuad") -> "QQuad":
        return self.add(other)

    def __sub__(self, other: "QQuad") -> "QQuad":
        return self.sub(other)

    def __mul__(self, other: "QQuad") -> "QQuad":
        return self.mul(other)

    def __neg__(self) -> "QQuad":
        return self.neg()

    def __truediv__(self, other: "QQuad") -> "QQuad":
        return self.div(other)

    def to_float(self) -> float:
        return self.a + self.b * sqrt(self.sq)


@dataclass
class Point2D:
    x: QQuad = field(default_factory=QQuad())
    y: QQuad = field(default_factory=QQuad())

    @staticmethod
    def zero() -> "Point2D":
        return Point2D(QQuad(0), QQuad(0))

    def add(self, other: "Point2D") -> "Point2D":
        return Point2D(self.x + other.x, self.y + other.y)

    def neg(self) -> "Point2D":
        return Point2D(-self.x, -self.y)

    def sub(self, other: "Point2D") -> "Point2D":
        return self.add(other.neg())

    def scale(self, scalar: QQuad) -> "Point2D":
        return Point2D(self.x * scalar, self.y * scalar)

    def __add__(self, other: "Point2D") -> "Point2D":
        return self.add(other)

    def __sub__(self, other: "Point2D") -> "Point2D":
        return self.sub(other)

    def __neg__(self) -> "Point2D":
        return self.neg()

    def __mul__(self, scalar: QQuad) -> "Point2D":
        return self.scale(scalar)

    def __rmul__(self, scalar: QQuad) -> "Point2D":
        return self.scale(scalar)

    def __truediv__(self, scalar: QQuad) -> "Point2D":
        return self.scale(scalar.reciprocal())
    
    @staticmethod
    def of_angle(angle: float) -> "Point2D":
        return Point2D(QQuad(cos(angle)), QQuad(sin(angle)))

    def len(self) -> float:
        return sqrt(self.x.to_float()**2 + self.y.to_float()**2)
@dataclass
class Tri:
    # vertices in the tri.
    vs: tuple[Point2D, Point2D, Point2D]
    # color.
    color: int

    def __init__(self, vs: tuple[Point2D, Point2D, Point2D], color: int):
        self.vs = vs
        self.color = color

    def A(self) -> Point2D:
        return self.vs[0]
    
    def B(self) -> Point2D:
        return self.vs[1]
    
    def C(self) -> Point2D:
        return self.vs[2]

def subdivide_tri(tri : Tri) -> list[Tri]:
    goldenRatio = QQuad(Fraction(1), Fraction(1)) / QQuad(Fraction(2))
    if tri.color == 0:
        # Subdivide red (sharp isosceles) (half kite) triangle
        Q = tri.A() + (tri.B() - tri.A()) / goldenRatio
        R = tri.B() + (tri.C() - tri.B()) / goldenRatio
        return [Tri((R, Q, tri.B()), 1), \
            Tri((Q, tri.A(), R), 0), \
            Tri((tri.C(), tri.A(), R), 0)]
    else:
        # Subdivide blue (fat isosceles) (half dart) triangle
        P = tri.C() + (tri.A() - tri.C()) / goldenRatio
        return [Tri((tri.B(), P, tri.A()), 1), \
            Tri((P, tri.C(), tri.B()), 0)]

def subdivide_tris_once(triangles : list[Tri]) -> list[Tri]:
    # 1 + sqrt(5) / 2

    # How go give type annotation? This is List[Tri]
    result : list[Tri] = []
    for tri in triangles:
        result.extend(subdivide_tri(tri))
    return result

def subdivide_tris_n(tris : list[Tri], n : int) -> list[Tri]:
    for _ in range(n):
        tris = subdivide_tris_once(tris)
    return tris


def starting_tris() -> list[Tri]:
    # Create wheel of red triangles around the origin
    triangles : list[Tri] = []
    for i in range(10):
        b : Point2D = Point2D.of_angle((2*i - 1) * math.pi / 10)
        c : Point2D = Point2D.of_angle((2*i + 1) * math.pi / 10)
        
        if i % 2 == 0:
            b, c = c, b # Make sure to mirror every second triangle
        triangles.append(Tri((b, Point2D.zero(), c), 0))
    return triangles

def color_to_rgb(color: int) -> tuple[float, float, float]:
    if color == 0:
        return (1.0, 0.35, 0.35) # red
    else:
        return (0.4, 0.4, 1.0) # blue

def draw_tri(tri : Tri, cr : cairo.Context):
    cr.move_to(tri.A().x.to_float(), tri.A().y.to_float())
    cr.line_to(tri.B().x.to_float(), tri.B().y.to_float())
    cr.line_to(tri.C().x.to_float(), tri.C().y.to_float())
    cr.close_path()
    cr.set_source_rgb(*color_to_rgb(tri.color))
    cr.fill()


def draw_tris(tris : list[Tri], cr : cairo.Context):
    for tri in tris:
        draw_tri(tri, cr)


def main():
    tris = starting_tris()
    tris = subdivide_tris_n(tris, 6)

    # Output size
    surface_width, surface_height = 800, 600

    # 1. Create surface and context
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, surface_width, surface_height)
    ctx = cairo.Context(surface)

    # 2. Define "model coordinates" (logical coordinate system)
    model_width, model_height = 1, 1  # units in your drawing space

    # 3. Compute scale to fit model into surface while preserving aspect ratio
    model2surface_x = surface_width / model_width
    model2surface_y = surface_height / model_height
    model2surface = min(model2surface_x, model2surface_y)  # uniform scaling

    # 4. Translate to center
    tx = 0.5 * model2surface_x
    ty = 0.5 * model2surface_y
    ctx.translate(tx, ty)
    ctx.scale(model2surface, model2surface)

    # Now all drawing is in model coordinates (0..100)
    draw_tris(tris, ctx)

    # 5. Save
    surface.write_to_png("tiling.png")


if __name__ == "__main__":
    main()