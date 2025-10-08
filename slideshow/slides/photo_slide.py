from pathlib import Path
import cv2
from PIL import Image
from slideshow.config import cfg, DEFAULT_CONFIG
from slideshow.slides.slide_item import SlideItem
from slideshow.transitions.utils import load_and_resize_image
from slideshow.transitions.ffmpeg_cache import FFmpegCache


class PhotoSlide(SlideItem):
    def __init__(self, path: Path, duration: float, fps: int = None, resolution: tuple = None):
        resolution = resolution if resolution is not None else tuple(DEFAULT_CONFIG["resolution"])
        super().__init__(path, duration, resolution)
        self.fps = fps if fps is not None else DEFAULT_CONFIG["fps"]

    def render(self, working_dir: Path, log_callback=None, progress_callback=None):
        """Render the photo slide into a CFR (constant frame rate) video clip."""
        working_dir.mkdir(parents=True, exist_ok=True)
        
        if log_callback:
            log_callback(f"[Slideshow] Rendering photo: {self.path.name} ({self.duration:.2f}s, {self.fps} fps)")

        # Create cache key parameters for this specific rendering
        cache_params = {
            "operation": "photo_slide_render",
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
                log_callback(f"[FFmpegCache] Using cached photo clip: {cached_clip.name}")
            
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

        img = cv2.imread(str(self.path))
        if img is None:
            raise RuntimeError(f"Cannot load image: {self.path}")

        h, w = img.shape[:2]
        target_w, target_h = self.resolution

        if log_callback:
            log_callback(f"Rendering photo slide: {self.path} -> {clip_path}\n"
                         f"Original size: {w}x{h}, Target: {target_w}x{target_h}")

        # --- Resize and pad ---
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(img, (new_w, new_h))

        top = (target_h - new_h) // 2
        bottom = target_h - new_h - top
        left = (target_w - new_w) // 2
        right = target_w - new_w - left
        framed = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(0, 0, 0))

        # --- Write CFR video ---
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(str(clip_path), fourcc, self.fps, (target_w, target_h))
        total_frames = int(self.fps * self.duration)

        for i in range(total_frames):
            out.write(framed)
            if progress_callback and (i % max(total_frames // 10, 1) == 0):
                progress_callback(i / total_frames)

        out.release()

        # Store result in cache for future use
        FFmpegCache.store_clip(self.path, cache_params, clip_path)

        if log_callback:
            log_callback(f"Photo slide rendered successfully: {clip_path} ({total_frames} frames @ {self.fps} fps)")

        return clip_path
    
    def _check_orientation(self) -> bool:
        """Check if the photo is in portrait orientation by examining the image file."""
        try:
            with Image.open(self.path) as img:
                return img.height > img.width
        except Exception:
            # Fallback: assume landscape if we can't read the image
            return False

    def __repr__(self):
        return (f"{self.__class__.__name__}(path={self.path}, duration={self.duration}, "
                f"fps={self.fps}, resolution={self.resolution})")
