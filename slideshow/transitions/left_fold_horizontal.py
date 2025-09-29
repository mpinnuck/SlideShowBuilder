# slideshow/transitions/left_fold_horizontal.py
import moderngl
from slideshow.transitions.left_right_fold import LeftRightFold
from slideshow.transitions.origami_render import render_phase1_frames, render_phase2_frames

class LeftFoldHorizontal(LeftRightFold):
    """Left-to-right origami-style fold transition."""

    def __init__(self, **kwargs):
        super().__init__(direction="left", **kwargs)

    def render_frames(self, from_img, to_img):
        ctx = moderngl.create_context(standalone=True)
        try:
            total_frames = int(self.fps * self.duration)
            phase1_frames = max(1, int(total_frames * 0.55))
            phase2_frames = total_frames - phase1_frames

#            print(f"[LeftFoldHorizontal] Phase 1: {phase1_frames} frames, Phase 2: {phase2_frames} frames")

            # ✅ Use shared Phases renderer with direction="right"
            phase1 = self.render_phase1_frames(ctx, from_img, to_img, num_frames=phase1_frames)
            phase2 = self.render_phase2_frames(ctx, from_img, to_img, num_frames=phase2_frames)
            return phase1 + phase2
        finally:
            ctx.release()
