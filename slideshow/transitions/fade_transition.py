# slideshow/transitions/fade_transition.py
from pathlib import Path
import subprocess
from slideshow.config import cfg
from .base_transition import BaseTransition
from .ffmpeg_paths import FFmpegPaths
from .ffmpeg_cache import FFmpegCache
# (Optional) only for type hints:
# from slideshow.slides.slide_item import SlideItem

class FadeTransition(BaseTransition):
    """Simple crossfade transition using FFmpeg."""

    def __init__(self, duration: float = 1.0):
        super().__init__(duration)
        self.name = "Fade"
        self.description = "Simple crossfade between slides"

    def get_requirements(self) -> list:
        return ["ffmpeg"]

    def render(self, index: int, slides: list, output_path: Path) -> int:
        """Render a crossfade transition between two slides from the slides array."""
        if index + 1 >= len(slides):
            raise ValueError(f"FadeTransition: Not enough slides for transition at index {index}")
            
        from_slide = slides[index]
        to_slide = slides[index + 1]
        
        # Create cache key based on the transition parameters and involved slides
        from_clip = from_slide.get_rendered_clip()
        to_clip = to_slide.get_rendered_clip()
        
        # Use a virtual path combining both slides for cache key
        virtual_path = Path(f"transition_{from_clip.stem}_to_{to_clip.stem}")
        
        cache_params = {
            "operation": "fade_transition",
            "duration": self.duration,
            "from_slide": str(from_clip.absolute()),
            "to_slide": str(to_clip.absolute()),
            "from_mtime": from_clip.stat().st_mtime if from_clip.exists() else 0,
            "to_mtime": to_clip.stat().st_mtime if to_clip.exists() else 0,
            "fps": 30,  # Fixed for transitions
            "video_quality": cfg.get('video_quality', 'maximum')  # Include quality in cache key
        }
        
        # Check cache first
        cached_transition = FFmpegCache.get_cached_clip(virtual_path, cache_params)
        if cached_transition:
            # Copy cached transition to output path
            import shutil
            shutil.copy2(cached_transition, output_path)
            return 1
        
        self.ensure_output_dir(output_path)

        from_png = output_path.parent / "from.png"
        to_png = output_path.parent / "to.png"

        # Save the opening and closing frames to disk
        from_frame = from_slide.get_from_image()  # last frame of from_slide
        to_frame = to_slide.get_to_image()       # first frame of to_slide
        from_frame.save(from_png)
        to_frame.save(to_png)

        cmd = [
            FFmpegPaths.ffmpeg(), "-y",
            "-loop", "1", "-t", f"{self.duration:.3f}", "-i", str(from_png),
            "-loop", "1", "-t", f"{self.duration:.3f}", "-i", str(to_png),
            "-filter_complex",
            f"[0:v][1:v]xfade=transition=fade:duration={self.duration}:offset=0",
            "-r", "30",  # could use from_slide.fps if slides share same fps
        ]
        cmd.extend(cfg.get_ffmpeg_encoding_params())  # Use project quality settings
        cmd.extend([
            "-pix_fmt", "yuv420p", 
            "-movflags", "+faststart",
            "-t", f"{self.duration:.3f}", str(output_path)
        ])

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FadeTransition failed:\\nCommand: {' '.join(cmd)}\\nError:\\n{result.stderr}"
            )

        # Store result in cache for future use
        FFmpegCache.store_clip(virtual_path, cache_params, output_path)

        # Fade transition always consumes exactly 1 slide
        return 1