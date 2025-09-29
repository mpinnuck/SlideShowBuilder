# slideshow/transitions/origami_render.py
"""
Shared ModernGL rendering functions for origami-style transitions.
Provides Phase 1 (fold) and a single reusable Phase 2 (unfold) function
that works for both left and right horizontal folds.
"""

import numpy as np
import moderngl

# ---------- MESH GENERATOR ----------

def generate_full_screen_mesh(segments=20, x_min=-1.0, x_max=1.0):
    """Generate vertices/indices for a mesh spanning x_min..x_max in NDC."""
    vertices, tex_coords, indices = [], [], []
    x_start = int((x_min + 1) / 2 * segments)
    x_end = int((x_max + 1) / 2 * segments)
    for y in range(segments + 1):
        for x in range(x_start, x_end + 1):
            u = x / segments
            v = y / segments
            vertices.extend([(u - 0.5) * 2.0, (v - 0.5) * 2.0, 0.0])
            tex_coords.extend([u, 1.0 - v])
    row_vertices = x_end - x_start + 1
    for y in range(segments):
        for x in range(row_vertices - 1):
            tl = y * row_vertices + x
            tr = tl + 1
            bl = (y + 1) * row_vertices + x
            br = bl + 1
            indices.extend([tl, bl, tr, tr, bl, br])
    return (np.array(vertices, np.float32),
            np.array(tex_coords, np.float32),
            np.array(indices, np.uint32))

