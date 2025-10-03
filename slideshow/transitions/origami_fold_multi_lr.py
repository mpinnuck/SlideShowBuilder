# slideshow/transitions/origami_fold_multi_lr.py

import numpy as np
import moderngl
from slideshow.transitions.origami_frame_transition import OrigamiFrameTransition


def draw_fullscreen_image(ctx, tex):
    """Draws a full-frame texture to the current framebuffer."""
    prog = ctx.program(
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

    v = np.array([-1,-1,0,  1,-1,0,  1,1,0, -1,1,0], np.float32)
    uv = np.array([0,1,  1,1,  1,0,  0,0], np.float32)
    idx = np.array([0,1,2, 0,2,3], np.uint32)

    vao = ctx.vertex_array(prog, [
        (ctx.buffer(v.tobytes()), '3f', 'in_position'),
        (ctx.buffer(uv.tobytes()), '2f', 'in_texcoord')
    ], ctx.buffer(idx.tobytes()))

    tex.use(0)
    prog['tex'] = 0
    vao.render()


def render_flap_fold(ctx, from_tex, to_tex, width, height,
                     x_min, x_max, u_min, u_max, seam_x,
                     num_frames, start_angle=0.0, end_angle=np.pi, 
                     previous_frame=None):
    """
    Render one flap folding (e.g. Q4→Q3), revealing TO behind the flap only.
    previous_frame: the result of the previous fold to use as background
    """
    frames = []

    # Create offscreen framebuffer
    flap_tex = ctx.texture((width, height), 3)
    fbo = ctx.framebuffer(color_attachments=[flap_tex])

    # Prepare flap mesh
    flap_v = np.array([
        x_min, -1, 0,
        x_max, -1, 0,
        x_max,  1, 0,
        x_min,  1, 0
    ], np.float32)
    flap_uv = np.array([
        u_min, 1.0,
        u_max, 1.0,
        u_max, 0.0,
        u_min, 0.0
    ], np.float32)
    flap_idx = np.array([0,1,2,0,2,3], np.uint32)

    flap_prog = ctx.program(
        vertex_shader="""
        #version 330
        in vec3 in_position;
        in vec2 in_texcoord;
        out vec2 uv;
        uniform float angle;
        uniform float seam_x;
        void main() {
            uv = in_texcoord;
            vec3 pos = in_position;
            float ox = pos.x - seam_x;
            float oz = pos.z;
            pos.x = seam_x + ox * cos(angle) - oz * sin(angle);
            pos.z = ox * sin(angle) + oz * cos(angle);
            gl_Position = vec4(pos.x, pos.y, -pos.z * 0.1, 1.0);
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

    flap_vao = ctx.vertex_array(flap_prog, [
        (ctx.buffer(flap_v.tobytes()), "3f", "in_position"),
        (ctx.buffer(flap_uv.tobytes()), "2f", "in_texcoord")
    ], ctx.buffer(flap_idx.tobytes()))

    ctx.disable(moderngl.CULL_FACE)

    # Use previous frame as background, or FROM image for first fold
    if previous_frame is not None:
        background_tex = ctx.texture((width, height), 3, previous_frame.tobytes())
    else:
        background_tex = from_tex

    for j in range(num_frames):
        t = j / (num_frames - 1)
        angle = start_angle + t * (end_angle - start_angle)

        fbo.use()
        ctx.clear(0, 0, 0, 1)

        # 1️⃣ Draw background (previous fold result or FROM image)
        background_tex.use(0)
        draw_fullscreen_image(ctx, background_tex)

        # 2️⃣ Only reveal TO image in the specific area being folded over
        # Create a quad for just the area being revealed
        reveal_v = np.array([
            x_min, -1, 0,
            x_max, -1, 0, 
            x_max,  1, 0,
            x_min,  1, 0
        ], np.float32)
        reveal_uv = np.array([
            u_min, 1.0,
            u_max, 1.0,
            u_max, 0.0,
            u_min, 0.0
        ], np.float32)
        reveal_idx = np.array([0,1,2,0,2,3], np.uint32)

        # Simple program for revealing TO image
        reveal_prog = ctx.program(
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

        reveal_vao = ctx.vertex_array(reveal_prog, [
            (ctx.buffer(reveal_v.tobytes()), "3f", "in_position"),
            (ctx.buffer(reveal_uv.tobytes()), "2f", "in_texcoord")
        ], ctx.buffer(reveal_idx.tobytes()))

        # Reveal TO image only in the area being folded over (gradually)
        reveal_progress = min(1.0, angle / (np.pi/2))  # 0 to 1 as angle goes 0 to 90°
        if reveal_progress > 0:
            to_tex.use(0)
            reveal_prog['tex'] = 0
            reveal_vao.render()

        # 3️⃣ Draw FROM flap rotating
        from_tex.use(0)
        flap_prog['tex'] = 0
        flap_prog['angle'] = angle
        flap_prog['seam_x'] = seam_x
        flap_vao.render()

        frame = np.flipud(
            np.frombuffer(fbo.read(), np.uint8).reshape((height, width, 3))
        )
        frames.append(frame.copy())

    return frames


class OrigamiFoldMultiLR(OrigamiFrameTransition):
    """
    Multi-quarter origami fold (left-right).
    Folds Q4→Q3, Q3→Q2, Q2→Q1, then Q1 off-screen 0→90°.
    """
    def __init__(self, direction="left", **kwargs):
        super().__init__(**kwargs)
        self.direction = direction.lower()

    def get_requirements(self):
        return ["moderngl", "numpy", "Pillow", "ffmpeg"]

    def render_phase1_frames(self, ctx, from_img, to_img, num_frames: int):
        width, height = from_img.size
        frames = []

        from_tex = ctx.texture(from_img.size, 3, np.array(from_img.convert("RGB")).tobytes())
        to_tex = ctx.texture(to_img.size, 3, np.array(to_img.convert("RGB")).tobytes())

        # ✅ Frame 0: full FROM image
        fbo0 = ctx.framebuffer(color_attachments=[ctx.texture((width, height), 3)])
        fbo0.use()
        ctx.clear(0, 0, 0, 1)
        draw_fullscreen_image(ctx, from_tex)
        frame0 = np.flipud(
            np.frombuffer(fbo0.read(), np.uint8).reshape((height, width, 3))
        )
        frames.append(frame0.copy())

        per_fold_frames = num_frames // 4
        previous_frame = frame0  # Start with the FROM image

        if self.direction == "left":
            # Fold 1: Q4 → Q3
            fold1_frames = render_flap_fold(ctx, from_tex, to_tex,
                                       width, height,
                                       0.5, 1.0, 0.75, 1.0, seam_x=0.5,
                                       num_frames=per_fold_frames,
                                       previous_frame=previous_frame)
            frames += fold1_frames
            previous_frame = fold1_frames[-1] if fold1_frames else previous_frame

            # Fold 2: Q3 → Q2
            fold2_frames = render_flap_fold(ctx, from_tex, to_tex,
                                       width, height,
                                       0.0, 0.5, 0.5, 0.75, seam_x=0.0,
                                       num_frames=per_fold_frames,
                                       previous_frame=previous_frame)
            frames += fold2_frames
            previous_frame = fold2_frames[-1] if fold2_frames else previous_frame

            # Fold 3: Q2 → Q1
            fold3_frames = render_flap_fold(ctx, from_tex, to_tex,
                                       width, height,
                                       -0.5, 0.0, 0.25, 0.5, seam_x=-0.5,
                                       num_frames=per_fold_frames,
                                       previous_frame=previous_frame)
            frames += fold3_frames
            previous_frame = fold3_frames[-1] if fold3_frames else previous_frame

            # Fold 4: Q1 book fold 0→90 at left edge
            fold4_frames = render_flap_fold(ctx, from_tex, to_tex,
                                       width, height,
                                       -1.0, -0.5, 0.0, 0.25, seam_x=-1.0,
                                       num_frames=per_fold_frames,
                                       start_angle=0.0, end_angle=np.pi/2,
                                       previous_frame=previous_frame)
            frames += fold4_frames

        return frames

    def render_phase2_frames(self, ctx, from_img, to_img, num_frames: int):
        return []

    def __repr__(self):
        return f"<OrigamiFoldMultiLR direction={self.direction} duration={self.duration}s fps={self.fps}>"


class OrigamiFoldMultiLRLeft(OrigamiFoldMultiLR):
    def __init__(self, **kwargs):
        super().__init__(direction="left", **kwargs)


class OrigamiFoldMultiLRRight(OrigamiFoldMultiLR):
    def __init__(self, **kwargs):
        super().__init__(direction="right", **kwargs)