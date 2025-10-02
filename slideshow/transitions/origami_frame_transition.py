# slideshow/transitions/origami_frame_transition.py
"""
Note: This base class is only for two-phase origami folds (start fold + finish fold).
If your transition doesn’t fit this structure (e.g. center folds with wobble),
subclass BaseTransition directly instead.
"""
import moderngl
from abc import ABC, abstractmethod
from pathlib import Path
from slideshow.transitions.base_transition import BaseTransition
from slideshow.transitions.utils import save_frames_as_video


class OrigamiFrameTransition(BaseTransition, ABC):
    """
    Abstract base for origami-style transitions (folds, flips, etc).
    Subclasses must implement phase1 and phase2 rendering.
    """

    def __init__(self, duration=1.0, resolution=(1920, 1080), fps=25):
        super().__init__(duration)
        self.resolution = resolution
        self.fps = fps

    @abstractmethod
    def render_phase1_frames(self, ctx, from_img, to_img, num_frames: int):
        """Subclasses implement phase 1 folding effect."""
        pass

    @abstractmethod
    def render_phase2_frames(self, ctx, from_img, to_img, num_frames: int):
        """Subclasses implement phase 2 unfolding effect."""
        pass

    def render_frames(self, from_img, to_img):
        """
        Shared rendering logic for origami folds:
        - Phase 1: start fold
        - Phase 2: finish fold
        """
        ctx = moderngl.create_context(standalone=True)
        try:
            total_frames = int(self.fps * self.duration)
            phase1_frames = max(1, int(total_frames * 0.55))
            phase2_frames = total_frames - phase1_frames

            phase1 = self.render_phase1_frames(ctx, from_img, to_img, num_frames=phase1_frames)
            phase2 = self.render_phase2_frames(ctx, from_img, to_img, num_frames=phase2_frames)

            return phase1 + phase2
        finally:
            ctx.release()

    def render(self, from_slide, to_slide, output_path: Path):
        """
        Public render API used by Slideshow.
        Converts SlideItem -> frames -> video file.
        """
        from_img = from_slide.get_from_image()
        to_img = to_slide.get_to_image()

        frames = self.render_frames(from_img, to_img)
        save_frames_as_video(frames, output_path, fps=self.fps)

        return output_path
