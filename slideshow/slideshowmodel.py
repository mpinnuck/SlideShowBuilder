from pathlib import Path
from slideshow.slides.photo_slide import PhotoSlide
from slideshow.slides.video_slide import VideoSlide
from slideshow.transitions.fade_transition import FadeTransition
import shutil
import subprocess

class Slideshow:
    def __init__(self, config: dict):
        self.items = []
        self.transitions = []
        self.config = config
        self.resolution = tuple(config["resolution"])
        self.fps = config["fps"]
        self.load_from_input(Path(config["input_folder"]))

    def load_from_input(self, folder: Path):
        if not folder.exists():
            return
        for path in sorted(folder.glob("*")):
            if path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                self.items.append(PhotoSlide(path, self.config["photo_duration"]))
            elif path.suffix.lower() in [".mp4", ".mov"]:
                self.items.append(VideoSlide(path, self.config["video_duration"]))
        self.transitions = [FadeTransition(self.config["transition_duration"])] * (len(self.items) - 1)

    def render(self, output_path: Path, progress_callback=None):
        # Create working folder in output directory
        working_folder = output_path.parent / "working"
        
        # Check if working folder exists and clean it if it does
        if working_folder.exists():
            if progress_callback:
                progress_callback(0, 1, "Cleaning existing working folder...")
            print(f"Cleaning existing working folder: {working_folder}")
            try:
                shutil.rmtree(working_folder)
            except Exception as e:
                error_msg = f"Failed to clean working folder: {e}"
                print(error_msg)
                if progress_callback:
                    progress_callback(0, 1, error_msg)
                raise
        
        # Create fresh working folder
        try:
            working_folder.mkdir(parents=True, exist_ok=True)
            print(f"Working folder created: {working_folder}")
            if progress_callback:
                progress_callback(0, 1, f"Working folder ready: {working_folder}")
        except Exception as e:
            error_msg = f"Failed to create working folder: {e}"
            print(error_msg)
            if progress_callback:
                progress_callback(0, 1, error_msg)
            raise
        clips = []
        total_items = len(self.items)
        total_transitions = len(self.items) - 1 if len(self.items) > 1 else 0
        # Weight final assembly as equivalent to all other steps combined
        # Since final assembly takes about 50% of total time
        processing_weight = total_items + total_transitions  # Weight for slides + transitions
        assembly_weight = processing_weight  # Final assembly gets equal weight
        total_weighted_steps = processing_weight + assembly_weight
        
        # Calculate effective duration for clips (reduced by transition overlap)
        transition_duration = self.config.get("transition_duration", 1)
        has_transitions = len(self.items) > 1

        for i, item in enumerate(self.items):
            if progress_callback:
                current_progress = i
                progress_callback(current_progress, total_weighted_steps, f"Processing slide {i+1}/{total_items}")
            
            # Calculate duration: reduce by half transition on each side except for first/last
            effective_duration = item.duration
            if has_transitions:
                if i == 0:  # First item: only reduce end
                    effective_duration = item.duration - (transition_duration / 2)
                elif i == len(self.items) - 1:  # Last item: only reduce start
                    effective_duration = item.duration - (transition_duration / 2)
                else:  # Middle items: reduce both sides
                    effective_duration = item.duration - transition_duration
            
            # Ensure minimum duration
            effective_duration = max(effective_duration, 0.5)
            
            print(f"Item {i}: original duration {item.duration}s, effective duration {effective_duration}s")
            
            out = working_folder / f"slide_{i:03}.mp4"
            # Temporarily modify duration for rendering
            original_duration = item.duration
            item.duration = effective_duration
            item.render(out, self.resolution, self.fps)
            item.duration = original_duration  # Restore original
            clips.append(out)

        merged = []
        for i in range(len(clips) - 1):
            if progress_callback:
                current_progress = total_items + i
                progress_callback(current_progress, total_weighted_steps, f"Creating transition {i+1}/{total_transitions}")
            merged.append(clips[i])
            trans_out = working_folder / f"trans_{i:03}.mp4"
            self.transitions[i].render(clips[i], clips[i+1], trans_out)
            merged.append(trans_out)
        merged.append(clips[-1])

        concat_file = working_folder / "concat.txt"
        with concat_file.open("w") as f:
            for c in merged:
                f.write(f"file '{c.resolve()}'\n")

        if progress_callback:
            # Final assembly starts at 50% (processing_weight) and goes to 100%
            progress_callback(processing_weight, total_weighted_steps, "Assembling final video...")

        # Calculate total duration for progress tracking
        total_duration = sum(item.duration for item in self.items)
        if len(self.items) > 1:
            total_duration += (len(self.items) - 1) * self.config.get("transition_duration", 1)
        
        # Run FFmpeg with progress monitoring
        import re
        process = subprocess.Popen([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-c:v", "libx264",  # Re-encode video with H264
            "-c:a", "aac",      # Re-encode audio with AAC
            "-preset", "fast",  # Fast encoding preset
            "-movflags", "+faststart",  # Optimize for streaming/QuickTime
            "-progress", "pipe:1",  # Send progress to stdout
            str(output_path)
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        
        # Monitor progress
        assembly_progress = 0
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output and progress_callback:
                # Look for time progress in FFmpeg output
                time_match = re.search(r'out_time_ms=(\d+)', output)
                if time_match:
                    time_ms = int(time_match.group(1))
                    time_seconds = time_ms / 1000000  # Convert microseconds to seconds
                    if total_duration > 0:
                        assembly_progress = min(time_seconds / total_duration, 1.0)
                        # Map assembly progress (0-1) to final 50% of progress bar
                        current_progress = processing_weight + (assembly_progress * assembly_weight)
                        progress_callback(int(current_progress), total_weighted_steps, 
                                        f"Assembling final video... {assembly_progress*100:.1f}%")
        
        # Wait for process to complete
        process.wait()
        if process.returncode != 0:
            stderr_output = process.stderr.read()
            raise subprocess.CalledProcessError(process.returncode, "ffmpeg", stderr_output)
        
        if progress_callback:
            progress_callback(total_weighted_steps, total_weighted_steps, "Video export completed!")
        
        # Clean up working folder
        if progress_callback:
            progress_callback(total_items + total_transitions + 1, total_items + total_transitions + 1, "Cleaning working folder...")
        try:
            shutil.rmtree(working_folder)
            print(f"Working folder cleaned: {working_folder}")
        except Exception as e:
            print(f"Warning: Failed to clean working folder: {e}")
            # Don't raise - video was created successfully
