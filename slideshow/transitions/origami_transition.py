# slideshow/transitions/origami_transition.py
#!/usr/bin/env python3
"""
OrigamiTransition (SlideItem-based)
----------------------------------
Production entry point for origami-style transitions.
Selects from multiple origami folds (left, right, up, down)
and delegates rendering to the chosen sub-transition.
"""

import hashlib
from pathlib import Path
from slideshow.transitions.base_transition import BaseTransition
from slideshow.transitions.ffmpeg_cache import FFmpegCache
from slideshow.transitions.origami_fold_left_right import OrigamiFoldLeft, OrigamiFoldRight
from slideshow.transitions.origami_fold_up_down import OrigamiFoldUp, OrigamiFoldDown
from slideshow.transitions.origami_fold_center import OrigamiFoldCenterHoriz, OrigamiFoldCenterVert
from slideshow.transitions.origami_fold_slide import OrigamiFoldSlideLeft, OrigamiFoldSlideRight
from slideshow.transitions.origami_fold_multi_lr import OrigamiFoldMultiLRLeft, OrigamiFoldMultiLRRight



class OrigamiTransition(BaseTransition):
    def __init__(self, duration=1.0, resolution=(1920, 1080), fps=30, fold=None, easing="quad", lighting=True, project_name=None):
        """
        Args:
            duration (float): Duration of the transition in seconds.
            resolution (tuple): Output resolution (width, height).
            fps (int): Frames per second for rendering.
            fold (str|None): Force a specific fold direction ("left", "right", "up", "down", 
                             "centerhoriz", "centervert", "slide_left", "slide_right", 
                             "multileft", "multiright", "multislide"). If None, one is chosen deterministically.
            easing (str): Easing function for smooth animation ("linear", "quad", "cubic", "back").
                         Default "quad" provides natural acceleration/deceleration.
            lighting (bool): Enable realistic directional lighting for depth and dimension.
                            Default True provides paper-like shading effects.
            project_name (str): Project name to include in deterministic transition selection.
        """
        super().__init__(duration=duration)
        self.name = "Origami"
        self.description = "3D paper folding transition with multiple variations: basic (left/right/up/down), center (horiz/vert), slide, multi-quarter progressive folds, and multi-slide preview"
        self.resolution = resolution
        self.fps = fps
        self.fold = fold  # optional forced fold direction
        self.easing = easing  # easing function for smooth animation
        self.lighting = lighting  # realistic directional lighting
        self.project_name = project_name  # for deterministic transition selection

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

    def _select_transition(self, slide1_path=None, slide2_path=None, project_name=None):
        """Pick a fold type based on self.fold or deterministic choice based on slide pair and project."""
        if self.fold:
            chosen = self.fold
        else:
            # Create deterministic selection based on slide paths AND project name
            if slide1_path and slide2_path:
                # Include project name in hash for different transition sets per project
                slide_pair = f"{project_name or 'default'}|{slide1_path}|{slide2_path}"
                hash_value = int(hashlib.md5(slide_pair.encode()).hexdigest()[:8], 16)
                fold_types = list(self.fold_map.keys())
                chosen = fold_types[hash_value % len(fold_types)]
            else:
                # Fallback to first option if no slide info available
                chosen = list(self.fold_map.keys())[0]
        
        cls = self.fold_map[chosen]
        
        # Pass easing and lighting parameters to multi-LR transitions that support them
        if chosen in ["multileft", "multiright"]:
            return cls(duration=self.duration, resolution=self.resolution, fps=self.fps, 
                      easing=self.easing, lighting=self.lighting)
        else:
            return cls(duration=self.duration, resolution=self.resolution, fps=self.fps)

    def _get_cache_params(self, slide1_path: str, slide2_path: str) -> dict:
        """Generate cache parameters for the complete transition."""
        return {
            'operation': 'origami_transition_render',
            'slide1_path': slide1_path,
            'slide2_path': slide2_path,
            'project_name': self.project_name or 'default',
            'duration': self.duration,
            'resolution': self.resolution,
            'fps': self.fps,
            'easing': self.easing,
            'lighting': self.lighting,
            'fold': self.fold or 'auto'  # Include the selected fold type
        }

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

        # Extract slide paths for deterministic transition selection
        slide1_path = None
        slide2_path = None
        
        if index < len(slides):
            slide1 = slides[index]
            slide1_path = str(slide1.input_path) if hasattr(slide1, 'input_path') else str(slide1)
            
        if index + 1 < len(slides):
            slide2 = slides[index + 1]
            slide2_path = str(slide2.input_path) if hasattr(slide2, 'input_path') else str(slide2)

        # Check cache for complete transition
        if slide1_path and slide2_path:
            # Get cache parameters for the complete transition
            cache_params = self._get_cache_params(slide1_path, slide2_path)
            
            # Try to get cached transition
            virtual_input_path = Path(f"{slide1_path}_to_{slide2_path}")
            cached_clip = FFmpegCache.get_cached_clip(virtual_input_path, cache_params)
            
            if cached_clip and cached_clip.exists():
                # Copy cached result to output location
                import shutil
                shutil.copy2(cached_clip, output_path)
                return 1  # Consumed one slide pair
        
        # Cache miss - render the transition
        transition = self._select_transition(slide1_path, slide2_path, self.project_name)
        result = transition.render(index, slides, output_path)
        
        # Store the rendered transition in cache
        if slide1_path and slide2_path and output_path.exists():
            virtual_input_path = Path(f"{slide1_path}_to_{slide2_path}")
            cache_params = self._get_cache_params(slide1_path, slide2_path)
            FFmpegCache.store_clip(virtual_input_path, cache_params, output_path)
        
        return result
