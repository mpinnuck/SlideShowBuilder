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

# ---------- PHASE 1: FOLD FUNCTIONS ----------

def render_phase1_frames_left(ctx, from_img, to_img, num_frames=60):
    """Fold LEFT half of FROM forward, revealing TO-left background."""
    width, height = from_img.size
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((width, height), 3)])
    fbo.use()
    ctx.enable(moderngl.DEPTH_TEST)

    vertices, tex_coords, indices = generate_full_screen_mesh()
    vshader = '''
    #version 330
    in vec3 in_position;
    in vec2 in_texcoord;
    uniform float fold_progress;
    uniform float z_offset;
    out vec2 uv;
    void main() {
        vec3 pos = in_position;
        uv = in_texcoord;
        if (pos.x < 0.0) { // LEFT half rotates forward
            float angle = fold_progress * 1.57079;
            float d = abs(pos.x);
            pos.x = -d * cos(angle);
            pos.z = d * sin(angle);
        }
        pos.z += z_offset;
        gl_Position = vec4(pos.x, pos.y, -pos.z * 0.1, 1.0);
    }
    '''
    fshader = '''
    #version 330
    in vec2 uv;
    out vec4 fragColor;
    uniform sampler2D tex;
    void main() { fragColor = texture(tex, uv); }
    '''
    program = ctx.program(vertex_shader=vshader, fragment_shader=fshader)
    vao = ctx.vertex_array(program, [
        (ctx.buffer(vertices.tobytes()), "3f", "in_position"),
        (ctx.buffer(tex_coords.tobytes()), "2f", "in_texcoord")
    ], ctx.buffer(indices.tobytes()))

    from_tex = ctx.texture(from_img.size, 3, from_img.tobytes())
    to_tex = ctx.texture(to_img.size, 3, to_img.tobytes())

    frames = []
    for i in range(num_frames):
        progress = min(i / (num_frames - 1), 0.99)
        ctx.clear(0, 0, 0, 1)
        ctx.enable(moderngl.DEPTH_TEST)

        program["fold_progress"] = 0.0
        program["z_offset"] = -0.1
        to_tex.use()
        vao.render()

        program["fold_progress"] = progress
        program["z_offset"] = 0.0
        from_tex.use()
        vao.render()

        frame_array = np.flipud(
            np.frombuffer(fbo.read(), np.uint8).reshape((height, width, 3))
        )
        frames.append(frame_array.copy())
    return frames

def render_phase1_frames_right(ctx, from_img, to_img, num_frames=60):
    """Fold RIGHT half of FROM forward, revealing TO-right background."""
    width, height = from_img.size
    fbo = ctx.framebuffer(color_attachments=[ctx.texture((width, height), 3)])
    fbo.use()
    ctx.enable(moderngl.DEPTH_TEST)

    vertices, tex_coords, indices = generate_full_screen_mesh()
    vshader = '''
    #version 330
    in vec3 in_position;
    in vec2 in_texcoord;
    uniform float fold_progress;
    uniform float z_offset;
    out vec2 uv;
    void main() {
        vec3 pos = in_position;
        uv = in_texcoord;
        if (pos.x > 0.0) { // RIGHT half rotates forward
            float angle = fold_progress * 1.57079;
            float d = abs(pos.x);
            pos.x = d * cos(angle);
            pos.z = d * sin(angle);
        }
        pos.z += z_offset;
        gl_Position = vec4(pos.x, pos.y, -pos.z * 0.1, 1.0);
    }
    '''
    fshader = '''
    #version 330
    in vec2 uv;
    out vec4 fragColor;
    uniform sampler2D tex;
    void main() { fragColor = texture(tex, uv); }
    '''
    program = ctx.program(vertex_shader=vshader, fragment_shader=fshader)
    vao = ctx.vertex_array(program, [
        (ctx.buffer(vertices.tobytes()), "3f", "in_position"),
        (ctx.buffer(tex_coords.tobytes()), "2f", "in_texcoord")
    ], ctx.buffer(indices.tobytes()))

    from_tex = ctx.texture(from_img.size, 3, from_img.tobytes())
    to_tex = ctx.texture(to_img.size, 3, to_img.tobytes())

    frames = []
    for i in range(num_frames):
        progress = min(i / (num_frames - 1), 0.99)
        ctx.clear(0, 0, 0, 1)
        ctx.enable(moderngl.DEPTH_TEST)

        program["fold_progress"] = 0.0
        program["z_offset"] = -0.1
        to_tex.use()
        vao.render()

        program["fold_progress"] = progress
        program["z_offset"] = 0.0
        from_tex.use()
        vao.render()

        frame_array = np.flipud(
            np.frombuffer(fbo.read(), np.uint8).reshape((height, width, 3))
        )
        frames.append(frame_array.copy())
    return frames

# ---------- SHARED PHASE 2: UNFOLD FUNCTION ----------

def render_phase2_frames(ctx, to_img, from_img, num_frames=45, direction="right"):
    """Shared Phase 2 renderer with full-screen background draw first."""
    width, height = to_img.size
    to_array, from_array = np.array(to_img), np.array(from_img)
    mid_x = width // 2

    composite_array = np.zeros_like(to_array)
    if direction == "right":
        composite_array[:, :mid_x] = to_array[:, :mid_x]
        composite_array[:, mid_x:] = from_array[:, mid_x:]
        x_min, x_max = 0.0, 1.0
        discard_test = "if (uv.x < 0.5) discard;"
        pos_expr = "pos.x = pos.x * cos(angle); pos.z = pos.x * sin(angle);"
    else:
        composite_array[:, :mid_x] = from_array[:, :mid_x]
        composite_array[:, mid_x:] = to_array[:, mid_x:]
        x_min, x_max = -1.0, 0.0
        discard_test = "if (uv.x > 0.5) discard;"
        pos_expr = "pos.x = pos.x * cos(angle); pos.z = -pos.x * sin(angle);"

    # Create textures
    composite_texture = ctx.texture((width, height), 3, composite_array.tobytes())
    to_texture = ctx.texture(to_img.size, 3, to_array.tobytes())

    fbo = ctx.framebuffer(color_attachments=[ctx.texture((width, height), 3)])
    fbo.use()

    # ---- FULLSCREEN QUAD for background ----
    fullscreen_vertices = np.array([-1,-1,0,  1,-1,0,  1,1,0,  -1,1,0], np.float32)
    fullscreen_uvs = np.array([0,1,  1,1,  1,0,  0,0], np.float32)
    fullscreen_idx = np.array([0,1,2,  0,2,3], np.uint32)

    bg_prog = ctx.program(
        vertex_shader="""
        #version 330
        in vec3 in_position;
        in vec2 in_texcoord;
        out vec2 uv;
        void main() {
            uv = in_texcoord;
            gl_Position = vec4(in_position, 1.0);
        }
        """,
        fragment_shader="""
        #version 330
        in vec2 uv;
        out vec4 fragColor;
        uniform sampler2D bg;
        void main() { fragColor = texture(bg, uv); }
        """
    )
    bg_vao = ctx.vertex_array(bg_prog, [
        (ctx.buffer(fullscreen_vertices.tobytes()), '3f', 'in_position'),
        (ctx.buffer(fullscreen_uvs.tobytes()), '2f', 'in_texcoord')
    ], ctx.buffer(fullscreen_idx.tobytes()))

    # ---- HALF-MESH for fold ----
    vertices, tex_coords, indices = generate_full_screen_mesh(20, x_min, x_max)
    fold_prog = ctx.program(
        vertex_shader=f"""
        #version 330
        in vec3 in_position;
        in vec2 in_texcoord;
        out vec2 uv;
        uniform float fold_progress;
        void main() {{
            uv = in_texcoord;
            vec3 pos = in_position;
            float angle = (1.0 - fold_progress) * 1.57079;
            {pos_expr}
            gl_Position = vec4(pos.x, pos.y, -pos.z * 0.1, 1.0);
        }}
        """,
        fragment_shader=f"""
        #version 330
        in vec2 uv;
        out vec4 fragColor;
        uniform sampler2D tex;
        void main() {{
            {discard_test}
            fragColor = texture(tex, uv);
        }}
        """
    )
    fold_vao = ctx.vertex_array(fold_prog, [
        (ctx.buffer(vertices.tobytes()), '3f', 'in_position'),
        (ctx.buffer(tex_coords.tobytes()), '2f', 'in_texcoord')
    ], ctx.buffer(indices.tobytes()))

    # ---- Render Loop ----
    frames = []
    for i in range(num_frames):
        progress = min(i / (num_frames - 1), 0.99)
        ctx.clear(0, 0, 0, 1)

        ctx.disable(moderngl.DEPTH_TEST)

        # Pass 1: full background
        composite_texture.use(0)
        bg_prog['bg'] = 0
        bg_vao.render()

        # Pass 2: folding mesh
        fold_prog['fold_progress'] = progress
        to_texture.use(0)
        fold_prog['tex'] = 0
        fold_vao.render()

        frame_array = np.flipud(
            np.frombuffer(fbo.read(), np.uint8).reshape((height, width, 3))
        )
        frames.append(frame_array.copy())

    return frames
