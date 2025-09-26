# slideshow/slideshowmodel.py
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from slideshow.slides.photo_slide import PhotoSlide
from slideshow.slides.video_slide import VideoSlide
from slideshow.transitions import get_transition
from slideshow.transitions.utils import get_video_duration


class Slideshow:
    def __init__(self, config: dict, log_callback=None, progress_callback=None):
        self.config = config
        self.log_callback = log_callback
        self.progress_callback = progress_callback

        self.slides: List[PhotoSlide | VideoSlide] = []
        self.transitions: List[object] = []  # from get_transition()

        self.working_dir = Path("data/output/working")
        if self.working_dir.exists():
            self._log(f"[Slideshow] Cleaning existing working dir: {self.working_dir}")
            try:
                shutil.rmtree(self.working_dir)
            except Exception as e:
                self._log(f"[Slideshow] WARNING: failed to clean working dir: {e}")
        self.working_dir.mkdir(parents=True, exist_ok=True)

        self.concat_file = self.working_dir / "concat.txt"
        self.video_only = self.working_dir / "slideshow_video_only.mp4"   # Pass 1 output
        self.mux_no_fade = self.working_dir / "slideshow_mux_no_fade.mp4" # Pass 2 output

        self.load_slides()

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
                "ffprobe", "-v", "error",
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

    def get_concat_duration(self, concat_file: Path) -> Optional[float]:
        """Return the expected video timeline from the concat list (seconds), or None."""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-f", "concat", "-safe", "0",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(concat_file),
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception as e:
            self._log(f"[Slideshow] WARN: concat duration probe failed: {e}")
        return None

    # -------------------------------
    # Slide Loading
    # -------------------------------
    def load_slides(self):
        input_folder = Path(self.config["input_folder"])
        if not input_folder.exists():
            self._log(f"[Slideshow] Input folder not found: {input_folder}")
            return

        media_files = sorted(input_folder.glob("*"))
        for i, path in enumerate(media_files):
            ext = path.suffix.lower()
            if ext in (".jpg", ".jpeg", ".png"):
                self._log(f"[Slideshow] Adding photo: {path.name}")
                self.slides.append(PhotoSlide(path, self.config["photo_duration"]))
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

                if video_duration_setting == -1:
                    self._log(f"[Slideshow] Using full duration for {path.name}: {actual_duration:.2f}s")
                    self.slides.append(VideoSlide(path, actual_duration))
                else:
                    final_duration = actual_duration if i == len(media_files) - 1 else min(video_duration_setting, actual_duration)
                    if i == len(media_files) - 1:
                        self._log(f"[Slideshow] Last slide {path.name}: forcing full duration {final_duration:.2f}s")
                    self.slides.append(VideoSlide(path, final_duration))

        # build transitions
        transition_type = self.config.get("transition_type", "fade")
        transition_duration = self.config.get("transition_duration", 1)
        for _ in range(max(0, len(self.slides) - 1)):
            try:
                self.transitions.append(get_transition(transition_type, duration=transition_duration))
            except (ValueError, ImportError) as e:
                self._log(f"[Slideshow] WARNING: transition '{transition_type}' not available ({e}), using fade")
                self.transitions.append(get_transition("fade", duration=transition_duration))

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
        self._log(f"[Slideshow] Running ffmpeg:\n{' '.join(cmd)}")
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

    # -------------------------------
    # Rendering
    # -------------------------------
    def render(self, output_path: Path, progress_callback=None, log_callback=None):
        """
        Keeps the legacy signature expected by SlideshowController.
        If callbacks are provided here, they override ones set at __init__.
        """
        if log_callback:
            self.log_callback = log_callback
        if progress_callback:
            self.progress_callback = progress_callback

        try:
            # Allocate 50% to slides+transitions, 50% to finalization (passes 1–3)
            total_items = len(self.slides)
            total_transitions = max(0, total_items - 1)
            processing_weight = total_items + total_transitions              # first half
            assembly_weight = max(1, processing_weight)                      # second half (mirrors first)
            total_weighted_steps = processing_weight + assembly_weight

            clips = []
            # --- Render slides ---
            for i, slide in enumerate(self.slides):
                self._log(f"[Slideshow] Rendering slide {i+1}/{total_items} ({slide.__class__.__name__})")
                out_path = self.working_dir / f"slide_{i:03}.mp4"
                slide.render(out_path, log_callback=self.log_callback)
                clips.append(out_path)
                if self.progress_callback:
                    self.progress_callback(i + 1, total_weighted_steps)

            # --- Render transitions ---
            merged = []
            for i in range(len(clips) - 1):
                merged.append(clips[i])
                trans_out = self.working_dir / f"trans_{i:03}.mp4"
                self._log(f"[Slideshow] Rendering transition {i+1}/{len(clips)-1}")
                self.transitions[i].render(clips[i], clips[i + 1], trans_out)
                merged.append(trans_out)
                if self.progress_callback:
                    self.progress_callback(total_items + i + 1, total_weighted_steps)
            if clips:
                merged.append(clips[-1])

            # --- Write concat file ---
            with self.concat_file.open("w") as f:
                for c in merged:
                    f.write(f"file '{c.resolve()}'\n")

            # Estimate duration for progress scaling during Pass 1
            expected_duration_concat = self.get_concat_duration(self.concat_file)
            if expected_duration_concat is None:
                # Rough fallback estimate
                transition_duration = self.config.get("transition_duration", 1)
                has_transitions = len(self.slides) > 1
                est = 0.0
                for idx, s in enumerate(self.slides):
                    eff = s.duration
                    if has_transitions:
                        if idx == 0 or idx == len(self.slides) - 1:
                            eff -= transition_duration / 2
                        else:
                            eff -= transition_duration
                    est += max(eff, 0.5)
                if has_transitions:
                    est += (len(self.slides) - 1) * transition_duration
                expected_duration_concat = max(1.0, est)
                self._log(f"[Slideshow] Using estimated concat duration: {expected_duration_concat:.2f}s")
            else:
                self._log(f"[Slideshow] Using probed concat duration: {expected_duration_concat:.2f}s")

            # Split assembly half: Pass1 40%, Pass2 50%, Pass3 10% (sums to 100% of assembly region)
            pass1_span = int(assembly_weight * 0.40)
            pass2_span = int(assembly_weight * 0.50)
            pass3_span = assembly_weight - pass1_span - pass2_span
            assembly_base = processing_weight

            # === PASS 1: Assemble VIDEO-ONLY (with progress) ===
            cmd_pass1 = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", str(self.concat_file),
                "-c:v", "libx264",
                "-preset", "fast",
                "-movflags", "+faststart",
                "-progress", "pipe:1",
                str(self.video_only),
            ]
            self._run_ffmpeg_progress(cmd_pass1, expected_duration_concat,
                                      base_offset=assembly_base,
                                      span_steps=pass1_span,
                                      total_steps=total_weighted_steps)

            # Get ACTUAL duration from the rendered video-only file
            actual_duration = self.get_file_duration(self.video_only)
            if not actual_duration:
                # As a last resort, use the concat estimate
                actual_duration = expected_duration_concat
            self._log(f"[Slideshow] Video-only duration: {actual_duration:.2f}s")

            # Soundtrack handling
            soundtrack_path = self.config.get("soundtrack", "")
            has_soundtrack = bool(soundtrack_path) and Path(soundtrack_path).exists()

            # === PASS 2: Mux soundtrack EXACTLY to video length (no fade), with progress ===
            if has_soundtrack:
                # Loop audio and trim output to EXACT video length with -t (no -shortest)
                cmd_pass2 = [
                    "ffmpeg", "-y",
                    "-i", str(self.video_only),
                    "-stream_loop", "-1", "-i", str(soundtrack_path),
                    "-map", "0:v", "-map", "1:a",
                    "-t", f"{actual_duration:.3f}",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-movflags", "+faststart",
                    "-progress", "pipe:1",
                    str(self.mux_no_fade),
                ]
                self._run_ffmpeg_progress(cmd_pass2, actual_duration,
                                          base_offset=assembly_base + pass1_span,
                                          span_steps=pass2_span,
                                          total_steps=total_weighted_steps)
            else:
                # No soundtrack: still remux with progress so the bar moves
                cmd_pass2 = [
                    "ffmpeg", "-y",
                    "-i", str(self.video_only),
                    "-c", "copy",
                    "-movflags", "+faststart",
                    "-progress", "pipe:1",
                    str(self.mux_no_fade),
                ]
                self._run_ffmpeg_progress(cmd_pass2, actual_duration,
                                          base_offset=assembly_base + pass1_span,
                                          span_steps=pass2_span,
                                          total_steps=total_weighted_steps)

            # === PASS 3: Apply final 1s fade (only if soundtrack exists & long enough), with progress ===
            if has_soundtrack and actual_duration and actual_duration > 1.0:
                fade_filter = f"afade=out:st={actual_duration - 1:.2f}:d=1"
                cmd_pass3 = [
                    "ffmpeg", "-y",
                    "-i", str(self.mux_no_fade),
                    "-c:v", "copy",
                    "-af", fade_filter,
                    "-movflags", "+faststart",
                    "-progress", "pipe:1",
                    str(output_path),
                ]
                # For pass3 progress, reuse the same duration for scaling
                self._run_ffmpeg_progress(cmd_pass3, actual_duration,
                                          base_offset=assembly_base + pass1_span + pass2_span,
                                          span_steps=pass3_span,
                                          total_steps=total_weighted_steps)
            else:
                # Copy as-is to final (quick), but keep progress consistent
                shutil.copyfile(self.mux_no_fade, output_path)
                if self.progress_callback:
                    self.progress_callback(total_weighted_steps, total_weighted_steps)

            # Final tick
            if self.progress_callback:
                self.progress_callback(total_weighted_steps, total_weighted_steps)

            self._log(f"[Slideshow] Slideshow complete: {output_path}")

        finally:
            if self.working_dir.exists():
                self._log(f"[Slideshow] Cleaning working dir: {self.working_dir}")
                try:
                    shutil.rmtree(self.working_dir)
                except Exception as e:
                    self._log(f"[Slideshow] WARNING: failed to clean working dir: {e}")
