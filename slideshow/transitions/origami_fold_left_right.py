# slideshow/transitions/origami_fold_left_right.py

import numpy as np
import moderngl
from slideshow.transitions.origami_frame_transition import OrigamiFrameTransition
from slideshow.transitions.origami_render import generate_full_screen_mesh


class LeftRightFold(OrigamiFrameTransition):
    """
    Base class for left/right horizontal origami-style folds.
    Provides shared rendering methods for Phase 1 (fold) and Phase 2 (unfold).
    """

    def __init__(self, direction="left", **kwargs):
        super().__init__(**kwargs)
        self.direction = direction  # "left" or "right"

    def get_requirements(self):
        return ["moderngl", "pillow", "numpy", "ffmpeg"]

    # ---- Phase 1: fold left/right half of from_img forward ----
    def render_phase1_frames(self, ctx, from_img, to_img, num_frames=60):
        width, height = from_img.size
        fbo = ctx.framebuffer(color_attachments=[ctx.texture((width, height), 3)])
        fbo.use()
        ctx.enable(moderngl.DEPTH_TEST)

        vertices, tex_coords, indices = generate_full_screen_mesh()
        vshader = self._phase1_vertex_shader()
        fshader = self._phase1_fragment_shader()
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

            # Pass 1: background (to_img)
            program["fold_progress"] = 0.0
            program["z_offset"] = -0.1
            to_tex.use()
            vao.render()

            # Pass 2: folding mesh (from_img)
            program["fold_progress"] = progress
            program["z_offset"] = 0.0
            from_tex.use()
            vao.render()

            frame_array = np.flipud(
                np.frombuffer(fbo.read(), np.uint8).reshape((height, width, 3))
            )
            frames.append(frame_array.copy())
        return frames

    def _phase1_vertex_shader(self):
        rotate_condition = "< 0.0" if self.direction == "left" else "> 0.0"
        rotate_sign = "-" if self.direction == "left" else ""
        return f"""
        #version 330
        in vec3 in_position;
        in vec2 in_texcoord;
        uniform float fold_progress;
        uniform float z_offset;
        out vec2 uv;
        void main() {{
            vec3 pos = in_position;
            uv = in_texcoord;
            if (pos.x {rotate_condition}) {{
                float angle = fold_progress * 1.57079;
                float d = abs(pos.x);
                pos.x = {rotate_sign}d * cos(angle);
                pos.z = d * sin(angle);
            }}
            pos.z += z_offset;
            gl_Position = vec4(pos.x, pos.y, -pos.z * 0.1, 1.0);
        }}
        """

    def _phase1_fragment_shader(self):
        return """
        #version 330
        in vec2 uv;
        out vec4 fragColor;
        uniform sampler2D tex;
        void main() { fragColor = texture(tex, uv); }
        """

    # ---- Phase 2: unfold remaining half of to_img ----
    def render_phase2_frames(self, ctx, from_img, to_img, num_frames=45):
        width, height = to_img.size
        from_array, to_array = np.array(from_img), np.array(to_img)
        mid_x = width // 2

        composite_array = np.zeros_like(to_array)
        if self.direction == "left":
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

        composite_texture = ctx.texture((width, height), 3, composite_array.tobytes())
        to_texture = ctx.texture(to_img.size, 3, to_array.tobytes())
        fbo = ctx.framebuffer(color_attachments=[ctx.texture((width, height), 3)])
        fbo.use()

        # fullscreen quad for background
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

        # half-mesh for fold
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

        frames = []
        for i in range(num_frames):
            progress = min(i / (num_frames - 1), 0.99)
            ctx.clear(0, 0, 0, 1)

            composite_texture.use(0)
            bg_prog['bg'] = 0
            bg_vao.render()

            fold_prog['fold_progress'] = progress
            to_texture.use(0)
            fold_prog['tex'] = 0
            fold_vao.render()

            frame_array = np.flipud(
                np.frombuffer(fbo.read(), np.uint8).reshape((height, width, 3))
            )
            frames.append(frame_array.copy())
        return frames

    def __repr__(self):
        return f"<LeftRightFold direction={self.direction} duration={self.duration}s fps={self.fps}>"


class OrigamiFoldLeft(LeftRightFold):
    def __init__(self, **kwargs):
        super().__init__(direction="left", **kwargs)


class OrigamiFoldRight(LeftRightFold):
    def __init__(self, **kwargs):
        super().__init__(direction="right", **kwargs)
