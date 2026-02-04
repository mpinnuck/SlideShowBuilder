from pathlib import Path
import subprocess
from slideshow.config import cfg, DEFAULT_CONFIG
from slideshow.slides.slide_item import SlideItem
from slideshow.transitions.ffmpeg_cache import FFmpegCache
from slideshow.transitions.ffmpeg_paths import FFmpegPaths


class VideoSlide(SlideItem):
    def __init__(self, path: Path, duration: float, fps: int = None, resolution: tuple = None, creation_date: float = None):
        resolution = resolution if resolution is not None else tuple(DEFAULT_CONFIG["resolution"])
        super().__init__(path, duration, resolution, creation_date)
        self.fps = fps if fps is not None else DEFAULT_CONFIG["fps"]

    def render(self, working_dir: Path, log_callback=None, progress_callback=None):
        working_dir.mkdir(parents=True, exist_ok=True)

        if log_callback:
            log_callback(f"[Slideshow] Rendering video slide: {self.path.name} "
                         f"(target={self.duration:.2f}s)")

        # Create cache key parameters for this specific rendering
        cache_params = {
            "operation": "video_slide_render",
            "duration": self.duration,
            "fps": self.fps,
            "resolution": self.resolution,
            "format": "mp4",
            "video_quality": cfg.get('video_quality', 'maximum')  # Include quality in cache key
        }
        
        # Check cache first
        cached_clip = FFmpegCache.get_cached_clip(self.path, cache_params)
        if cached_clip:
            if log_callback:
                log_callback(f"[FFmpegCache] Using cached video clip: {cached_clip.name}")
            
            # Create a unique output filename in working directory
            import hashlib
            param_hash = hashlib.md5(str(cache_params).encode()).hexdigest()[:8]
            clip_path = working_dir / f"{self.path.stem}_{param_hash}.mp4"
            self._rendered_clip = clip_path
            
            # Copy cached clip to working directory
            import shutil
            shutil.copy2(cached_clip, clip_path)
            return clip_path

        # Create a unique output filename based on parameters
        import hashlib
        param_hash = hashlib.md5(str(cache_params).encode()).hexdigest()[:8]
        clip_path = working_dir / f"{self.path.stem}_{param_hash}.mp4"
        self._rendered_clip = clip_path

        ffmpeg_cmd = [
            FFmpegPaths.ffmpeg(), "-y",
            "-i", str(self.path),
            "-vf", (
                f"fps={self.fps},"
                f"scale={self.resolution[0]}:{self.resolution[1]}:force_original_aspect_ratio=decrease,"
                f"pad={self.resolution[0]}:{self.resolution[1]}:(ow-iw)/2:(oh-ih)/2:black"
            ),
            "-t", f"{self.duration:.3f}",
            "-r", str(self.fps),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest",
            "-movflags", "+faststart",
            str(clip_path)
        ]

        if log_callback:
            log_callback(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")

        process = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg failed for {self.path}:\n{process.stderr}")

        # Store result in cache for future use
        FFmpegCache.store_clip(self.path, cache_params, clip_path)

        if log_callback:
            log_callback(f"Video slide rendered successfully: {clip_path}")

        return clip_path
    
    def _check_orientation(self) -> bool:
        """Check if the video is in portrait orientation by examining video metadata."""
        try:
            # Use ffprobe to get video dimensions
            cmd = [
                FFmpegPaths.ffprobe(), "-v", "quiet",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0",
                str(self.path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                dimensions = result.stdout.strip()
                if 'x' in dimensions:
                    width, height = map(int, dimensions.split('x'))
                    return height > width
            
        except Exception:
            pass
        
        # Fallback: assume landscape if we can't determine orientation
        return False

    def __repr__(self):
        return (f"{self.__class__.__name__}(path={self.path}, duration={self.duration}, "
                f"fps={self.fps}, resolution={self.resolution})")
