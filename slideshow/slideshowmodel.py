import datetime
from collections import Counter
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional

from slideshow.config import cfg
from slideshow.slides.photo_slide import PhotoSlide
from slideshow.slides.video_slide import VideoSlide
from slideshow.transitions import get_transition
from slideshow.transitions.utils import get_video_duration, add_soundtrack_with_fade
from slideshow.config import DEFAULT_CONFIG
from slideshow.transitions.transition_factory import TransitionFactory
from slideshow.transitions.intro_title import IntroTitle
from slideshow.transitions.ffmpeg_cache import FFmpegCache
from slideshow.transitions.ffmpeg_paths import FFmpegPaths
from slideshow.error_handling import ErrorHandler, safe_file_stat


class Slideshow:
    def __init__(self, config: dict, log_callback=None, progress_callback=None):
        # Initialize the Config singleton with the provided config
        cfg.update(config)
        self.config = config  # Keep for backward compatibility
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.cancel_check = None  # Callback to check if cancellation requested

        self.slides: List[PhotoSlide | VideoSlide] = []
        self.transitions: List[object] = []  # from get_transition()

        # Use config output folder instead of hardcoded path
        output_folder = Path(self.config.get("output_folder", "media/output"))
        self.working_dir = output_folder / "working"
        
        # Check if we should clean the working directory on startup
        keep_intermediate = self.config.get("keep_intermediate_frames", False)
        
        if self.working_dir.exists() and not keep_intermediate:
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
                ErrorHandler.log_warning(self._log, "Working directory cleanup", e)
        elif self.working_dir.exists():
            self._log(f"[Slideshow] Preserving existing working dir (keep_intermediate_frames enabled)")
        
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
            fps=int(self.config.get("fps", DEFAULT_CONFIG["fps"]))
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
    # Slide Cache Management
    # -------------------------------
    def _get_slide_cache_path(self) -> Path:
        """Get the path to the slide cache file for the current project."""
        # Create a unique cache file based on input folder and sort settings
        input_folder = self.config.get("input_folder", "")
        sort_key = f"{input_folder}_{self.config.get('sort_by_filename', False)}_{self.config.get('recurse_folders', False)}_{self.config.get('older_images_no_exif', False)}"
        cache_hash = hashlib.md5(sort_key.encode()).hexdigest()[:12]
        return self.working_dir / "ffmpeg_cache" / f"slide_order_{cache_hash}.json"
    
    def _save_slide_cache(self):
        """Save slide paths to cache for faster loading next time."""
        try:
            from slideshow.slides.multi_slide import MultiSlide
            
            cache_path = self._get_slide_cache_path()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save slide paths, types, and creation dates
            slide_data = []
            for slide in self.slides:
                if isinstance(slide, MultiSlide):
                    # Save MultiSlide with all component files
                    slide_data.append({
                        "path": str(slide.path),  # First image path
                        "type": "multi",
                        "duration": slide.duration,
                        "creation_date": slide.creation_date,
                        "media_files": [str(p) for p in slide.media_files]
                    })
                elif isinstance(slide, PhotoSlide):
                    slide_data.append({
                        "path": str(slide.path),
                        "type": "photo",
                        "duration": slide.duration,
                        "creation_date": slide.creation_date
                    })
                else:  # VideoSlide
                    slide_data.append({
                        "path": str(slide.path),
                        "type": "video",
                        "duration": slide.duration,
                        "creation_date": slide.creation_date
                    })
            
            with open(cache_path, 'w') as f:
                json.dump(slide_data, f, indent=2)
        except Exception as e:
            self._log(f"[Slideshow] Warning: Could not save slide cache: {e}")

    def _log_input_file_counts(self):
        """Log a breakdown of input file types from the loaded slides."""
        try:
            from slideshow.slides.multi_slide import MultiSlide
            files = []
            for slide in self.slides:
                if isinstance(slide, MultiSlide):
                    files.extend(slide.media_files)
                else:
                    files.append(slide.path)
            counts = Counter(f.suffix.lower() for f in files)
            total = sum(counts.values())
            parts = ", ".join(f"{count} {ext.lstrip('.').upper()}" for ext, count in sorted(counts.items()) if count > 0)
            self._log(f"[Slideshow] Input files: {parts} = {total} total")
        except Exception as e:
            self._log(f"[Slideshow] Could not count input file types: {e}")

    def _load_slide_cache(self) -> bool:
        """Try to load slides from cache. Returns True if successful."""
        try:
            cache_path = self._get_slide_cache_path()
            
            if not cache_path.exists():
                return False
            
            with open(cache_path, 'r') as f:
                slide_data = json.load(f)
            
            # Recreate slides from cache, skipping any with missing files
            fps = self.config.get("fps", DEFAULT_CONFIG["fps"])
            resolution = tuple(self.config.get("resolution", DEFAULT_CONFIG["resolution"]))
            skipped = 0
            total_items = len(slide_data)
            
            for idx, item in enumerate(slide_data):
                path = Path(item["path"])
                
                # Report progress every 10% of items
                if self.progress_callback and total_items > 0:
                    if idx % max(1, total_items // 10) == 0 or idx == total_items - 1:
                        self.progress_callback(idx + 1, total_items, f"Loading {idx + 1}/{total_items} slides from cache...")
                
                # Check if files exist
                skip_this_slide = False
                if item["type"] == "multi":
                    # For MultiSlide, check all component files
                    media_files = [Path(p) for p in item.get("media_files", [])]
                    if not all(p.exists() for p in media_files):
                        skip_this_slide = True
                else:
                    # For PhotoSlide/VideoSlide, check the main file
                    if not path.exists():
                        skip_this_slide = True
                
                if skip_this_slide:
                    skipped += 1
                    continue
                
                # Validate type matches file extension (catch cache corruption)
                ext = path.suffix.lower()
                cached_type = item["type"]
                if cached_type == "photo" and ext not in ['.jpg', '.jpeg', '.png', '.heic', '.heif']:
                    skipped += 1
                    continue
                if cached_type == "video" and ext not in ['.mp4', '.mov']:
                    skipped += 1
                    continue
                
                # Create the slide
                duration = item["duration"]
                creation_date = item.get("creation_date")
                
                if item["type"] == "photo":
                    self.slides.append(PhotoSlide(path, duration, fps=fps, resolution=resolution, creation_date=creation_date))
                elif item["type"] == "video":
                    self.slides.append(VideoSlide(path, duration, fps=fps, resolution=resolution, creation_date=creation_date))
                elif item["type"] == "multi":
                    # Recreate MultiSlide from cached data
                    from slideshow.slides.multi_slide import MultiSlide
                    media_files = [Path(p) for p in item.get("media_files", [])]
                    if media_files:
                        multi_slide = MultiSlide(
                            media_files=media_files,
                            duration=duration,
                            resolution=resolution,
                            fps=fps,
                            creation_date=creation_date
                        )
                        self.slides.append(multi_slide)
            
            if skipped > 0:
                self._log(f"[Slideshow] Loaded {len(self.slides)} slides from cache ({skipped} deleted files skipped)")
            else:
                self._log(f"[Slideshow] Loaded {len(self.slides)} slides from cache")
            
            return True
            
        except Exception as e:
            self._log(f"[Slideshow] Could not load slide cache: {e}")
            return False

    # -------------------------------
    # FFprobe utilities
    # -------------------------------
    def _extract_video_metadata_parallel(self, video_files: List[Path], files_processed: List[int], total_files: int) -> dict:
        """Extract creation time metadata from video files in parallel using ffprobe."""
        def extract_single_video_metadata(video_path: Path) -> tuple[Path, Optional[float]]:
            """Extract metadata from a single video file."""
            try:
                result = subprocess.run([
                    'ffprobe', '-v', 'quiet', '-print_format', 'json',
                    '-show_format', str(video_path)
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    metadata = json.loads(result.stdout)
                    creation_time = metadata.get('format', {}).get('tags', {}).get('creation_time')
                    if creation_time:
                        # Handle various ISO 8601 formats
                        for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S']:
                            try:
                                dt = datetime.datetime.strptime(creation_time.replace('+00:00', 'Z'), fmt)
                                return video_path, dt.timestamp()
                            except ValueError:
                                continue
                return video_path, None
            except Exception:
                return video_path, None
        
        video_metadata = {}
        if not video_files:
            return video_metadata
        
        # Process videos in parallel with limited concurrency to avoid overwhelming the system
        max_workers = min(4, len(video_files))  # Limit to 4 concurrent ffprobe processes
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all video metadata extraction tasks
            future_to_path = {executor.submit(extract_single_video_metadata, path): path for path in video_files}
            
            # Collect results as they complete
            for future in as_completed(future_to_path):
                path, timestamp = future.result()
                if timestamp is not None:
                    video_metadata[path] = timestamp
                
                # Update progress
                files_processed[0] += 1
                if files_processed[0] % 10 == 0 or files_processed[0] == total_files:
                    if self.progress_callback:
                        self.progress_callback(files_processed[0], total_files, f"Reading dates {files_processed[0]}/{total_files}...")
                    self._log(f"[Slideshow] Reading dates {files_processed[0]}/{total_files}...\r")
        
        return video_metadata

    def _extract_video_metadata_parallel(self, video_files: List[Path], files_processed: List[int], total_files: int) -> dict:
        """Extract creation time metadata from video files in parallel using ffprobe."""
        def extract_single_video_metadata(video_path: Path) -> tuple[Path, Optional[float]]:
            """Extract metadata from a single video file."""
            try:
                result = subprocess.run([
                    'ffprobe', '-v', 'quiet', '-print_format', 'json',
                    '-show_format', str(video_path)
                ], capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    metadata = json.loads(result.stdout)
                    creation_time = metadata.get('format', {}).get('tags', {}).get('creation_time')
                    if creation_time:
                        # Handle various ISO 8601 formats
                        for fmt in ['%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S']:
                            try:
                                dt = datetime.datetime.strptime(creation_time.replace('+00:00', 'Z'), fmt)
                                return video_path, dt.timestamp()
                            except ValueError:
                                continue
                return video_path, None
            except Exception:
                return video_path, None
        
        video_metadata = {}
        if not video_files:
            return video_metadata
        
        # Process videos in parallel with limited concurrency to avoid overwhelming the system
        max_workers = min(4, len(video_files))  # Limit to 4 concurrent ffprobe processes
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all video metadata extraction tasks
            future_to_path = {executor.submit(extract_single_video_metadata, path): path for path in video_files}
            
            # Collect results as they complete
            for future in as_completed(future_to_path):
                path, timestamp = future.result()
                if timestamp is not None:
                    video_metadata[path] = timestamp
                
                # Update progress
                files_processed[0] += 1
                if files_processed[0] % 10 == 0 or files_processed[0] == total_files:
                    if self.progress_callback:
                        self.progress_callback(files_processed[0], total_files, f"Reading dates {files_processed[0]}/{total_files}...")
                    self._log(f"[Slideshow] Reading dates {files_processed[0]}/{total_files}...\r")
        
        return video_metadata


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

        # Try to load from cache first
        cache_loaded = self._load_slide_cache()
        if cache_loaded:
            self._log(f"[Slideshow] Loaded {len(self.slides)} slides from cache")
            # Final progress update (must come before _log_input_file_counts, as the progress
            # message uses \r which deletes the previous log line)
            if self.progress_callback:
                total = len(self.slides)
                self.progress_callback(total, total, f"Loaded {total} slides from cache")
            self._log_input_file_counts()
            return
        
        # If cache failed to load, rebuild from scratch
        self.slides = []  # Clear any partial cache data

        # Get multislide frequency setting
        multislide_frequency = self.config.get("multislide_frequency", 0)
        
        # Log that we're starting to load files
        recurse_folders = self.config.get("recurse_folders", False)
        if recurse_folders:
            self._log(f"[Slideshow] Reading files recursively from {input_folder}...")
        else:
            self._log(f"[Slideshow] Reading files from {input_folder}...")
        
        # Get all files (recursive or not)
        if recurse_folders:
            all_files_list = [f for f in input_folder.rglob("*") if f.is_file()]
        else:
            all_files_list = [f for f in input_folder.glob("*") if f.is_file()]
        
        self._log(f"[Slideshow] Found {len(all_files_list)} total files")
        
        # Filter to only supported media files BEFORE sorting (more efficient)
        # Photos: JPEG, PNG, HEIC/HEIF
        # Videos: MP4, MOV
        supported_extensions = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.mp4', '.mov'}
        ignored_names = {'.ds_store', 'thumbs.db', 'desktop.ini'}
        all_files_list = [
            f for f in all_files_list 
            if f.suffix.lower() in supported_extensions
            and f.name.lower() not in ignored_names
        ]
        total_files = len(all_files_list)

        # Report progress for the scanning phase
        if self.progress_callback:
            self.progress_callback(0, total_files, f"Scanning {total_files} media files...")
        
        # Check if we should sort by filename instead of date
        sort_by_filename = self.config.get("sort_by_filename", False)
        timestamp_cache = {}
        
        if sort_by_filename:
            # Sort alphabetically by filename (no EXIF extraction needed)
            self._log(f"[Slideshow] Sorting {total_files} files by filename...")
            all_files = sorted(all_files_list, key=lambda p: p.name.lower())
            self._log(f"[Slideshow] Sorted {total_files} files by filename")
        else:
            # Sort with cached timestamps (progress shown during metadata extraction)
            self._log(f"[Slideshow] Sorting {total_files} files by date taken...")
            files_processed = [0]  # Use list to allow modification in nested function
            
            # Separate video files for parallel processing
            video_extensions = {'.mp4', '.mov'}
            video_files = [f for f in all_files_list if f.suffix.lower() in video_extensions]
            photo_files = [f for f in all_files_list if f.suffix.lower() not in video_extensions]
            
            self._log(f"[Slideshow] Processing {len(video_files)} videos in parallel and {len(photo_files)} photos...")
            
            # Process all video files in parallel first
            video_metadata = self._extract_video_metadata_parallel(video_files, files_processed, len(video_files))
            
            # Process photos sequentially (EXIF is usually fast)
            def get_photo_timestamp(path: Path) -> float:
                """Get timestamp for photo files: EXIF date or creation/modification time."""
                ext = path.suffix.lower()
                
                # Default fallback: try creation time first (st_birthtime on macOS), then modification time
                timestamp = safe_file_stat(path, self._log)
                
                # For photos, try to get EXIF date
                if ext in ('.jpg', '.jpeg', '.heic', '.heif'):
                    try:
                        from PIL import Image
                        from PIL.ExifTags import TAGS
                        
                        with Image.open(path) as img:
                            exif = img._getexif()
                            if exif:
                                for tag_id, value in exif.items():
                                    tag_name = TAGS.get(tag_id, tag_id)
                                    if tag_name == 'DateTimeOriginal':
                                        dt = datetime.datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                                        timestamp = dt.timestamp()
                                        break
                    except Exception as e:
                        ErrorHandler.log_warning(self._log, f"EXIF extraction from {path.name}", e)
                        # Keep the file system timestamp
                
                return timestamp
            
            # Build complete timestamp cache
            timestamp_cache = {}
            
            # Add video metadata (already processed in parallel)
            timestamp_cache.update(video_metadata)
            
            # Add photo timestamps (process sequentially)
            for photo_path in photo_files:
                    # Get timestamp for this photo with proper error handling
                
                # Update progress
                if files_processed[0] % 50 == 0 or files_processed[0] == total_files:
                    if self.progress_callback:
                        self.progress_callback(files_processed[0], total_files, f"Reading dates {files_processed[0]}/{total_files}...")
                    self._log(f"[Slideshow] Reading dates {files_processed[0]}/{total_files}...\\r")
            
            # For files without specific metadata, use file system timestamps
            for file_path in all_files_list:
                if file_path not in timestamp_cache:
                    timestamp_cache[file_path] = safe_file_stat(file_path, self._log)
            
            # Sort using the complete timestamp cache
            all_files = sorted(all_files_list, key=lambda p: timestamp_cache.get(p, 0.0))
            self._log(f"[Slideshow] Sorted {total_files} files by date taken")
        
        # Use the filtered and sorted files
        media_files = all_files
        
        # Save slide cache after sorting for next time
        # (Will be saved again after slides are created)
        
        skip_until = 0  # Track files consumed by MultiSlides
        
        # Counters for import summary
        photo_count = 0
        video_count = 0
        multislide_count = 0
        
        # Log initial message
        total_files = len(media_files)
        self._log(f"[Slideshow] Loading {total_files} files...")
        
        # Report initial progress
        if self.progress_callback:
            self.progress_callback(0, total_files, f"Loading {total_files} files...")
        
        for i, path in enumerate(media_files):
            # Skip files that were consumed by previous MultiSlides
            if i < skip_until:
                continue
            
            # Update progress callback (every file)
            if self.progress_callback:
                self.progress_callback(i + 1, total_files, f"Loading {i + 1}/{total_files} files...")
                
            ext = path.suffix.lower()
            
            # Get timestamp for this file from cache
            timestamp = timestamp_cache.get(path)
            if timestamp is None:
                try:
                    timestamp = path.stat().st_mtime
                except OSError:
                    timestamp = 0.0
            
            # Check if we should create a multislide at this position
            # Trigger: Every 5 slides (e.g., at indices 5, 10, 15, ...)
            if (multislide_frequency > 0 and 
                len(self.slides) > 0 and  # Have at least one slide already
                len(self.slides) % multislide_frequency == 0 and  # Every Nth slide
                i + 2 < len(media_files)):  # Have enough files left
                
                # Create MultiSlide from 3 consecutive files (can be any mix of photos and videos)
                next_files = media_files[i:i+3]
                resolution = tuple(self.config.get("resolution", DEFAULT_CONFIG["resolution"]))
                fps = self.config.get("fps", DEFAULT_CONFIG["fps"])
                
                from slideshow.slides.multi_slide import MultiSlide
                multi_slide = MultiSlide(
                    media_files=next_files,
                    duration=self.config["photo_duration"],
                    resolution=resolution,
                    fps=fps,
                    creation_date=timestamp
                )
                self.slides.append(multi_slide)
                
                # Count photos and videos consumed by the multislide
                photos_in_multi = sum(1 for f in next_files if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".heic", ".heif"))
                videos_in_multi = sum(1 for f in next_files if f.suffix.lower() in (".mp4", ".mov"))
                photo_count += photos_in_multi
                video_count += videos_in_multi
                multislide_count += 1
                
                # Skip the files consumed by the multislide
                skip_until = i + multi_slide.get_slide_count()
                continue
            
            # Process single file normally
            if ext in (".jpg", ".jpeg", ".png", ".heic", ".heif"):
                resolution = tuple(self.config.get("resolution", DEFAULT_CONFIG["resolution"]))
                fps = self.config.get("fps", DEFAULT_CONFIG["fps"])
                
                self.slides.append(PhotoSlide(path, self.config["photo_duration"], fps=fps, resolution=resolution, creation_date=timestamp))
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
                    self.slides.append(VideoSlide(path, actual_duration, fps=fps, resolution=resolution, creation_date=timestamp))
                    video_count += 1
                else:
                    # Force last video to play full duration for a natural, complete ending
                    # Other videos are limited to video_duration_setting to maintain consistent pacing
                    is_last_file = (i == len(media_files) - 1)
                    final_duration = actual_duration if is_last_file else min(video_duration_setting, actual_duration)
                    
                    self.slides.append(VideoSlide(path, final_duration, fps=fps, resolution=resolution, creation_date=timestamp))
                    video_count += 1
            
            # Show progress every 10 files
            if (i + 1) % 10 == 0 or (i + 1) == total_files:
                self._log(f"[Slideshow] Loaded {i + 1}/{total_files} files...\r")
        
        # Log import summary
        total_input_files = len(media_files)
        total_slides = len(self.slides)
        single_photo_slides = (photo_count - (multislide_count * 3))  # Photos not in MultiSlides
        
        self._log(f"[Slideshow] Importing {total_input_files} files → {total_slides} slides: {single_photo_slides} photo, {video_count} video, {multislide_count} multi")
        self._log_input_file_counts()

        # Save slide list to cache for faster loading next time
        self._save_slide_cache()
        
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
        # Drain stderr in a background thread to prevent pipe buffer deadlock
        stderr_lines = []
        stderr_thread = threading.Thread(
            target=lambda: stderr_lines.extend(proc.stderr.readlines()),
            daemon=True
        )
        stderr_thread.start()
        last_report = -1
        try:
            while True:
                # Check for cancellation
                if self.cancel_check and self.cancel_check():
                    self._log("[Slideshow] Cancelling FFmpeg process...")
                    proc.terminate()  # Send SIGTERM
                    try:
                        proc.wait(timeout=2)  # Wait up to 2 seconds for graceful termination
                    except subprocess.TimeoutExpired:
                        proc.kill()  # Force kill if it doesn't terminate
                        proc.wait()
                    raise RuntimeError("Export cancelled by user")
                
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
        finally:
            # Ensure process is cleaned up
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    proc.kill()

        proc.wait()
        stderr_thread.join(timeout=5)
        if proc.returncode != 0:
            stderr_out = "".join(stderr_lines)
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



            # --- Render slides (parallel — each slide is independent) ---
            self._log("")
            completed = 0
            # VideoToolbox corrupts output with too many concurrent sessions; limit to 4
            hw_accel = cfg.get('hardware_acceleration', False)
            max_workers = 4 if hw_accel else 6

            def _render_slide(slide):
                try:
                    slide.render(self.working_dir)
                    return slide
                except Exception as e:
                    # Include slide information in error for debugging
                    raise RuntimeError(f"Failed to render slide {slide.path.name}: {str(e)}") from e

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_render_slide, s): s for s in self.slides}
                for future in as_completed(futures):
                    if self.cancel_check and self.cancel_check():
                        executor.shutdown(wait=False, cancel_futures=True)
                        self._log("[Slideshow] Cancelling export...")
                        raise RuntimeError("Export cancelled by user")
                    try:
                        future.result()  # re-raise any exception
                    except Exception as e:
                        # Get the slide that failed from the futures mapping
                        failed_slide = futures[future]
                        self._log(f"[Slideshow] Failed rendering slide {completed+1}/{total_items}: {failed_slide.path.name}")
                        raise
                    completed += 1
                    self._log(f"[Slideshow] Rendering slides ({completed}/{total_items})...\r")
                    if self.progress_callback:
                        self.progress_callback(completed, total_weighted_steps)

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


            # --- Render transitions (parallel — each is independent, slides are read-only) ---
            transition_clips = [None] * (total_items - 1)  # Pre-allocate ordered list
            completed_trans = 0

            def _render_transition(i):
                trans_out = self.working_dir / f"trans_{i:03}.mp4"
                self.transition.render(i, self.slides, trans_out)
                return i, trans_out

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(_render_transition, i): i for i in range(total_items - 1)}
                for future in as_completed(futures):
                    if self.cancel_check and self.cancel_check():
                        executor.shutdown(wait=False, cancel_futures=True)
                        self._log("[Slideshow] Cancelling export...")
                        raise RuntimeError("Export cancelled by user")
                    idx, trans_out = future.result()
                    transition_clips[idx] = trans_out
                    completed_trans += 1
                    self._log(f"[Slideshow] Rendering transitions ({completed_trans}/{total_transitions})...\r")
                    if self.progress_callback:
                        self.progress_callback(total_items + completed_trans, total_weighted_steps)

            # --- Write concat file ---
            # Check for cancellation before assembly
            if self.cancel_check and self.cancel_check():
                self._log("[Slideshow] Cancelling export...")
                raise RuntimeError("Export cancelled by user")
            
            self._log("[Slideshow] Building concat file...")
            
            with self.concat_file.open("w") as f:
                # Prepend intro clip if it exists
                if self._intro_clip:
                    f.write(f"file '{self._intro_clip.resolve()}'\n")

                for i, slide in enumerate(self.slides):
                    slide_clip = slide.get_rendered_clip()
                    f.write(f"file '{slide_clip.resolve()}'\n")
                    
                    # Insert transition after every slide except last
                    if i < len(transition_clips):
                        trans_clip = transition_clips[i]
                        f.write(f"file '{trans_clip.resolve()}'\n")

            # --- Assemble & mux ---
            expected_duration = self.get_estimated_duration()
            hours = int(expected_duration // 3600)
            minutes = int((expected_duration % 3600) // 60)
            seconds = expected_duration % 60
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:05.2f}"
            self._log(f"[Slideshow] Estimated duration for progress scaling: {duration_str}")

            # --- Pass 1: Assemble video-only ---
            self._log(f"[Slideshow] Assembling video-only...")
            cmd_pass1 = [
                FFmpegPaths.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat", "-safe", "0", "-i", str(self.concat_file),
                "-c", "copy",  # Stream copy - no re-encode! Clips already at correct quality
                "-progress", "pipe:1",
                str(self.video_only),
            ]
            self._run_ffmpeg_progress(cmd_pass1,
                                    expected_duration or 1.0,
                                    base_offset=processing_weight,
                                    span_steps=int(assembly_weight * 0.9),
                                    total_steps=total_weighted_steps)

            actual_duration = self.get_file_duration(self.video_only)
            if actual_duration:
                hours = int(actual_duration // 3600)
                minutes = int((actual_duration % 3600) // 60)
                seconds = actual_duration % 60
                duration_str = f"{hours:02d}:{minutes:02d}:{seconds:05.2f}"
                self._log(f"[Slideshow] Video-only duration: {duration_str}")
            else:
                self._log("[Slideshow] WARNING: could not determine duration — using estimate")

            # --- Pass 2: Mux soundtrack (if present) using shared utility ---
            soundtrack_path = self.config.get("soundtrack", "")
            has_soundtrack = bool(soundtrack_path) and Path(soundtrack_path).exists()

            self._log("[Slideshow] Muxing soundtrack..." if has_soundtrack else "[Slideshow] Finalizing video (no soundtrack)...")
            
            # Use shared utility function for soundtrack muxing
            success = add_soundtrack_with_fade(
                video_only_path=self.video_only,
                output_path=output_path,
                soundtrack_path=soundtrack_path if has_soundtrack else None,
                duration=actual_duration or 1.0,
                progress_callback=self._log
            )
            
            if not success:
                raise RuntimeError("Failed to add soundtrack to video")
            
            # Update progress to completion
            if self.progress_callback:
                self.progress_callback(total_weighted_steps, total_weighted_steps)

            self._log(f"[Slideshow] Slideshow complete: {output_path}")
            
            # Display cache statistics
            # cache_stats = FFmpegCache.get_cache_stats()
            # if cache_stats.get("enabled", False):
            #     hit_rate = cache_stats.get("hit_rate_percent", 0)
            #     total_requests = cache_stats.get("total_requests", 0)
            #     
            #     if total_requests > 0:
            #         self._log(f"[FFmpegCache] Cache stats: {cache_stats['total_entries']} entries "
            #                  f"({cache_stats['clip_count']} clips, {cache_stats['frame_count']} frames), "
            #                  f"{cache_stats['total_size_mb']:.1f} MB")
            #         self._log(f"[FFmpegCache] Performance: {cache_stats['cache_hits']} hits, "
            #                  f"{cache_stats['cache_misses']} misses, {hit_rate}% hit rate")
            #     else:
            #         self._log(f"[FFmpegCache] Cache stats: {cache_stats['total_entries']} entries "
            #                  f"({cache_stats['clip_count']} clips, {cache_stats['frame_count']} frames), "
            #                  f"{cache_stats['total_size_mb']:.1f} MB (no usage data yet)")
            
            # Clean up working directory on successful completion only
            keep_intermediate = self.config.get("keep_intermediate_frames", False)
            
            if self.working_dir.exists() and not keep_intermediate:
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
            # elif self.working_dir.exists():
            #     self._log(f"[Slideshow] Preserving working dir (keep_intermediate_frames enabled)")

        except Exception:
            # On error, preserve working directory for debugging
            # This allows users to inspect temp files and see what went wrong
            raise
    
    # -------------------------------
    # Cache Management
    # -------------------------------
    def get_cache_stats(self) -> dict:
        """Get FFmpeg cache statistics."""
        return FFmpegCache.get_cache_stats()
    
    def get_cache_dir(self) -> Path:
        """Get the cache directory path."""
        return self.working_dir / "ffmpeg_cache"
    
    def _clear_slide_cache(self):
        """Clear the slide order cache file."""
        try:
            cache_path = self._get_slide_cache_path()
            if cache_path.exists():
                cache_path.unlink()
                self._log(f"[Cache] Slide order cache cleared: {cache_path.name}")
        except Exception as e:
            self._log(f"[Cache] Error clearing slide cache: {e}")
    
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

