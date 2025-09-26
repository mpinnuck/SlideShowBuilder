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
        self.fps = fps if fps is not None else self._determine_fps_from_region()
        self.direction = direction

    def _determine_fps_from_region(self):
        """
        Determine fps based on regional video standards.
        PAL regions: Europe, Australia, parts of Asia/Africa - 25 fps
        NTSC regions: North America, Japan, parts of South America - 30 fps
        
        Checks multiple sources for region information:
        1. macOS system region settings
        2. Timezone information  
        3. Locale settings (as fallback)
        
        Defaults to 25 fps (PAL) as it's used by most countries worldwide.
        """
        import locale
        import os
        import subprocess
        import platform
        
        try:
            region_indicators = []
            
            # Check macOS system region first (most reliable for your case)
            if platform.system() == "Darwin":  # macOS
                try:
                    # Get the system region/country setting
                    result = subprocess.run(
                        ["defaults", "read", "-g", "AppleLocale"], 
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        apple_locale = result.stdout.strip()
                        region_indicators.append(f"AppleLocale:{apple_locale}")
                        
                    # Also try AppleLanguages
                    result2 = subprocess.run(
                        ["defaults", "read", "-g", "AppleLanguages"], 
                        capture_output=True, text=True, timeout=5
                    )
                    if result2.returncode == 0 and result2.stdout.strip():
                        apple_langs = result2.stdout.strip()
                        if "AU" in apple_langs or "Australia" in apple_langs:
                            region_indicators.append(f"AppleLanguages:AU_detected")
                            
                except Exception as e:
                    pass
            
            # Check timezone 
            tz_var = os.environ.get('TZ', '')
            if tz_var:
                region_indicators.append(f"TZ:{tz_var}")
            
            # Check locale variables
            lang_var = os.environ.get('LANG', '')
            if lang_var:
                region_indicators.append(f"LANG:{lang_var}")
                
            lc_all = os.environ.get('LC_ALL', '')
            if lc_all:
                region_indicators.append(f"LC_ALL:{lc_all}")
            
            # Debug print removed
            
            # Check for PAL regions first (including Australia)
            pal_indicators = [
                "AU", "Australia", "_AU", "en_AU", 
                "GB", "UK", "_GB", "en_GB",
                "DE", "_DE", "FR", "_FR", "NL", "_NL", "NZ", "_NZ",
                "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide",
                "Australia/", "Pacific/Auckland", "Europe/"
            ]
            
            for indicator in region_indicators:
                for pal_pattern in pal_indicators:
                    if pal_pattern in indicator:
                        return 25
            
            # Check for specific NTSC regions
            ntsc_indicators = [
                "America/", "US/", "_US.", "en_CA", "fr_CA", "es_MX",
                "ja_JP", "ko_KR", "Asia/Tokyo", "Asia/Seoul"
            ]
            
            for indicator in region_indicators:
                for ntsc_pattern in ntsc_indicators:
                    if ntsc_pattern in indicator:
                        return 30
            
            # Default to PAL (25 fps) - used by most of the world
            # No specific region indicators found, default to PAL
            return 25
                
        except Exception as e:
            return 25

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
            return LeftFoldHorizontal(duration=self.duration, resolution=self.resolution, fps=self.fps)
        else:
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
    # Debug print removed
