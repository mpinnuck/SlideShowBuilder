from pathlib import Path
from slideshow.slides.photo_slide import PhotoSlide
from slideshow.slides.video_slide import VideoSlide
from slideshow.transitions import get_transition
from slideshow.transitions.utils import get_video_duration

import shutil
import subprocess
import locale

class Slideshow:
    def __init__(self, config: dict):
        self.items = []
        self.transitions = []
        self.config = config
        self.resolution = tuple(config["resolution"])
        self.fps = self._detect_fps_from_locale()
        self.load_from_input(Path(config["input_folder"]))

    def _detect_fps_from_locale(self):
        """Detect appropriate FPS based on system locale - 25fps default (PAL), 30fps for NTSC regions"""
        try:
            # Try to get the most accurate locale information
            loc = None
            
            # First try Apple system locale (most accurate on Mac)
            try:
                import subprocess
                result = subprocess.run(['defaults', 'read', '-g', 'AppleLocale'], 
                                      capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    loc = result.stdout.strip()
                    print(f"[Slideshow] Apple system locale: {loc}")
            except:
                pass
            
            # Fallback to Python locale detection
            if not loc:
                loc = locale.getdefaultlocale()[0] or 'en_US'
                print(f"[Slideshow] Python locale: {loc}")
            
            # NTSC regions (30fps) - specific regions that use 30fps
            ntsc_regions = {
                'en_US', 'en_CA', 'fr_CA',  # North America
                'ja_JP',  # Japan
                'ko_KR'   # South Korea
            }
            
            # Check if locale matches any NTSC region
            if loc in ntsc_regions:
                print(f"[Slideshow] Using 30 fps (NTSC) for locale {loc}")
                return 30
            
            # Default to PAL (25fps) for everywhere else (including Australia)
            print(f"[Slideshow] Using 25 fps (PAL - default) for locale {loc}")
            return 25
            
        except Exception as e:
            print(f"[Slideshow] Error detecting locale: {e}, defaulting to 25 fps")
            return 25  # Default to 25fps as requested

    def load_from_input(self, folder: Path):
        if not folder.exists():
            return
        
        # First, collect all valid media files
        media_files = []
        for path in sorted(folder.glob("*")):
            if path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                media_files.append(("photo", path))
            elif path.suffix.lower() in [".mp4", ".mov"]:
                media_files.append(("video", path))
        
        # Create slides with appropriate durations
        for i, (media_type, path) in enumerate(media_files):
            is_last_slide = (i == len(media_files) - 1)
            
            if media_type == "photo":
                self.items.append(PhotoSlide(path, self.config["photo_duration"]))
            elif media_type == "video":
                video_duration_setting = self.config.get("video_duration", 5.0)
                
                # Handle special video duration settings
                if video_duration_setting == 0:
                    # Skip videos when duration is 0
                    print(f"Skipping video {path.name} (video_duration = 0)")
                    continue
                elif video_duration_setting == -1:
                    # Use full video duration when setting is -1
                    try:
                        actual_duration = get_video_duration(path)
                        print(f"Using full video duration for {path.name}: {actual_duration:.2f}s (video_duration = -1)")
                        self.items.append(VideoSlide(path, actual_duration))
                    except Exception as e:
                        print(f"Warning: Could not get video duration for {path}: {e}")
                        print(f"Skipping video {path.name}")
                        continue
                elif video_duration_setting > 0:
                    # For positive values, use configured duration or actual duration (whichever is lesser)
                    try:
                        actual_duration = get_video_duration(path)
                        
                        # Use the lesser of configured duration or actual duration
                        final_duration = min(video_duration_setting, actual_duration)
                        
                        # For last slide, ensure full video duration to prevent audio sync issues
                        if is_last_slide:
                            final_duration = actual_duration
                            print(f"Last slide video {path.name}: using full duration {final_duration:.2f}s (audio sync)")
                        else:
                            print(f"Video {path.name}: config={video_duration_setting}s, actual={actual_duration:.2f}s, using={final_duration:.2f}s")
                        
                        self.items.append(VideoSlide(path, final_duration))
                    except Exception as e:
                        print(f"Warning: Could not get video duration for {path}: {e}")
                        print(f"Using configured duration: {video_duration_setting}s")
                        self.items.append(VideoSlide(path, video_duration_setting))
                else:
                    print(f"Invalid video_duration setting: {video_duration_setting}, skipping video {path.name}")
                    continue
        
        # Get transition type from config, default to 'fade'
        transition_type = self.config.get("transition_type", "fade")
        transition_duration = self.config["transition_duration"]
        
        # Create transitions between slides
        self.transitions = []
        for i in range(len(self.items) - 1):
            try:
                transition = get_transition(transition_type, duration=transition_duration)
                self.transitions.append(transition)
            except (ValueError, ImportError) as e:
                # Fallback to fade if requested transition is not available
                print(f"Warning: {transition_type} transition not available ({e}), using fade")
                transition = get_transition("fade", duration=transition_duration)
                self.transitions.append(transition)

    def get_actual_concat_duration(self, concat_file: Path) -> float:
        cmd = [
            "ffprobe", "-v", "error",
            "-f", "concat", "-safe", "0",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(concat_file)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            try:
                return float(result.stdout.strip())
            except ValueError:
                return None
        return None

    def render(self, output_path: Path, progress_callback=None, log_callback=None):
        # Create working folder in output directory
        working_folder = output_path.parent / "working"
        if working_folder.exists():
            if log_callback:
                log_callback("Cleaning existing working folder...")
            print(f"Cleaning existing working folder: {working_folder}")
            try:
                shutil.rmtree(working_folder)
            except Exception as e:
                error_msg = f"Failed to clean working folder: {e}"
                print(error_msg)
                if log_callback:
                    log_callback(error_msg)
                raise

        try:
            working_folder.mkdir(parents=True, exist_ok=True)
            print(f"Working folder created: {working_folder}")
            if log_callback:
                log_callback(f"Working folder ready: {working_folder}")
        except Exception as e:
            error_msg = f"Failed to create working folder: {e}"
            print(error_msg)
            if log_callback:
                log_callback(error_msg)
            raise

        soundtrack_path = self.config.get("soundtrack", "")
        has_soundtrack = soundtrack_path and Path(soundtrack_path).exists()
        if has_soundtrack:
            if log_callback:
                log_callback(f"Using soundtrack: {soundtrack_path}")
            print(f"Soundtrack found: {soundtrack_path}")
        else:
            if soundtrack_path:
                print(f"Warning: Soundtrack file not found: {soundtrack_path}")
                if log_callback:
                    log_callback(f"Warning: Soundtrack file not found: {soundtrack_path}")
            else:
                print("No soundtrack specified")
                if log_callback:
                    log_callback("No soundtrack specified")

        clips = []
        total_items = len(self.items)
        total_transitions = len(self.items) - 1 if len(self.items) > 1 else 0
        processing_weight = total_items + total_transitions
        assembly_weight = processing_weight
        total_weighted_steps = processing_weight + assembly_weight

        transition_duration = self.config.get("transition_duration", 1)
        has_transitions = len(self.items) > 1

        for i, item in enumerate(self.items):
            if progress_callback:
                current_progress = i
                progress_callback(current_progress, total_weighted_steps)
            if log_callback:
                log_callback(f"Processing slide {i+1}/{total_items}")

            effective_duration = item.duration
            if has_transitions:
                if i == 0:
                    # First slide: trim end for outgoing transition
                    effective_duration -= transition_duration / 2
                elif 0 < i < len(self.items) - 1:
                    # Middle slides: trim start and end for both transitions
                    effective_duration -= transition_duration
                # Last slide: do not trim at all (play full length)

            effective_duration = max(effective_duration, 0.5)
            print(f"Item {i}: original duration {item.duration}s, effective duration {effective_duration}s")

            out = working_folder / f"slide_{i:03}.mp4"
            original_duration = item.duration
            item.duration = effective_duration
            item.render(out, self.resolution, self.fps)
            item.duration = original_duration
            clips.append(out)

        merged = []
        for i in range(len(clips) - 1):
            if progress_callback:
                current_progress = total_items + i
                progress_callback(current_progress, total_weighted_steps)
            if log_callback:
                log_callback(f"Creating transition {i+1}/{total_transitions}")

            merged.append(clips[i])
            trans_out = working_folder / f"trans_{i:03}.mp4"

            # Use the transition that was already created in load_from_input
            transition = self.transitions[i]
            transition.render(clips[i], clips[i + 1], trans_out)

            merged.append(trans_out)
        merged.append(clips[-1])

        concat_file = working_folder / "concat.txt"
        with concat_file.open("w") as f:
            for c in merged:
                f.write(f"file '{c.resolve()}'\n")

        if progress_callback:
            progress_callback(processing_weight, total_weighted_steps)
        if log_callback:
            log_callback("Assembling final video...")

        concat_duration = self.get_actual_concat_duration(concat_file)
        if concat_duration:
            total_duration = concat_duration
            print(f"[Slideshow] Using ffprobe concat duration: {total_duration:.3f}s")
        else:
            # fallback to manually calculated total_duration if ffprobe fails
            transition_duration = self.config.get("transition_duration", 1)
            has_transitions = len(self.items) > 1
            total_duration = 0
            for i, item in enumerate(self.items):
                effective_duration = item.duration
                if has_transitions:
                    if i == 0:
                        effective_duration -= transition_duration / 2
                    elif i == len(self.items) - 1:
                        effective_duration -= transition_duration / 2
                    else:
                        effective_duration -= transition_duration
                effective_duration = max(effective_duration, 0.5)
                total_duration += effective_duration

            if has_transitions:
                total_duration += (len(self.items) - 1) * transition_duration

            print(f"[Slideshow] Calculated total video duration: {total_duration:.2f}s")


        import re
        if has_soundtrack:
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_file),
                "-stream_loop", "-1", "-i", str(soundtrack_path),
                "-c:v", "libx264",
                "-c:a", "aac",
                "-map", "0:v",
                "-map", "1:a",
                "-t", str(total_duration),
                "-af", f"afade=in:st=0:d=1,afade=out:st={total_duration-1}:d=1",
                "-preset", "fast",
                "-movflags", "+faststart",
                "-progress", "pipe:1",
                str(output_path)
            ]
            if log_callback:
                log_callback("Assembling final video with soundtrack...")
        else:
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(concat_file),
                "-c:v", "libx264",
                "-c:a", "aac",
                "-preset", "fast",
                "-movflags", "+faststart",
                "-progress", "pipe:1",
                str(output_path)
            ]
            if log_callback:
                log_callback("Assembling final video...")

        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        assembly_progress = 0
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output and (progress_callback or log_callback):
                time_match = re.search(r'out_time_ms=(\d+)', output)
                if time_match:
                    time_ms = int(time_match.group(1))
                    time_seconds = time_ms / 1000000
                    if total_duration > 0:
                        assembly_progress = min(time_seconds / total_duration, 1.0)
                        current_progress = processing_weight + (assembly_progress * assembly_weight)
                        if progress_callback:
                            progress_callback(int(current_progress), total_weighted_steps)
                        if log_callback:
                            log_callback(f"Assembling final video... {assembly_progress*100:.1f}%")

        process.wait()
        if process.returncode != 0:
            stderr_output = process.stderr.read()
            raise subprocess.CalledProcessError(process.returncode, "ffmpeg", stderr_output)

        if progress_callback:
            progress_callback(total_weighted_steps, total_weighted_steps)
        if log_callback:
            log_callback("Video export completed!")

        if log_callback:
            log_callback("Cleaning working folder...")
        try:
            shutil.rmtree(working_folder)
            print(f"Working folder cleaned: {working_folder}")
        except Exception as e:
            print(f"Warning: Failed to clean working folder: {e}")
