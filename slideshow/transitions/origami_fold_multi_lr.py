# slideshow/transitions/origami_fold_multi_lr.py

import numpy as np
import moderngl
from slideshow.transitions.origami_frame_transition import OrigamiFrameTransition
from slideshow.transitions.origami_render import draw_fullscreen_image, render_flap_fold


class OrigamiFoldMultiLR(OrigamiFrameTransition):
    """
    Base class for multi-quarter origami fold transitions.
    Subclasses implement direction-specific folding logic.
    """
    def __init__(self, easing="quad", lighting=True, **kwargs):
        super().__init__(**kwargs)
        self.easing = easing  # Easing function: "linear", "quad", "cubic", "back"
        self.lighting = lighting  # Enable realistic directional lighting for depth
        
        # Multi-fold transitions need more time to be visible - use minimum 2.5 seconds
        self.effective_duration = max(self.duration, 2.5)
        if self.effective_duration > self.duration:
            print(f"Note: Multi-fold transition extended from {self.duration}s to {self.effective_duration}s for better visibility")

    def get_requirements(self):
        return ["moderngl", "numpy", "Pillow", "ffmpeg"]

    def render_phase1_frames(self, ctx, from_img, to_img, num_frames: int):
        """Base implementation - subclasses should override this."""
        raise NotImplementedError("Subclasses must implement render_phase1_frames")

    def render_phase2_frames(self, ctx, from_img, to_img, num_frames: int):
        return []

    def __repr__(self):
        return f"<{self.__class__.__name__} duration={self.duration}s fps={self.fps}>"


class OrigamiFoldMultiLRLeft(OrigamiFoldMultiLR):
    """Multi-LR fold transitioning LEFT: Q4→Q3→Q2→Q1 (right to left)."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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

        # Calculate frames using effective duration for better timing
        effective_frames = int(self.effective_duration * self.fps)
        
        # Distribute frames with more time for each fold (minimum 15 frames per fold)
        min_frames_per_fold = 15  # 0.5 seconds at 30fps
        per_fold_frames = max(min_frames_per_fold, effective_frames // 4)
        
        # Add a small pause between folds for better visual separation
        pause_frames = max(1, effective_frames // 20)  # Small pause between folds
        
        print(f"Multi-fold timing: {per_fold_frames} frames per fold, {pause_frames} pause frames")
        
        previous_frame = frame0  # Start with the FROM image

        # LEFT direction: Fold 1: Q4 → Q3
        fold1_frames = render_flap_fold(ctx, from_tex, to_tex,
                                   width, height,
                                   0.5, 1.0, 0.75, 1.0, seam_x=0.5,
                                   num_frames=per_fold_frames,
                                   previous_frame=previous_frame,
                                   easing=self.easing,
                                   lighting=self.lighting)
        frames += fold1_frames
        previous_frame = fold1_frames[-1] if fold1_frames else previous_frame
        
        # Brief pause for visual separation
        for _ in range(pause_frames):
            frames.append(previous_frame.copy())

        # Fold 2: Q3 → Q2
        fold2_frames = render_flap_fold(ctx, from_tex, to_tex,
                                   width, height,
                                   0.0, 0.5, 0.5, 0.75, seam_x=0.0,
                                   num_frames=per_fold_frames,
                                   previous_frame=previous_frame,
                                   easing=self.easing,
                                   lighting=self.lighting)
        frames += fold2_frames
        previous_frame = fold2_frames[-1] if fold2_frames else previous_frame
        
        # Brief pause for visual separation
        for _ in range(pause_frames):
            frames.append(previous_frame.copy())

        # Fold 3: Q2 → Q1
        fold3_frames = render_flap_fold(ctx, from_tex, to_tex,
                                   width, height,
                                   -0.5, 0.0, 0.25, 0.5, seam_x=-0.5,
                                   num_frames=per_fold_frames,
                                   previous_frame=previous_frame,
                                   easing=self.easing,
                                   lighting=self.lighting)
        frames += fold3_frames
        previous_frame = fold3_frames[-1] if fold3_frames else previous_frame
        
        # Brief pause for visual separation
        for _ in range(pause_frames):
            frames.append(previous_frame.copy())

        # Fold 4: Q1 book fold 0→90 at left edge
        fold4_frames = render_flap_fold(ctx, from_tex, to_tex,
                                   width, height,
                                   -1.0, -0.5, 0.0, 0.25, seam_x=-1.0,
                                   num_frames=per_fold_frames,
                                   start_angle=0.0, end_angle=np.pi/2,
                                   previous_frame=previous_frame,
                                   easing=self.easing,
                                   lighting=self.lighting)
        frames += fold4_frames

        return frames


class OrigamiFoldMultiLRRight(OrigamiFoldMultiLR):
    """Multi-LR fold transitioning RIGHT: Q1→Q2→Q3→Q4 (left to right)."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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

        # Calculate frames using effective duration for better timing
        effective_frames = int(self.effective_duration * self.fps)
        
        # Distribute frames with more time for each fold (minimum 15 frames per fold)
        min_frames_per_fold = 15  # 0.5 seconds at 30fps
        per_fold_frames = max(min_frames_per_fold, effective_frames // 4)
        
        # Add a small pause between folds for better visual separation
        pause_frames = max(1, effective_frames // 20)  # Small pause between folds
        
        print(f"Multi-fold timing: {per_fold_frames} frames per fold, {pause_frames} pause frames")
        
        previous_frame = frame0  # Start with the FROM image

        # RIGHT direction: Fold 1: Q1 → Q2 (leftmost quarter folds right over Q2)
        fold1_frames = render_flap_fold(ctx, from_tex, to_tex,
                                   width, height,
                                   -1.0, -0.5, 0.0, 0.25, seam_x=-0.5,
                                   num_frames=per_fold_frames,
                                   previous_frame=previous_frame,
                                   easing=self.easing,
                                   lighting=self.lighting)
        frames += fold1_frames
        previous_frame = fold1_frames[-1] if fold1_frames else previous_frame
        
        # Brief pause for visual separation
        for _ in range(pause_frames):
            frames.append(previous_frame.copy())

        # Fold 2: Q2 → Q3
        fold2_frames = render_flap_fold(ctx, from_tex, to_tex,
                                   width, height,
                                   -0.5, 0.0, 0.25, 0.5, seam_x=0.0,
                                   num_frames=per_fold_frames,
                                   previous_frame=previous_frame,
                                   easing=self.easing,
                                   lighting=self.lighting)
        frames += fold2_frames
        previous_frame = fold2_frames[-1] if fold2_frames else previous_frame
        
        # Brief pause for visual separation
        for _ in range(pause_frames):
            frames.append(previous_frame.copy())

        # Fold 3: Q3 → Q4
        fold3_frames = render_flap_fold(ctx, from_tex, to_tex,
                                   width, height,
                                   0.0, 0.5, 0.5, 0.75, seam_x=0.5,
                                   num_frames=per_fold_frames,
                                   previous_frame=previous_frame,
                                   easing=self.easing,
                                   lighting=self.lighting)
        frames += fold3_frames
        previous_frame = fold3_frames[-1] if fold3_frames else previous_frame
        
        # Brief pause for visual separation
        for _ in range(pause_frames):
            frames.append(previous_frame.copy())

        # Fold 4: Q4 book fold 0→90 at right edge
        fold4_frames = render_flap_fold(ctx, from_tex, to_tex,
                                   width, height,
                                   0.5, 1.0, 0.75, 1.0, seam_x=1.0,
                                   num_frames=per_fold_frames,
                                   start_angle=0.0, end_angle=np.pi/2,
                                   previous_frame=previous_frame,
                                   easing=self.easing,
                                   lighting=self.lighting)
        frames += fold4_frames

        return frames