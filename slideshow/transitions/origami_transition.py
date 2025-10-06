# slideshow/transitions/origami_transition.py
#!/usr/bin/env python3
"""
OrigamiTransition (SlideItem-based)
----------------------------------
Production entry point for origami-style transitions.
Selects from multiple origami folds (left, right, up, down)
and delegates rendering to the chosen sub-transition.
"""

import random
from pathlib import Path
from slideshow.transitions.base_transition import BaseTransition
from slideshow.transitions.origami_fold_left_right import OrigamiFoldLeft, OrigamiFoldRight
from slideshow.transitions.origami_fold_up_down import OrigamiFoldUp, OrigamiFoldDown
from slideshow.transitions.origami_fold_center import OrigamiFoldCenterHoriz, OrigamiFoldCenterVert
from slideshow.transitions.origami_fold_slide import OrigamiFoldSlideLeft, OrigamiFoldSlideRight
from slideshow.transitions.origami_fold_multi_lr import OrigamiFoldMultiLRLeft, OrigamiFoldMultiLRRight



class OrigamiTransition(BaseTransition):
    def __init__(self, duration=1.0, resolution=(1920, 1080), fps=30, fold=None, easing="quad", lighting=True):
        """
        Args:
            duration (float): Duration of the transition in seconds.
            resolution (tuple): Output resolution (width, height).
            fps (int): Frames per second for rendering.
            fold (str|None): Force a specific fold direction ("left", "right", "up", "down", 
                             "centerhoriz", "centervert", "slide_left", "slide_right", 
                             "multileft", "multiright", "multislide"). If None, one is chosen randomly.
            easing (str): Easing function for smooth animation ("linear", "quad", "cubic", "back").
                         Default "quad" provides natural acceleration/deceleration.
            lighting (bool): Enable realistic directional lighting for depth and dimension.
                            Default True provides paper-like shading effects.
        """
        super().__init__(duration=duration)
        self.name = "Origami"
        self.description = "3D paper folding transition with multiple variations: basic (left/right/up/down), center (horiz/vert), slide, multi-quarter progressive folds, and multi-slide preview"
        self.resolution = resolution
        self.fps = fps
        self.fold = fold  # optional forced fold direction
        self.easing = easing  # easing function for smooth animation
        self.lighting = lighting  # realistic directional lighting

        # Mapping of fold direction → transition class
        self.fold_map = {
            "left": OrigamiFoldLeft,
            "right": OrigamiFoldRight,
            "up": OrigamiFoldUp,
            "down": OrigamiFoldDown,
            "centerhoriz": OrigamiFoldCenterHoriz,
            "centervert": OrigamiFoldCenterVert,
            "slide_left": OrigamiFoldSlideLeft,
            "slide_right": OrigamiFoldSlideRight,
            "multileft": OrigamiFoldMultiLRLeft,
            "multiright": OrigamiFoldMultiLRRight,
        }

    def get_requirements(self):
        """Return required dependencies for this transition."""
        return ["moderngl", "numpy", "Pillow", "ffmpeg"]

    def _select_transition(self):
        """Pick a fold type based on self.fold or random choice."""
        chosen = self.fold or random.choice(list(self.fold_map.keys()))
        cls = self.fold_map[chosen]
        
        # Pass easing and lighting parameters to multi-LR transitions that support them
        if chosen in ["multileft", "multiright"]:
            return cls(duration=self.duration, resolution=self.resolution, fps=self.fps, 
                      easing=self.easing, lighting=self.lighting)
        else:
            return cls(duration=self.duration, resolution=self.resolution, fps=self.fps)

    def render(self, index: int, slides: list, output_path: Path) -> int:
        """
        Render the Origami transition using slides from the array.

        Args:
            index: Current slide index in the slideshow
            slides: Array of all slides
            output_path: Path where the transition video should be saved
            
        Returns:
            Number of slides consumed by this transition
        """
        if not self.is_available():
            raise RuntimeError(
                "OrigamiTransition dependencies not available. "
                "Install with: pip install moderngl pillow numpy"
            )

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        transition = self._select_transition()
        return transition.render(index, slides, output_path)
