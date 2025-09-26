
from pathlib import Path
import subprocess
from slideshow.config import DEFAULT_CONFIG

class VideoSlide:
    def __init__(self, path: Path, duration: float, fps: int = None, resolution: tuple = None):
        self.path = path
        self.duration = duration
        self.fps = fps if fps is not None else DEFAULT_CONFIG["fps"]
        self.resolution = resolution if resolution is not None else tuple(DEFAULT_CONFIG["resolution"])

    def render(self, output_path: Path, log_callback=None, progress_callback=None):
        import subprocess

        if log_callback:
            log_callback(f"[Slideshow] Rendering video slide: {self.path.name} "
                         f"(target={self.duration:.2f}s, output={output_path})")

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", str(self.path),
            "-vf", f"fps={self.fps},scale={self.resolution[0]}:{self.resolution[1]}:force_original_aspect_ratio=decrease,"
                   f"pad={self.resolution[0]}:{self.resolution[1]}:(ow-iw)/2:(oh-ih)/2:black",
            "-t", f"{self.duration:.2f}",
            "-r", str(self.fps),  # Force constant frame rate
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest",
            "-movflags", "+faststart",
            str(output_path)
        ]

        if log_callback:
            log_callback(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")

        process = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg failed for {self.path}:\n{process.stderr}")

        if log_callback:
            log_callback(f"Video slide rendered successfully: {output_path}")
