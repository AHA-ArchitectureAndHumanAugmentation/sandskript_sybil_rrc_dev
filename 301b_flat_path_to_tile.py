#!/usr/bin/env python3
"""
301b_flat_path_to_tile.py

STANDALONE TESTING UTILITY -- projects a flat 2D path (drawn on the
ground, Z ignored) onto a chosen tile mesh, producing a JSON file in
the exact same {"strokes": [...]} format 301_convert_to_compas_json.py
expects from Lin's real depth-cam pipeline.

Exists purely so you can test 301 -> 302 -> 304 with a made-up path,
without Lin's actual capture setup running. NOT part of the main
pipeline, never called by main.py or 300's watcher -- run by hand.

Path input: a simple JSON file, e.g.
    {"points": [[0, 0], [200, 50], [400, 0], [600, -100]]}

Tile input: any mesh .obj file. Defaults to sybil_geo/surface.obj (same
surface the viewer already loads) so this runs out of the box.

--tile-id: optional, embeds a tile_id in the output JSON for testing
the tile-selection pipeline. Omit it and no tile_id field is written.

Projection: nearest-vertex, not full closest-point-on-triangle -- good
enough for a testing tool, much simpler to get right. Orientation is a
placeholder; 302 rebuilds real orientation from the sphere center
regardless, so nothing downstream depends on it being "correct" here.

Usage:
    python 301b_flat_path_to_tile.py path.json
    python 301b_flat_path_to_tile.py path.json --tile sybil_geo/some_tile.obj
    python 301b_flat_path_to_tile.py path.json --tile-id 2
"""

import argparse
import json
from pathlib import Path

from compas.datastructures import Mesh
from compas.geometry import Point, Vector

ROOT = Path(__file__).resolve().parent
DEFAULT_TILE = ROOT / "sybil_geo" / "surface.obj"


def load_flat_points(path_json):
    with open(path_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    points = [Point(xy[0], xy[1], 0.0) for xy in data["points"]]  # z ignored -- always flat
    if len(points) < 2:
        raise ValueError("Need at least 2 points to build a path.")
    return points


def nearest_vertex(mesh, point):
    """Brute-force nearest mesh vertex -- fine for one tile's vertex
    count, not meant for huge meshes."""
    best_vkey, best_dist = None, None
    for vkey in mesh.vertices():
        vpos = Point(*mesh.vertex_coordinates(vkey))
        dist = (vpos - point).length
        if best_dist is None or dist < best_dist:
            best_dist, best_vkey = dist, vkey
    return best_vkey, best_dist


def build_frame_axes(point, next_point, normal):
    """A simple, always-valid local frame. Orientation is a placeholder --
    302 rebuilds real orientation from the sphere center regardless."""
    xaxis = Vector.from_start_end(point, next_point)
    if xaxis.length < 1e-9:
        xaxis = Vector(1.0, 0.0, 0.0)
    xaxis.unitize()

    zaxis = Vector(*normal)
    if zaxis.length < 1e-9:
        zaxis = Vector(0.0, 0.0, 1.0)
    zaxis.unitize()

    yaxis = zaxis.cross(xaxis)
    if yaxis.length < 1e-6:
        yaxis = Vector(1.0, 0.0, 0.0).cross(xaxis)
    yaxis.unitize()

    return xaxis, yaxis


def project_path_onto_tile(flat_points, mesh):
    projected_points, normals = [], []

    for point in flat_points:
        vkey, dist = nearest_vertex(mesh, point)
        projected_points.append(Point(*mesh.vertex_coordinates(vkey)))
        normals.append(mesh.vertex_normal(vkey))
        print(f"Point {point} -> nearest tile vertex, {dist:.1f} mm away")

    stroke = []
    for i, point in enumerate(projected_points):
        next_point = projected_points[i + 1] if i + 1 < len(projected_points) else projected_points[i - 1]
        xaxis, yaxis = build_frame_axes(point, next_point, normals[i])
        stroke.append({
            "plane": {
                "origin": [point.x, point.y, point.z],
                "xaxis": [xaxis.x, xaxis.y, xaxis.z],
                "yaxis": [yaxis.x, yaxis.y, yaxis.z],
            }
        })
    return stroke


def main():
    parser = argparse.ArgumentParser(description="Project a flat 2D path onto a tile mesh.")
    parser.add_argument("path_json", type=Path, help="JSON file with {'points': [[x, y], ...]}")
    parser.add_argument("--tile", type=Path, default=DEFAULT_TILE, help="Tile mesh .obj file")
    parser.add_argument("--tile-id", type=int, default=None, help="Tile ID to embed, for testing the tile pipeline")
    args = parser.parse_args()

    flat_points = load_flat_points(args.path_json)
    print(f"Loaded {len(flat_points)} flat path points from {args.path_json}")

    if not args.tile.is_file():
        raise FileNotFoundError(f"Tile mesh not found: {args.tile}")
    mesh = Mesh.from_obj(str(args.tile))
    print(f"Loaded tile mesh: {args.tile} ({mesh.number_of_vertices()} vertices)")

    stroke = project_path_onto_tile(flat_points, mesh)
    data = {"strokes": [stroke]}
    if args.tile_id is not None:
        data["tile_id"] = args.tile_id

    out_dir = ROOT / "data" / "in" / f"{args.path_json.stem}_flat_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "path.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"\nSaved: {out_path}")
    print("Ready for 301, or just run main.py -- it auto-picks the newest data/in folder.")


if __name__ == "__main__":
    main()