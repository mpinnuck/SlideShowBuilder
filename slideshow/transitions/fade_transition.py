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
        
        # Get duration of first video to calculate proper offset
        # The transition should start at (first_video_duration - transition_duration)
        # so that it crossfades at the end of the first video
        
        subprocess.run([
            "ffmpeg", "-y",
            "-i", str(from_path), "-i", str(to_path),
            "-filter_complex",
            f"[0:v][1:v]xfade=transition=fade:duration={self.duration}:offset=0",
            "-t", str(self.duration),  # Only output the transition duration
            "-preset", "fast", 
            "-c:v", "libx264", 
            "-c:a", "aac",
            str(output_path)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
