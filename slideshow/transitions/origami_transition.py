#!/usr/bin/env python3
"""
OrigamiTransition (BaseTransition-compliant)
--------------------------------------------
Production entry point for origami-style transitions.
Selects left/right fold randomly (or forced) and delegates rendering
to the correct fold class.
"""

import random
import locale
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
        self.fps = fps or self._determine_fps_from_locale()
        self.direction = direction

    def _determine_fps_from_locale(self):
        loc = locale.getdefaultlocale()
        loc_str = loc[0] if loc and loc[0] else ""
        if any(region in loc_str for region in ["AU", "GB", "DE", "FR", "NL", "NZ", "EU"]):
            print(f"[OrigamiTransition] Locale {loc_str} → using 25 fps (PAL)")
            return 25
        print(f"[OrigamiTransition] Locale {loc_str} → using 30 fps (NTSC)")
        return 30

    def get_requirements(self):
        """Return required dependencies for this transition."""
        return ["moderngl", "numpy", "Pillow", "ffmpeg"]

    def is_available(self):
        """Return True if all requirements are available."""
        try:
            __import__("moderngl")
            __import__("numpy")
            __import__("PIL")
            return True
        except ImportError:
            return False

    def _select_transition(self):
        chosen_dir = self.direction or random.choice(["left", "right"])
        if chosen_dir == "left":
            print("[OrigamiTransition] Using LEFT fold")
            return LeftFoldHorizontal(duration=self.duration, resolution=self.resolution, fps=self.fps)
        else:
            print("[OrigamiTransition] Using RIGHT fold")
            return RightFoldHorizontal(duration=self.duration, resolution=self.resolution, fps=self.fps)

    def render(self, from_path, to_path, output_path):
        # Validate inputs using BaseTransition helper
        self.validate_inputs(from_path, to_path, output_path)

        if not self.is_available():
            raise RuntimeError("OrigamiTransition dependencies not available. "
                             "Install with: pip install moderngl pillow numpy")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        transition = self._select_transition()
        transition.render(from_path, to_path, output_path)
        print(f"[OrigamiTransition] Transition video saved → {output_path}")
