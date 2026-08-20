"""
tile_visualizer.py — real-time tile-status visualizer for Sybil.

Renders the ACTUAL tile meshes (loaded from surfaces/tile_*.obj) as lit 3D
geometry, viewed front-on and centered for a PORTRAIT-mounted 4K screen.
Each tile gets a screen-space frame (black outline box) and its tile ID
number at the frame's center.

CURRENT STATE (debug/look-dev):
  - Each tile is a fixed, distinct grey (not yet driven by real spray data).
  - Palette is inverted from the first pass: bright background, dark-ish
    tiles, black frame lines — swap back easily if this isn't the direction.

TODO (still pending real data):
  - TileDataSource -> replace with a live poll of tile_status.py / a JSON
    export / OSC, and the real cooldown constant from tile_selector.py.
  - Re-enable per-tile fade (currently overridden by the debug grey palette
    in on_render — search "debug grey" below).
"""

import time
import math
import re
import numpy as np
import moderngl
import moderngl_window as mglw
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Portrait: the two Iiyama 4K panels will be mounted vertically, so the
# window is built at the ROTATED resolution (OS-level rotation is assumed
# to already present this as the desktop resolution to the app).
SCREEN_SIZE = (2160, 3840)
COOLDOWN_S = 60.0 * 5.0      # TODO: replace with the real rate-limit window
SURFACES_DIR = Path("surfaces")


class TileDataSource:
    """
    Stand-in for the live data feed. Exposes exactly the shape the renderer
    needs: per-tile last-sprayed timestamp (None = never sprayed / ready),
    and which tile (if any) is currently selected.

    TODO: replace internals with a live poll of tile_status.py's data.
    """
    def __init__(self, tile_ids: list[int]):
        self.last_sprayed: dict[int, float | None] = {tid: None for tid in tile_ids}
        self.selected_tile: int | None = None
        self.selected_at: float = 0.0

    def fade_fraction(self, tile_id: int, now: float) -> float:
        """0.0 = just sprayed .. 1.0 = fully ready."""
        ts = self.last_sprayed.get(tile_id)
        if ts is None:
            return 1.0
        elapsed = now - ts
        return min(max(elapsed / COOLDOWN_S, 0.0), 1.0)

    def flash_intensity(self, tile_id: int, now: float) -> float:
        if tile_id != self.selected_tile:
            return 0.0
        dt = now - self.selected_at
        flash_duration = 0.6
        if dt > flash_duration:
            return 0.0
        return max(0.0, math.cos(dt * 18.0)) * (1.0 - dt / flash_duration)


def load_tile_mesh(path: Path):
    """Parses an OBJ into flat-shaded render data: (positions Nx3,
    normals Nx3, centroid xyz)."""
    verts = []
    faces = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("v "):
                p = line.split()
                verts.append((float(p[1]), float(p[2]), float(p[3])))
            elif line.startswith("f "):
                p = line.split()[1:]
                idx = [int(tok.split("/")[0]) - 1 for tok in p]
                for i in range(1, len(idx) - 1):
                    faces.append((idx[0], idx[i], idx[i + 1]))

    verts = np.array(verts, dtype="f4")
    positions, normals = [], []
    for a, b, c in faces:
        pa, pb, pc = verts[a], verts[b], verts[c]
        n = np.cross(pb - pa, pc - pa)
        norm = np.linalg.norm(n)
        if norm > 1e-9:
            n = n / norm
        for p in (pa, pb, pc):
            positions.append(p)
            normals.append(n)

    positions = np.array(positions, dtype="f4")
    normals = np.array(normals, dtype="f4")
    centroid = verts.mean(axis=0)
    return positions, normals, centroid


def load_all_tiles(surfaces_dir: Path = SURFACES_DIR):
    tiles = []
    all_pts = []
    for path in sorted(surfaces_dir.glob("tile_*.obj")):
        m = re.search(r"tile_(\d+)", path.stem)
        if not m:
            continue
        tile_id = int(m.group(1))
        positions, normals, centroid = load_tile_mesh(path)
        tiles.append((tile_id, positions, normals, centroid))
        all_pts.append(positions)

    if not tiles:
        raise RuntimeError(f"No tile_*.obj files found in {surfaces_dir.resolve()}")

    all_pts = np.concatenate(all_pts, axis=0)
    return tiles, all_pts.min(axis=0), all_pts.max(axis=0)


def perspective_matrix(fov_y_deg, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fov_y_deg) / 2.0)
    m = np.zeros((4, 4), dtype="f4")
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def look_at(eye, target, up):
    eye = np.array(eye, dtype="f4")
    target = np.array(target, dtype="f4")
    up = np.array(up, dtype="f4")
    f = target - eye
    f = f / np.linalg.norm(f)
    s = np.cross(f, up)
    s = s / np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.identity(4, dtype="f4")
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    m[:3, 3] = [-np.dot(s, eye), -np.dot(u, eye), np.dot(f, eye)]
    return m


def make_number_texture(ctx, number: int, size: int = 256):
    """Renders a tile number to a black-on-transparent RGBA texture."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", int(size * 0.55))
    except Exception:
        font = ImageFont.load_default()
    text = str(number)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
              text, font=font, fill=(0, 0, 0, 255))
    data = img.tobytes()
    tex = ctx.texture((size, size), 4, data)
    tex.filter = (ctx.LINEAR, ctx.LINEAR)  # no mipmaps -> no edge-bleed halo
    return tex


MESH_VERTEX_SHADER = """
#version 330
in vec3 in_position;
in vec3 in_normal;
uniform mat4 u_mvp;
uniform mat4 u_model;
out vec3 v_normal;

void main() {
    gl_Position = u_mvp * vec4(in_position, 1.0);
    v_normal = mat3(u_model) * in_normal;
}
"""

MESH_FRAGMENT_SHADER = """
#version 330
in vec3 v_normal;
out vec4 f_color;

uniform vec3 u_base_color;  // per-tile debug grey, overrides live fade for now
uniform float u_flash;      // 0..1 bloom flash intensity
const vec3 COLOR_FLASH = vec3(1.0, 1.0, 1.0);
const vec3 LIGHT_DIR = normalize(vec3(0.4, 0.6, 0.8));

void main() {
    vec3 n = normalize(v_normal);
    float ndotl = max(dot(n, LIGHT_DIR), 0.0);
    float shade = 0.6 + 0.4 * ndotl;

    vec3 col = mix(u_base_color, COLOR_FLASH, u_flash) * shade;
    col += u_flash * 0.5;
    f_color = vec4(col, 1.0);
}
"""

# Screen-space (NDC, no camera) overlay for the frame line + number sprite.
OVERLAY_VERTEX_SHADER = """
#version 330
in vec2 in_position;
in vec2 in_uv;
out vec2 v_uv;
void main() {
    gl_Position = vec4(in_position, 0.0, 1.0);
    v_uv = in_uv;
}
"""

FRAME_FRAGMENT_SHADER = """
#version 330
out vec4 f_color;
void main() {
    f_color = vec4(0.0, 0.0, 0.0, 1.0);   // black frame line
}
"""

NUMBER_FRAGMENT_SHADER = """
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D u_tex;
void main() {
    f_color = texture(u_tex, v_uv);
}
"""


class TileVisualizer(mglw.WindowConfig):
    gl_version = (3, 3)
    title = "Sybil — Tile Status"
    window_size = SCREEN_SIZE
    aspect_ratio = None
    resizable = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.tiles, bbox_min, bbox_max = load_all_tiles()
        tile_ids = [t[0] for t in self.tiles]
        self.data = TileDataSource(tile_ids)

        center = (bbox_min + bbox_max) / 2.0
        self.center = center

        # Fit the camera distance to the object's actual dimensions against
        # the portrait aspect. Camera is ROLLED 90° (up=X instead of Z) so
        # the object's WIDE axis (X) maps to the screen's TALL axis — the
        # object is much wider than tall, and the screen is much taller
        # than wide, so this fills the portrait frame properly instead of
        # squeezing the wide object into a thin horizontal strip.
        half_x = (bbox_max[0] - bbox_min[0]) / 2.0   # object width -> screen height
        half_z = (bbox_max[2] - bbox_min[2]) / 2.0   # object height -> screen width
        fov_y_deg = 35.0
        aspect = SCREEN_SIZE[0] / SCREEN_SIZE[1]
        v_half = math.radians(fov_y_deg) / 2.0
        h_half = math.atan(aspect * math.tan(v_half))
        dist_for_screen_width = half_z / math.tan(h_half)
        dist_for_screen_height = half_x / math.tan(v_half)
        self.distance = max(dist_for_screen_width, dist_for_screen_height) * 1.22
        self.eye = center + np.array([0.0, -self.distance, 0.0], dtype="f4")

        proj = perspective_matrix(fov_y_deg, aspect, self.distance * 0.1, self.distance * 3.0)
        view = look_at(self.eye, self.center, up=(1.0, 0.0, 0.0))  # rolled 90°
        model = np.identity(4, dtype="f4")
        self.mvp = proj @ view @ model  # camera is static -> compute once

        # DEBUG PALETTE: distinct, inverted greys per tile (dark-ish shapes
        # on a bright background). Swap back to fade-driven color once the
        # real data source is wired in — see TileDataSource.fade_fraction.
        self.debug_colors = {}
        n = len(self.tiles)
        for i, (tile_id, _p, _n_arr, _c) in enumerate(self.tiles):
            g = 0.80 - 0.55 * (i / max(n - 1, 1))   # inverted vs. first pass
            self.debug_colors[tile_id] = (g, g, g)

        # ── Mesh program + per-tile VAOs ────────────────────────────────
        self.mesh_prog = self.ctx.program(
            vertex_shader=MESH_VERTEX_SHADER, fragment_shader=MESH_FRAGMENT_SHADER
        )
        self.tile_vaos = {}
        for tile_id, positions, normals, _centroid in self.tiles:
            vbo_pos = self.ctx.buffer(positions.tobytes())
            vbo_norm = self.ctx.buffer(normals.tobytes())
            vao = self.ctx.vertex_array(
                self.mesh_prog,
                [(vbo_pos, "3f", "in_position"), (vbo_norm, "3f", "in_normal")],
            )
            self.tile_vaos[tile_id] = (vao, positions.shape[0])

        # ── Screen-space frame + number overlay, precomputed once since
        # the camera is static ─────────────────────────────────────────
        self.frame_prog = self.ctx.program(
            vertex_shader=OVERLAY_VERTEX_SHADER, fragment_shader=FRAME_FRAGMENT_SHADER
        )
        self.number_prog = self.ctx.program(
            vertex_shader=OVERLAY_VERTEX_SHADER, fragment_shader=NUMBER_FRAGMENT_SHADER
        )

        self.frame_vaos = {}
        self.number_vaos = {}
        self.number_textures = {}
        pad = 0.03  # small margin outside the mesh's exact screen bbox

        for tile_id, positions, _normals, _centroid in self.tiles:
            ones = np.ones((positions.shape[0], 1), dtype="f4")
            hom = np.concatenate([positions, ones], axis=1)
            clip = hom @ self.mvp.T
            ndc = clip[:, :2] / clip[:, 3:4]
            x_min, y_min = ndc.min(axis=0)
            x_max, y_max = ndc.max(axis=0)
            w, h = x_max - x_min, y_max - y_min
            x_min -= w * pad; x_max += w * pad
            y_min -= h * pad; y_max += h * pad

            # Frame: a line loop around the (padded) bbox.
            corners = np.array([
                [x_min, y_min], [x_max, y_min],
                [x_max, y_max], [x_min, y_max],
            ], dtype="f4")
            vbo = self.ctx.buffer(corners.tobytes())
            vao = self.ctx.vertex_array(self.frame_prog, [(vbo, "2f", "in_position")])
            self.frame_vaos[tile_id] = vao

            # Number sprite: a small textured quad centered in the bbox,
            # sized relative to the SMALLER of the bbox's width/height so
            # it never overflows a narrow tile.
            cx, cy = (x_min + x_max) / 2.0, (y_min + y_max) / 2.0
            half = min(w, h) * 0.28
            quad = np.array([
                [cx - half, cy - half, 0.0, 1.0],
                [cx + half, cy - half, 1.0, 1.0],
                [cx - half, cy + half, 0.0, 0.0],
                [cx + half, cy + half, 1.0, 0.0],
            ], dtype="f4")
            vbo_q = self.ctx.buffer(quad.tobytes())
            vao_q = self.ctx.vertex_array(
                self.number_prog, [(vbo_q, "2f 2f", "in_position", "in_uv")]
            )
            self.number_vaos[tile_id] = vao_q
            self.number_textures[tile_id] = make_number_texture(self.ctx, tile_id)

        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.ctx.line_width = 3.0

    def on_render(self, time_s: float, frametime: float):
        # Inverted palette: bright background instead of dark.
        self.ctx.clear(0.93, 0.93, 0.95, depth=1.0)
        now = time.time()

        self.mesh_prog["u_mvp"].write(self.mvp.T.astype("f4").tobytes())
        self.mesh_prog["u_model"].write(np.identity(4, dtype="f4").tobytes())

        for tile_id, (vao, n_verts) in self.tile_vaos.items():
            flash = self.data.flash_intensity(tile_id, now)
            self.mesh_prog["u_base_color"].value = self.debug_colors[tile_id]
            self.mesh_prog["u_flash"].value = flash
            vao.render(moderngl.TRIANGLES)

        for tile_id, vao in self.frame_vaos.items():
            vao.render(moderngl.LINE_LOOP)

        self.ctx.disable(moderngl.DEPTH_TEST)  # overlay must never be hidden/z-fought
        for tile_id, vao in self.number_vaos.items():
            self.number_textures[tile_id].use(0)
            self.number_prog["u_tex"].value = 0
            vao.render(moderngl.TRIANGLE_STRIP)
        self.ctx.enable(moderngl.DEPTH_TEST)

    def on_key_event(self, key, action, modifiers):
        if action == self.wnd.keys.ACTION_PRESS:
            if key == self.wnd.keys.SPACE:
                import random
                tid = random.choice(list(self.tile_vaos.keys()))
                self.data.selected_tile = tid
                self.data.selected_at = time.time()
                self.data.last_sprayed[tid] = time.time()
                print(f"[demo] selected + sprayed tile {tid}")


if __name__ == "__main__":
    mglw.run_window_config(TileVisualizer)