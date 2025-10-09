# slideshow/transitions/origami_fold_slide_lr.py

import numpy as np
import moderngl
from slideshow.transitions.origami_frame_transition import (
    OrigamiFrameTransition,
    ORIGAMI_BLACK_DISCARD_THRESHOLD,
)


class OrigamiFoldSlide(OrigamiFrameTransition):
    """
    Base class for slide-style origami folds (left/right).
    - The 'from' image is split into two trapezoids (left & right of seam).
    - One outer edge slides inward, the other edge stays fixed.
    - The seam is always the midpoint between the two edges,
      and shrinks vertically for 3D illusion.
    - Black triangles above/below seam fill the gaps.
    """

    def __init__(self, direction="right", duration=1.0,
                 resolution=(1920, 1080), fps=25, min_seam_height=0.75):
        super().__init__(duration=duration, resolution=resolution, fps=fps)
        self.direction = direction  # "left" or "right"
        self.min_seam_height = min_seam_height

    def get_requirements(self):
        return ["moderngl", "numpy", "Pillow", "ffmpeg"]

    def render_phase1_frames(self, ctx, from_img, to_img, num_frames: int):
        width, height = from_img.size
        frames = []

        from_tex = ctx.texture(from_img.size, 3, np.array(from_img.convert("RGB")).tobytes())
        to_tex = ctx.texture(to_img.size, 3, np.array(to_img.convert("RGB")).tobytes())

        # --- fullscreen quad for background ---
        fs_v = np.array([-1,-1,0,  1,-1,0,  1,1,0,  -1,1,0], np.float32)
        fs_uv = np.array([0,1,  1,1,  1,0,  0,0], np.float32)
        fs_idx = np.array([0,1,2,  0,2,3], np.uint32)

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
            """
        )
        bg_vao = ctx.vertex_array(bg_prog, [
            (ctx.buffer(fs_v.tobytes()), "3f", "in_position"),
            (ctx.buffer(fs_uv.tobytes()), "2f", "in_texcoord")
        ], ctx.buffer(fs_idx.tobytes()))

        # --- shader for from-image trapezoids ---
        from_prog = ctx.program(
            vertex_shader="""
            #version 330
            in vec2 in_position;
            in vec2 in_texcoord;
            out vec2 uv;
            void main() {
                uv = in_texcoord;
                gl_Position = vec4(in_position, 0.0, 1.0);
            }
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
            """
        )

        # --- solid black program for seam-fill triangles ---
        black_prog = ctx.program(
            vertex_shader="""
            #version 330
            in vec2 in_position;
            void main() {
                gl_Position = vec4(in_position, 0.0, 1.0);
            }
            """,
            fragment_shader="""
            #version 330
            out vec4 fragColor;
            void main() {
                fragColor = vec4(0.0, 0.0, 0.0, 1.0);
            }
            """
        )

        fbo = ctx.framebuffer(color_attachments=[ctx.texture((width, height), 3)])
        fbo.use()

        for j in range(num_frames):
            progress = j / (num_frames - 1)

            if self.direction == "right":
                left_x = -1.0 + 2.0 * progress
                right_x = +1.0
            else:  # "left"
                left_x = -1.0
                right_x = +1.0 - 2.0 * progress

            # seam = midpoint
            seam_x = (left_x + right_x) * 0.5

            # shrink seam vertically
            seam_scale = max(self.min_seam_height, 1.0 - progress)
            seam_top = seam_scale
            seam_bottom = -seam_scale

            ctx.clear(0, 0, 0, 1)

            # background (to_img)
            to_tex.use(0)
            bg_prog["tex"] = 0
            bg_vao.render()

            # --- LEFT trapezoid (from left edge to seam) ---
            left_vertices = np.array([
                left_x, -1.0,
                left_x,  1.0,
                seam_x,  seam_top,
                seam_x,  seam_bottom
            ], np.float32)
            left_uvs = np.array([
                0.0, 1.0,
                0.0, 0.0,
                0.5, 0.0,
                0.5, 1.0
            ], np.float32)
            idx = np.array([0,1,2, 0,2,3], np.uint32)
            left_vao = ctx.vertex_array(from_prog, [
                (ctx.buffer(left_vertices.tobytes()), "2f", "in_position"),
                (ctx.buffer(left_uvs.tobytes()), "2f", "in_texcoord")
            ], ctx.buffer(idx.tobytes()))
            from_tex.use(0)
            left_vao.render()

            # --- RIGHT trapezoid (from seam to right edge) ---
            right_vertices = np.array([
                seam_x,  seam_bottom,
                seam_x,  seam_top,
                right_x,  1.0,
                right_x, -1.0
            ], np.float32)
            right_uvs = np.array([
                0.5, 1.0,
                0.5, 0.0,
                1.0, 0.0,
                1.0, 1.0
            ], np.float32)
            right_vao = ctx.vertex_array(from_prog, [
                (ctx.buffer(right_vertices.tobytes()), "2f", "in_position"),
                (ctx.buffer(right_uvs.tobytes()), "2f", "in_texcoord")
            ], ctx.buffer(idx.tobytes()))
            from_tex.use(0)
            right_vao.render()

            # --- black triangles above/below seam ---
            black_vertices = np.array([
                # top triangle
                left_x,  1.0,
                right_x, 1.0,
                seam_x,  seam_top,
                # bottom triangle
                left_x, -1.0,
                right_x, -1.0,
                seam_x,  seam_bottom
            ], np.float32)
            black_idx = np.array([0,1,2, 3,4,5], np.uint32)
            black_vao = ctx.vertex_array(black_prog, [
                (ctx.buffer(black_vertices.tobytes()), "2f", "in_position")
            ], ctx.buffer(black_idx.tobytes()))
            black_vao.render()

            # --- save frame ---
            frame = np.flipud(
                np.frombuffer(fbo.read(), np.uint8).reshape((height, width, 3))
            )
            frames.append(frame.copy())

        return frames

    def render_phase2_frames(self, ctx, from_img, to_img, num_frames: int):
        # No second phase for slide fold
        return []

    def __repr__(self):
        return (f"<OrigamiFoldSlide direction={self.direction} "
                f"duration={self.duration}s fps={self.fps} "
                f"min_seam_height={self.min_seam_height}>")


class OrigamiFoldSlideLeft(OrigamiFoldSlide):
    def __init__(self, **kwargs):
        super().__init__(direction="left", **kwargs)


class OrigamiFoldSlideRight(OrigamiFoldSlide):
    def __init__(self, **kwargs):
        super().__init__(direction="right", **kwargs)
