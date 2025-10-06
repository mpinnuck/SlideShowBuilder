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
from slideshow.transitions.ffmpeg_cache import FFmpegCache


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

    def render(self, index: int, slides: list, output_path: Path) -> int:
        """
        Render method using slides from array.
        Converts SlideItem -> frames -> video file.
        Returns number of slides consumed (default 1).
        """
        if index + 1 >= len(slides):
            raise ValueError(f"OrigamiFrameTransition: Not enough slides for transition at index {index}")
            
        from_slide = slides[index]
        to_slide = slides[index + 1]
        
        # Create cache key based on the transition parameters and involved slides
        from_clip = from_slide.get_rendered_clip()
        to_clip = to_slide.get_rendered_clip()
        
        # Use a virtual path combining both slides for cache key
        virtual_path = Path(f"origami_transition_{from_clip.stem}_to_{to_clip.stem}")
        
        cache_params = {
            "operation": "origami_frame_transition",
            "transition_type": self.__class__.__name__,
            "duration": self.duration,
            "fps": self.fps,
            "from_slide": str(from_clip.absolute()),
            "to_slide": str(to_clip.absolute()),
            "from_mtime": from_clip.stat().st_mtime if from_clip.exists() else 0,
            "to_mtime": to_clip.stat().st_mtime if to_clip.exists() else 0,
        }
        
        # Check cache first
        cached_transition = FFmpegCache.get_cached_clip(virtual_path, cache_params)
        if cached_transition:
            # Copy cached transition to output path
            import shutil
            shutil.copy2(cached_transition, output_path)
            return 1
        
        from_img = from_slide.get_from_image()
        to_img = to_slide.get_to_image()

        frames = self.render_frames(from_img, to_img)
        save_frames_as_video(frames, output_path, fps=self.fps)

        # Store result in cache for future use
        FFmpegCache.store_clip(virtual_path, cache_params, output_path)

        return 1  # Most origami transitions consume 1 slide
