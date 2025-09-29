# slideshow/transitions/fade_transition.py
from pathlib import Path
import subprocess
from .base_transition import BaseTransition
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

    def render(self, from_slide, to_slide, output_path: Path):
        """Render a crossfade transition between two rendered slide clips."""
        self.ensure_output_dir(output_path)

        from_png = output_path.parent / "from.png"
        to_png = output_path.parent / "to.png"

        # Save the opening and closing frames to disk
        from_frame = from_slide.get_from_image()  # last frame of from_slide
        to_frame = to_slide.get_to_image()       # first frame of to_slide
        from_frame.save(from_png)
        to_frame.save(to_png)

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-t", f"{self.duration:.3f}", "-i", str(from_png),
            "-loop", "1", "-t", f"{self.duration:.3f}", "-i", str(to_png),
            "-filter_complex",
            f"[0:v][1:v]xfade=transition=fade:duration={self.duration}:offset=0",
            "-r", "30",  # could use from_slide.fps if slides share same fps
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-t", f"{self.duration:.3f}", str(output_path)
        ]

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"FadeTransition failed:\nCommand: {' '.join(cmd)}\nError:\n{result.stderr}"
            )

        return output_path