from pathlib import Path
import subprocess

class FadeTransition:
    def __init__(self, duration=1.0):
        self.duration = duration

    def render(self, from_path: Path, to_path: Path, output_path: Path):
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
