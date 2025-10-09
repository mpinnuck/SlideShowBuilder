# slideshow/transitions/origami_fold_center.py

import numpy as np
import moderngl
from slideshow.transitions.origami_frame_transition import (
    OrigamiFrameTransition,
    ORIGAMI_BLACK_DISCARD_THRESHOLD,
)
from slideshow.transitions.origami_render import (
    generate_full_screen_mesh_x,
    generate_full_screen_mesh_y,
)


class OrigamiFoldCenter(OrigamiFrameTransition):
    """
    Common base for center-fold origami transitions.
    Handles the GL setup and folding logic for horizontal/vertical center folds.
    """

    def __init__(self, orientation="horizontal", duration=1.0, resolution=(1920, 1080), fps=25):
        super().__init__(duration=duration, resolution=resolution, fps=fps)
        self.orientation = orientation
        self.description = f"Origami-style inward center fold ({orientation})"

    def render_phase1_frames(self, ctx, from_img, to_img, num_frames: int):
        return self._render_center_fold(ctx, from_img, to_img, num_frames, self.orientation)

    def render_phase2_frames(self, ctx, from_img, to_img, num_frames: int):
        # No unfold phase – transition ends at closed fold
        return []

    def _render_center_fold(self, ctx, from_img, to_img, num_frames: int, orientation="horizontal"):
        width, height = from_img.size
        frames = []

        # Safe RGB conversion
        from_arr = np.array(from_img.convert("RGB"))
        to_arr = np.array(to_img.convert("RGB"))
        from_tex = ctx.texture(from_img.size, 3, from_arr.tobytes())
        to_tex = ctx.texture(to_img.size, 3, to_arr.tobytes())

        # --- Fullscreen quad for TO background ---
        fs_v = np.array([-1, -1, 0, 1, -1, 0, 1, 1, 0, -1, 1, 0], np.float32)
        fs_uv = np.array([0, 1, 1, 1, 1, 0, 0, 0], np.float32)
        fs_idx = np.array([0, 1, 2, 0, 2, 3], np.uint32)

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
            uniform sampler2D tex;
            void main() {
                fragColor = texture(tex, uv);
            }
            """,
        )
        bg_vao = ctx.vertex_array(
            bg_prog,
            [
                (ctx.buffer(fs_v.tobytes()), "3f", "in_position"),
                (ctx.buffer(fs_uv.tobytes()), "2f", "in_texcoord"),
            ],
            ctx.buffer(fs_idx.tobytes()),
        )

        # --- Flap meshes ---
        if orientation == "horizontal":
            vtx_first, uv_first, idx_first = generate_full_screen_mesh_x(20, -1.0, 0.0)
            vtx_second, uv_second, idx_second = generate_full_screen_mesh_x(20, 0.0, 1.0)
            orient_block = """
                if (is_first == 1) {
                    float ox = pos.x, oz = pos.z;
                    pos.x = ox * cos(angle) - oz * sin(angle);
                    pos.z = ox * sin(angle) + oz * cos(angle);
                } else {
                    float ox = pos.x, oz = pos.z;
                    pos.x = ox * cos(-angle) - oz * sin(-angle);
                    pos.z = ox * sin(-angle) + oz * cos(-angle);
                }
            """
        else:  # vertical
            vtx_first, uv_first, idx_first = generate_full_screen_mesh_y(20, 0.0, 1.0)
            vtx_second, uv_second, idx_second = generate_full_screen_mesh_y(20, -1.0, 0.0)
            orient_block = """
                if (is_first == 1) {
                    float oy = pos.y, oz = pos.z;
                    pos.y = oy * cos(angle) - oz * sin(angle);
                    pos.z = oy * sin(angle) + oz * cos(angle);
                } else {
                    float oy = pos.y, oz = pos.z;
                    pos.y = oy * cos(-angle) - oz * sin(-angle);
                    pos.z = oy * sin(-angle) + oz * cos(-angle);
                }
            """

        # --- Shared flap shader ---
        flap_prog = ctx.program(
            vertex_shader=f"""
            #version 330
            in vec3 in_position;
            in vec2 in_texcoord;
            out vec2 uv;
            uniform float progress;
            uniform int is_first;
            void main() {{
                uv = in_texcoord;
                vec3 pos = in_position;
                float angle = progress * 1.5708; // 0→90°

                {orient_block}

                // push seam into screen
                pos.z -= progress * 0.5;
                gl_Position = vec4(pos.x, pos.y, -pos.z * 0.1, 1.0);
            }}
            """,
            fragment_shader=f"""
            #version 330
            in vec2 uv;
            out vec4 fragColor;
            uniform sampler2D tex;
            void main() {{
                vec4 c = texture(tex, uv);
                // Discard test commented out for testing
                //if (c.r < {ORIGAMI_BLACK_DISCARD_THRESHOLD} && c.g < {ORIGAMI_BLACK_DISCARD_THRESHOLD} && c.b < {ORIGAMI_BLACK_DISCARD_THRESHOLD}) {{
                //    discard;  // discard only absolute zero black padding
                //}}
                fragColor = c;
            }}
            """,
        )

        vao_first = ctx.vertex_array(
            flap_prog,
            [
                (ctx.buffer(vtx_first.tobytes()), "3f", "in_position"),
                (ctx.buffer(uv_first.tobytes()), "2f", "in_texcoord"),
            ],
            ctx.buffer(idx_first.tobytes()),
        )
        vao_second = ctx.vertex_array(
            flap_prog,
            [
                (ctx.buffer(vtx_second.tobytes()), "3f", "in_position"),
                (ctx.buffer(uv_second.tobytes()), "2f", "in_texcoord"),
            ],
            ctx.buffer(idx_second.tobytes()),
        )

        fbo = ctx.framebuffer(color_attachments=[ctx.texture((width, height), 3)])
        fbo.use()

        for j in range(num_frames):
            progress = min(1.0, j / (num_frames - 1))

            ctx.clear(0, 0, 0, 1)

            # TO background
            to_tex.use(0)
            bg_prog["tex"] = 0
            bg_vao.render()

            # First flap
            flap_prog["progress"] = progress
            flap_prog["is_first"] = 1
            from_tex.use(0)
            vao_first.render()

            # Second flap
            flap_prog["progress"] = progress
            flap_prog["is_first"] = 0
            from_tex.use(0)
            vao_second.render()

            frame = np.flipud(
                np.frombuffer(fbo.read(), np.uint8).reshape((height, width, 3))
            )
            frames.append(frame.copy())

        return frames


class OrigamiFoldCenterHoriz(OrigamiFoldCenter):
    def __init__(self, **kwargs):
        super().__init__(orientation="horizontal", **kwargs)


class OrigamiFoldCenterVert(OrigamiFoldCenter):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
