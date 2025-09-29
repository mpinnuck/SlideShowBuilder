# slideshow/transitions/right_fold_horizontal.py
import moderngl
from slideshow.transitions.left_right_fold import LeftRightFold
from slideshow.transitions.origami_render import render_phase1_frames_right, render_phase2_frames

class RightFoldHorizontal(LeftRightFold):
    """Right-to-left origami-style fold transition."""

    def __init__(self, **kwargs):
        super().__init__(direction="right", **kwargs)

    def render_frames(self, from_img, to_img):
        ctx = moderngl.create_context(standalone=True)
        try:
            total_frames = int(self.fps * self.duration)
            phase1_frames = max(1, int(total_frames * 0.55))
            phase2_frames = total_frames - phase1_frames

#            print(f"[RightFoldHorizontal] Phase 1: {phase1_frames} frames, Phase 2: {phase2_frames} frames")

            phase1 = render_phase1_frames_right(ctx, from_img, to_img, num_frames=phase1_frames)
            # ✅ Use shared Phase 2 renderer with direction="left"
            phase2 = render_phase2_frames(ctx, to_img, from_img, num_frames=phase2_frames, direction="left")
            return phase1 + phase2
        finally:
            ctx.release()
