phi = (1 + sqrt(5)) / 2;

function regular_pentagon_area(side) =
  sqrt(5 * (5 + 2*sqrt(5))) * side * side / 4;

function triangle_area_ssa(side1, side2, angle) =
  0.5 * side1 * side2 * sin(angle);

/* In the Wieringa roofing, the ceiling tile has diagonals 1
   and phi. Within the patterns it forms pentagonal flowers
   (both convex and concave) which requires the tile to be
   angled down/up. The projection of that angled tile is the
   Penrose tile T. We can use these facts to figure out what
   projection angle is used and what scale the ceiling tile
   must be compared to T. */

/* The pentagonal flowers are invariant by rotation of 72°
   around Z, therefore the 1-edges are flat and unaffected by
   the projection. So in order to be to scale with the Penrose
   tiles (which have side length 1), the 1-edge should match
   the T tile's short diagonal, whose length is 2*cos(54). */
tile_short = 2 * cos(54);
tile_long = tile_short * phi;

/* Rhombus area */
tile_area = tile_short * tile_long / 2;
echo("tile area:", tile_area);

/* The projection of the pentagonal flower is a regular
   pentagon of side tile_short. Each triangle in the pentagon 
   contributes to one fifth of its total area and makes up
   half a tile. */
projected_tile_area = 2 * regular_pentagon_area(tile_short) / 5;
echo("projected tile area:", projected_tile_area);

/* Since the 1-edges are flat the rotation is defined by a
   single angle alpha around X. The projection multiplies the
   area by cos(alpha), so we can recover alpha. */
alpha = acos(projected_tile_area / tile_area);
echo("alpha:", alpha);

// TODO: Why doesn't it also work with surface ratio?
// T_area = triangle_area_ssa(1, 1, 72);
// tile_scale = T_area / projected_tile_area;

/* The t tile is the projection of the ceiling tiles nestled
   around the pentagons. This time the long edge of the t tile
   is flat for the projection, so we also have a single angle
   beta defining it. We can reuse the area method. */
t_area = 2 * triangle_area_ssa(1, 1, 36);
beta = acos(t_area / tile_area);
echo("beta:", beta);

/* Visualization setting: scales tiles without affecting their
   locations. Setting slightly less than 1 adds spacing. */
space_tiles = false;
tile_inherent_scale = space_tiles ? 0.95 : 1.0;

tile_height = 0.0005;
module green() { color("#62ae19") children(); }
module blue()  { color("#80afe1") children(); }
module gray()  { color("gray") children(); }

/* Ceiling tile, centered */
module tile(tr=[0,0,0]) {
  s = tile_short; l = tile_long;
  gray()
  translate([0,0,-tile_height/2]) linear_extrude(tile_height)
  translate(tr)
  scale(tile_inherent_scale)
  polygon([[-s/2,0], [0,-l/2], [s/2,0], [0,l/2]]);
}
/* Ceiling tile at vertex with long edge towards +x */
module tile_lx() { rotate(-90) tile([0, tile_long/2, 0]); }
/* Ceiling tile at vertex with short edge towards +x */
module tile_sx() { tile([tile_short/2, 0, 0]); }

/* Penrose t tile */
module t() {
  c = cos(36 / 2); s = sin(36 / 2);
  linear_extrude(tile_height)
  polygon([[-c,0], [0,s], [c,0], [0,-s]]);
}
/* Penrose T tile */
module T() {
  c = cos(72 / 2); s = sin(72 / 2);
  linear_extrude(tile_height)
  polygon([[-c,0], [0,s], [c,0], [0,-s]]);
}

module flower() {
  for(i=[0:4])
    rotate([0,alpha,72*i]) green() tile_lx();
  for(i=[0:4])
     rotate([0,0,72*i+36])
     translate([1,0,-tan(alpha) * cos(36)])
     rotate([0,beta,0])
     blue() tile_sx();
}

/*
tile();
translate([0,1.5,0]) tile_sx();
translate([0,3,0]) tile_lx();

translate([2,0,0]) rotate([0,0,90]) blue() t();
translate([4,0,0]) rotate([0,0,90]) green() T();

translate([4,3,2]) flower();

translate([7.65,0.5,0]) rotate(36) green() T();
*/

/*
translate([6,3,2]) {
  for(i=[0:4])
    rotate([0,0,72*i]) rotate([0,-beta,0]) tile(center=false);
}
*/

include <autogen.scad>;

scale([0.1, 0.1, 0]) autogen(0.1);
scale([0.1, 0.1, 3]) translate([0,0,2]) autogen(0.1);
