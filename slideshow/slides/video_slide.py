from slideshow.slides.slide_item import SlideItem
from pathlib import Path
import subprocess

class VideoSlide(SlideItem):
    def render(self, output_path: Path, resolution=(640, 360), fps=30):
        print(f"Rendering video slide: {self.path} -> {output_path}")

        # Scaling and padding filter for aspect ratio
        filter_scale = (
            f"scale={resolution[0]}:{resolution[1]}:force_original_aspect_ratio=decrease,"
            f"pad={resolution[0]}:{resolution[1]}:(ow-iw)/2:(oh-ih)/2:black"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(self.path),
            "-vf", filter_scale,
            "-t", str(self.duration),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",   # Ensures compatibility
            "-c:a", "aac",
            "-shortest",              # Prevents FFmpeg from outputting black after video ends
            "-movflags", "+faststart",
            str(output_path)
        ]

        print(f"FFmpeg command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            raise RuntimeError(f"FFmpeg failed: {result.stderr}")
        else:
            print(f"Video slide rendered successfully: {output_path}")
