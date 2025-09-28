# slideshow/transitions/fade_transition.py
from pathlib import Path
import subprocess
from .base_transition import BaseTransition

class FadeTransition(BaseTransition):
    """Simple crossfade transition using FFmpeg."""

    def __init__(self, duration: float = 1.0):
        super().__init__(duration)
        self.name = "Fade"
        self.description = "Simple crossfade between slides"

    def get_requirements(self) -> list:
        # Only ffmpeg is required
        return ["ffmpeg"]

    def render(self, from_clip: Path, to_clip: Path, output_path: Path):
        self.ensure_output_dir(output_path)

        work_dir = output_path.parent / f"xfade_trans_{output_path.stem}"
        work_dir.mkdir(parents=True, exist_ok=True)

        from_png = work_dir / "from.png"
        to_png   = work_dir / "to.png"

        # Extract last frame of from_clip
        subprocess.run([
            "ffmpeg", "-y",
            "-sseof", "-0.1", "-i", str(from_clip),
            "-vframes", "1", str(from_png)
        ], check=True)

        # Extract first frame of to_clip
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(to_clip),
            "-vframes", "1", str(to_png)
        ], check=True)

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-t", f"{self.duration:.3f}", "-i", str(from_png),
            "-loop", "1", "-t", f"{self.duration:.3f}", "-i", str(to_png),
            "-filter_complex", f"[0:v][1:v]xfade=transition=fade:duration={self.duration}:offset=0",
            "-r", "30",  # or use config fps
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-t", f"{self.duration:.3f}", str(output_path)
        ]
        subprocess.run(cmd, check=True)
