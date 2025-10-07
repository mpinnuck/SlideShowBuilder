# slideshow/slideshowmodel.py
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional

from slideshow.slides.photo_slide import PhotoSlide
from slideshow.slides.video_slide import VideoSlide
from slideshow.transitions import get_transition
from slideshow.transitions.utils import get_video_duration
from slideshow.config import DEFAULT_CONFIG
from slideshow.transitions.transition_factory import TransitionFactory
from slideshow.transitions.intro_title import IntroTitle
from slideshow.transitions.ffmpeg_cache import FFmpegCache
from slideshow.transitions.ffmpeg_paths import FFmpegPaths


class Slideshow:
    def __init__(self, config: dict, log_callback=None, progress_callback=None):
        self.config = config
        self.log_callback = log_callback
        self.progress_callback = progress_callback

        self.slides: List[PhotoSlide | VideoSlide] = []
        self.transitions: List[object] = []  # from get_transition()

        # Use config output folder instead of hardcoded path
        output_folder = Path(self.config.get("output_folder", "media/output"))
        self.working_dir = output_folder / "working"
        if self.working_dir.exists():
            self._log(f"[Slideshow] Cleaning existing working dir: {self.working_dir}")
            try:
                # Clean everything except ffmpeg_cache directory
                for item in self.working_dir.iterdir():
                    if item.name != "ffmpeg_cache":
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            item.unlink()
            except Exception as e:
                self._log(f"[Slideshow] WARNING: failed to clean working dir: {e}")
        self.working_dir.mkdir(parents=True, exist_ok=True)

        self.concat_file = self.working_dir / "concat.txt"
        self.video_only = self.working_dir / "slideshow_video_only.mp4"   # Pass 1 output
        self.mux_no_fade = self.working_dir / "slideshow_mux_no_fade.mp4" # Pass 2 output

        fps = self.config.get("fps", DEFAULT_CONFIG["fps"])
        resolution = tuple(self.config.get("resolution", DEFAULT_CONFIG["resolution"]))
        self._log(f"[Slideshow] Using fps: {fps}, resolution: {resolution}")


        # Ceate slected transition
        self.transition = TransitionFactory.create(
            name=self.config.get("transition_type", DEFAULT_CONFIG["transition_type"]),
            duration=float(self.config.get("transition_duration", DEFAULT_CONFIG["transition_duration"])),
            resolution=tuple(self.config.get("resolution", DEFAULT_CONFIG["resolution"])),
            fps=int(self.config.get("fps", DEFAULT_CONFIG["fps"])),
            config=self.config  # Pass full config for transition-specific settings
        )

        self.load_slides()

        # Configure FFmpeg cache under output folder for user control
        cache_enabled = self.config.get("ffmpeg_cache_enabled", True)
        if cache_enabled:
            cache_dir = self.config.get("ffmpeg_cache_dir")
            if not cache_dir:
                # Default to output_folder/working/ffmpeg_cache
                output_folder = Path(self.config.get("output_folder", "media/output"))
                cache_dir = output_folder / "working" / "ffmpeg_cache"
            
            FFmpegCache.configure(cache_dir)
            self._log(f"[FFmpegCache] Using cache directory: {cache_dir}")
            
            # Log initial cache stats if cache has existing content
            cache_stats = FFmpegCache.get_cache_stats()
            if cache_stats.get("total_entries", 0) > 0:
                self._log(f"[FFmpegCache] Loaded cache: {cache_stats['total_entries']} entries, "
                         f"{cache_stats['total_size_mb']:.1f} MB")
        else:
            FFmpegCache.enable(False)
            self._log("[FFmpegCache] Caching disabled by configuration")

    # -------------------------------
    # Logging helper
    # -------------------------------
    def _log(self, msg: str):
        if self.log_callback:
            self.log_callback(msg)
        else:
            print(msg)

    # -------------------------------
    # FFprobe utilities
    # -------------------------------
    def get_file_duration(self, path: Path) -> Optional[float]:
        """Return file duration (seconds) or None."""
        try:
            cmd = [
                FFmpegPaths.ffprobe(), "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception as e:
            self._log(f"[Slideshow] WARN: get_file_duration failed for {path}: {e}")
        return None


    def get_estimated_duration(self, fudge: float = 1.1) -> float:
        total = sum(getattr(slide, "duration", 0) for slide in self.slides)
        if len(self.slides) > 1:
            total += (len(self.slides) - 1) * self.config.get("transition_duration", 1.0)
        return total * fudge

    # -------------------------------
    # Slide Loading
    # -------------------------------
    def load_slides(self):
        input_folder = Path(self.config["input_folder"])
        if not input_folder.exists():
            self._log(f"[Slideshow] Input folder not found: {input_folder}")
            return

        # Get multislide frequency setting
        multislide_frequency = self.config.get("multislide_frequency", 0)
        
        media_files = sorted(input_folder.glob("*"))
        skip_until = 0  # Track files consumed by MultiSlides
        
        # Counters for import summary
        photo_count = 0
        video_count = 0
        multislide_count = 0
        
        # Log initial message
        total_files = len(media_files)
        self._log(f"[Slideshow] Loading {total_files} files...")
        
        for i, path in enumerate(media_files):
            # Skip files that were consumed by previous MultiSlides
            if i < skip_until:
                continue
                
            ext = path.suffix.lower()
            
            # Check if we should create a multislide at this position
            if (multislide_frequency > 0 and 
                len(self.slides) > 0 and  # Not the first slide
                (len(self.slides) + 1) % multislide_frequency == 0 and  # Hit frequency
                i + 2 < len(media_files) and  # Have enough files left
                ext in (".jpg", ".jpeg", ".png")):  # Current file is image
                
                # Check if next 2 files are also images
                next_files = media_files[i:i+3]
                if all(f.suffix.lower() in (".jpg", ".jpeg", ".png") for f in next_files):
                    # Create MultiSlide from 3 consecutive image files
                    resolution = tuple(self.config.get("resolution", DEFAULT_CONFIG["resolution"]))
                    fps = self.config.get("fps", DEFAULT_CONFIG["fps"])
                    
                    from slideshow.slides.multi_slide import MultiSlide
                    multi_slide = MultiSlide(
                        i=i,
                        media_files=media_files,
                        duration=self.config["photo_duration"],
                        resolution=resolution,
                        fps=fps
                    )
                    self.slides.append(multi_slide)
                    
                    # Count the 3 photos consumed by the multislide
                    photo_count += 3
                    multislide_count += 1
                    
                    # Skip the files consumed by the multislide
                    skip_until = i + multi_slide.get_slide_count()
                    continue
            
            # Process single file normally
            if ext in (".jpg", ".jpeg", ".png"):
                resolution = tuple(self.config.get("resolution", DEFAULT_CONFIG["resolution"]))
                fps = self.config.get("fps", DEFAULT_CONFIG["fps"])
                self.slides.append(PhotoSlide(path, self.config["photo_duration"], fps=fps, resolution=resolution))
                photo_count += 1
            elif ext in (".mp4", ".mov"):
                video_duration_setting = self.config.get("video_duration", 5.0)
                if video_duration_setting == 0:
                    self._log(f"[Slideshow] Skipping video: {path.name} (video_duration=0)")
                    continue
                try:
                    actual_duration = get_video_duration(path)
                except Exception as e:
                    self._log(f"[Slideshow] WARNING: could not get duration for {path.name}: {e}")
                    actual_duration = video_duration_setting

                resolution = tuple(self.config.get("resolution", DEFAULT_CONFIG["resolution"]))
                fps = self.config.get("fps", DEFAULT_CONFIG["fps"])
                
                if video_duration_setting == -1:
                    self._log(f"[Slideshow] Using full duration for {path.name}: {actual_duration:.2f}s")
                    self.slides.append(VideoSlide(path, actual_duration, fps=fps, resolution=resolution))
                    video_count += 1
                else:
                    final_duration = actual_duration if i == len(media_files) - 1 else min(video_duration_setting, actual_duration)
                    if i == len(media_files) - 1:
                        self._log(f"[Slideshow] Last slide {path.name}: forcing full duration {final_duration:.2f}s")
                    self.slides.append(VideoSlide(path, final_duration, fps=fps, resolution=resolution))
                    video_count += 1
            
            # Show progress every 10 files (overwriting the same line)
            if (i + 1) % 10 == 0 or (i + 1) == total_files:
                self._log(f"[Slideshow] Loaded {i + 1}/{total_files} files...\r")
        
        # Final newline after progress updates
#        self._log("")
        
        # Log import summary
        total_input_files = len(media_files)
        total_slides = len(self.slides)
        single_photo_slides = (photo_count - (multislide_count * 3))  # Photos not in MultiSlides
        
        self._log(f"[Slideshow] Importing {total_input_files} files → {total_slides} slides: {single_photo_slides} photo, {video_count} video, {multislide_count} multi")
        
        # Removed self.update_transitions() from here to decouple transitions from slide loading
        # Transitions should be updated explicitly when needed, such as during export or transition type change.









    # -------------------------------
    # Internal: run ffmpeg and stream progress into the assembly half
    # -------------------------------
    def _run_ffmpeg_progress(self, cmd: list, expected_seconds: float,
                             base_offset: int, span_steps: int, total_steps: int):
        """
        Streams ffmpeg -progress pipe:1 (out_time_ms=...) and maps to progress bar.
        base_offset: processing_weight offset (start of assembly region)
        span_steps:  portion of assembly steps to fill (e.g. 40% or 50% of assembly half)
        """
#        self._log(f"[Slideshow] Running ffmpeg:\n{' '.join(cmd)}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        last_report = -1
        while True:
            line = proc.stdout.readline()
            if line == '' and proc.poll() is not None:
                break
            m = re.search(r'out_time_ms=(\d+)', line)
            if m and self.progress_callback and expected_seconds and expected_seconds > 0:
                elapsed = int(m.group(1)) / 1_000_000.0
                frac = max(0.0, min(elapsed / expected_seconds, 1.0))
                current = base_offset + int(frac * span_steps)
                if current != last_report:
                    self.progress_callback(current, total_steps)
                    last_report = current

        proc.wait()
        if proc.returncode != 0:
            stderr_out = proc.stderr.read() if proc.stderr else ""
            raise subprocess.CalledProcessError(proc.returncode, cmd, stderr_out)

    def set_transition_type(self, transition_type: str):
        """Update the transition type in the configuration."""
        self.config["transition_type"] = transition_type
        self._log(f"[Slideshow] Transition type updated to: {transition_type}")

    # -------------------------------
    # Rendering
    # -------------------------------
    def render(self, output_path: Path, progress_callback=None, log_callback=None):
        """
        Render slideshow into final video.
        Uses SlideItem.render() to generate individual clips, then transitions,
        then concatenates everything into one final video with optional audio.
        """
        if log_callback:
            self.log_callback = log_callback
        if progress_callback:
            self.progress_callback = progress_callback

        try:
            total_items = len(self.slides)
            total_transitions = max(0, total_items - 1)
            processing_weight = total_items + total_transitions
            assembly_weight = max(1, processing_weight)
            total_weighted_steps = processing_weight + assembly_weight



            # --- Render slides ---
            self._log("")  # Newline before slide rendering
            for i, slide in enumerate(self.slides):
                self._log(f"[Slideshow] Rendering slides ({i+1}/{total_items})...{'\r' if i < total_items else '\n'}")
                slide.render(self.working_dir)  # sets slide._rendered_clip
                if self.progress_callback:
                    self.progress_callback(i + 1, total_weighted_steps)

            # --- Render Intro Title (before slides) ---
            intro = IntroTitle()
            self._intro_clip = None
#            if False: #intro.enabled and self.slides:
            if intro.enabled and self.slides:
                first_slide = self.slides[0]
                first_frame = first_slide.get_from_image()
                intro_path = self.working_dir / "intro_title.mp4"
                self._log(f"[Slideshow] Rendering intro title: {intro.text}")
                self._intro_clip = intro.render(first_frame, intro_path)


            # --- Render transitions ---
            self._log("")  # Newline before transition rendering
            transition_clips = []
            for i in range(total_items - 1):
                self._log(f"[Slideshow] Rendering transitions ({i+1}/{total_transitions})...{'\r' if i < total_transitions else '\n'}")
                trans_out = self.working_dir / f"trans_{i:03}.mp4"
                self.transition.render(i, self.slides, trans_out)
                transition_clips.append(trans_out)  # Just store the path
                if self.progress_callback:
                    self.progress_callback(total_items + i + 1, total_weighted_steps)

            # --- Write concat file ---
            with self.concat_file.open("w") as f:
                # Prepend intro clip if it exists
                if self._intro_clip:
                    f.write(f"file '{self._intro_clip.resolve()}'\n")

                for i, slide in enumerate(self.slides):
                    f.write(f"file '{slide.get_rendered_clip().resolve()}'\n")
                    # Insert transition after every slide except last
                    if i < len(transition_clips):
                        f.write(f"file '{transition_clips[i].resolve()}'\n")

            # --- Assemble & mux ---
            expected_duration = self.get_estimated_duration()
            self._log(f"[Slideshow] Estimated duration for progress scaling: {expected_duration:.2f}s")

            # --- Pass 1: Assemble video-only ---
            self._log(f"[Slideshow] Assembling video-only...")
            cmd_pass1 = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0", "-i", str(self.concat_file),
                "-c:v", "libx264", "-preset", "fast",
                "-movflags", "+faststart", "-progress", "pipe:1",
                str(self.video_only),
            ]
            self._run_ffmpeg_progress(cmd_pass1,
                                    expected_duration or 1.0,
                                    base_offset=processing_weight,
                                    span_steps=int(assembly_weight * 0.4),
                                    total_steps=total_weighted_steps)

            actual_duration = self.get_file_duration(self.video_only)
            self._log(f"[Slideshow] Video-only duration: {actual_duration:.2f}s" if actual_duration else
                    "[Slideshow] WARNING: could not determine duration — using estimate")

            # --- Pass 2: Mux soundtrack (if present) ---
            soundtrack_path = self.config.get("soundtrack", "")
            has_soundtrack = bool(soundtrack_path) and Path(soundtrack_path).exists()

            self._log("[Slideshow] Muxing soundtrack..." if has_soundtrack else "[Slideshow] Finalizing video (no soundtrack)...")
            cmd_pass2 = (
                [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(self.video_only),
                    "-stream_loop", "-1", "-i", str(soundtrack_path),
                    "-map", "0:v", "-map", "1:a",
                    "-t", f"{actual_duration:.3f}" if actual_duration else "0",
                    "-c:v", "copy", "-c:a", "aac",
                    "-movflags", "+faststart", "-progress", "pipe:1",
                    str(self.mux_no_fade),
                ]
                if has_soundtrack
                else [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", str(self.video_only),
                    "-c", "copy", "-movflags", "+faststart",
                    "-progress", "pipe:1", str(self.mux_no_fade),
                ]
            )
            self._run_ffmpeg_progress(cmd_pass2,
                                    actual_duration or 1.0,
                                    base_offset=processing_weight + int(assembly_weight * 0.4),
                                    span_steps=int(assembly_weight * 0.5),
                                    total_steps=total_weighted_steps)

            # --- Pass 3: Fade audio at end (if soundtrack present & duration known) ---
            if has_soundtrack and actual_duration and actual_duration > 1.0:
                self._log(f"[Slideshow] Applying 1s audio fade at {actual_duration-1:.2f}s")
                fade_filter = f"afade=out:st={actual_duration - 1:.2f}:d=1"
                cmd_pass3 = [
                    FFmpegPaths.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(self.mux_no_fade),
                    "-c:v", "copy", "-af", fade_filter,
                    "-movflags", "+faststart", "-progress", "pipe:1",
                    str(output_path),
                ]
                self._run_ffmpeg_progress(cmd_pass3,
                                        actual_duration,
                                        base_offset=processing_weight + int(assembly_weight * 0.9),
                                        span_steps=int(assembly_weight * 0.1),
                                        total_steps=total_weighted_steps)
            else:
                shutil.copyfile(self.mux_no_fade, output_path)
                if self.progress_callback:
                    self.progress_callback(total_weighted_steps, total_weighted_steps)

            self._log(f"[Slideshow] Slideshow complete: {output_path}")
            
            # Display cache statistics
            cache_stats = FFmpegCache.get_cache_stats()
            if cache_stats.get("enabled", False):
                hit_rate = cache_stats.get("hit_rate_percent", 0)
                total_requests = cache_stats.get("total_requests", 0)
                
                if total_requests > 0:
                    self._log(f"[FFmpegCache] Cache stats: {cache_stats['total_entries']} entries "
                             f"({cache_stats['clip_count']} clips, {cache_stats['frame_count']} frames), "
                             f"{cache_stats['total_size_mb']:.1f} MB")
                    self._log(f"[FFmpegCache] Performance: {cache_stats['cache_hits']} hits, "
                             f"{cache_stats['cache_misses']} misses, {hit_rate}% hit rate")
                else:
                    self._log(f"[FFmpegCache] Cache stats: {cache_stats['total_entries']} entries "
                             f"({cache_stats['clip_count']} clips, {cache_stats['frame_count']} frames), "
                             f"{cache_stats['total_size_mb']:.1f} MB (no usage data yet)")

        finally:
            if self.working_dir.exists():
                self._log(f"[Slideshow] Cleaning working dir: {self.working_dir}")
                # Clean everything except ffmpeg_cache directory
                try:
                    for item in self.working_dir.iterdir():
                        if item.name != "ffmpeg_cache":
                            if item.is_dir():
                                shutil.rmtree(item, ignore_errors=True)
                            else:
                                item.unlink(missing_ok=True)
                except Exception as e:
                    self._log(f"[Slideshow] WARNING: failed to clean working dir: {e}")
    
    # -------------------------------
    # Cache Management
    # -------------------------------
    def get_cache_stats(self) -> dict:
        """Get FFmpeg cache statistics."""
        return FFmpegCache.get_cache_stats()
    
    def clear_cache(self):
        """Clear the FFmpeg cache."""
        FFmpegCache.clear_cache()
        self._log("[FFmpegCache] Cache cleared")
    
    def cleanup_old_cache_entries(self, max_age_days: int = 30):
        """Remove cache entries older than specified days."""
        FFmpegCache.cleanup_old_entries(max_age_days)
    
    def enable_cache(self, enabled: bool = True):
        """Enable or disable FFmpeg caching."""
        FFmpegCache.enable(enabled)
        status = "enabled" if enabled else "disabled"
        self._log(f"[FFmpegCache] Caching {status}")
    
    def reset_cache_stats(self):
        """Reset cache hit/miss statistics."""
        FFmpegCache.reset_stats()
        self._log("[FFmpegCache] Cache statistics reset")

