#!/usr/bin/env python3
"""
OrigamiTransition (SlideItem-based)
----------------------------------
Production entry point for origami-style transitions.
Selects left/right fold randomly (or forced) and delegates rendering
to the correct fold class.
"""

import random
from pathlib import Path
from slideshow.transitions.base_transition import BaseTransition
from slideshow.transitions.left_fold_horizontal import LeftFoldHorizontal
from slideshow.transitions.right_fold_horizontal import RightFoldHorizontal

class OrigamiTransition(BaseTransition):
    def __init__(self, duration=1.0, resolution=(1920, 1080), fps=None, direction=None):
        super().__init__(duration=duration)
        self.name = "Origami"
        self.description = "3D paper folding transition with left/right fold variations"
        self.resolution = resolution
        self.fps = fps
        self.direction = direction

    def get_requirements(self):
        """Return required dependencies for this transition."""
        return ["moderngl", "numpy", "Pillow", "ffmpeg"]

    def _select_transition(self):
        """Randomly choose left or right fold (or respect forced direction)."""
        chosen_dir = self.direction or random.choice(["left", "right"])
        if chosen_dir == "left":
            return LeftFoldHorizontal(duration=self.duration, resolution=self.resolution, fps=self.fps)
        else:
            return RightFoldHorizontal(duration=self.duration, resolution=self.resolution, fps=self.fps)

    def render(self, from_slide, to_slide, output_path: Path):
        """
        Render the Origami transition between two SlideItem instances.
        
        Args:
            from_slide: SlideItem (PhotoSlide or VideoSlide)
            to_slide:   SlideItem (PhotoSlide or VideoSlide)
            output_path: Path where the transition video should be saved
        """
        if not self.is_available():
            raise RuntimeError("OrigamiTransition dependencies not available. "
                               "Install with: pip install moderngl pillow numpy")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use the new SlideItem API to get frame paths
        from_frame = from_slide.get_last_frame()
        to_frame = to_slide.get_first_frame()

        # Select and render the actual fold transition
        transition = self._select_transition()
        transition.render(from_frame, to_frame, output_path)
