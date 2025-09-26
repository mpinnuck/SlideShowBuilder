from pathlib import Path
import subprocess
from .base_transition import BaseTransition

class FadeTransition(BaseTransition):
    """Simple crossfade transition using FFmpeg"""
    
    def __init__(self, duration=1.0):
        super().__init__(duration)
        self.name = "Fade"
        self.description = "Simple crossfade between slides"

    def get_requirements(self) -> list:
        """FFmpeg-based transition only requires ffmpeg"""
        return ["ffmpeg"]

    def render(self, from_path: Path, to_path: Path, output_path: Path):
        """
        Render a crossfade transition between two video files
        
        Args:
            from_path: Path to the source video file
            to_path: Path to the destination video file
            output_path: Path where the transition video should be saved
        """
        # Validate inputs
        self.validate_inputs(from_path, to_path, output_path)

        # If duration is -1 or 0, use the full duration of the first video
        transition_duration = self.duration
        if self.duration in (-1, 0):
            # Get duration of the first video using ffprobe
            import json
            result = subprocess.run([
                "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(from_path)
            ], capture_output=True, text=True)
            try:
                info = json.loads(result.stdout)
                transition_duration = float(info["format"]["duration"])
            except Exception:
                transition_duration = 1.0  # fallback

        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(from_path), "-i", str(to_path),
            "-filter_complex",
            f"[0:v][1:v]xfade=transition=fade:duration={transition_duration}:offset=0",
            "-t", str(transition_duration),  # Only output the transition duration
            "-preset", "fast", 
            "-c:v", "libx264", 
            "-c:a", "aac",
            str(output_path)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
