from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageOps
from slideshow.config import cfg, DEFAULT_CONFIG
from slideshow.slides.slide_item import SlideItem
from slideshow.transitions.utils import load_and_resize_image
from slideshow.transitions.ffmpeg_cache import FFmpegCache


class PhotoSlide(SlideItem):
    def __init__(self, path: Path, duration: float, fps: int = None, resolution: tuple = None, creation_date: float = None):
        resolution = resolution if resolution is not None else tuple(DEFAULT_CONFIG["resolution"])
        super().__init__(path, duration, resolution, creation_date)
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

        # Load image - use PIL for HEIC support, then convert to OpenCV format
        try:
            # Try PIL first (supports HEIC, JPEG, PNG, etc.)
            with Image.open(self.path) as pil_img:
                # Apply EXIF orientation correction (fixes upside-down/sideways images)
                pil_img = ImageOps.exif_transpose(pil_img)
                # Convert to RGB if needed
                if pil_img.mode != 'RGB':
                    pil_img = pil_img.convert('RGB')
                # Convert PIL image to OpenCV format (RGB -> BGR)
                img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            # Fallback to cv2.imread for compatibility
            img = cv2.imread(str(self.path))
            if img is None:
                raise RuntimeError(f"Cannot load image: {self.path}. Error: {e}")

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

        # --- Write CFR video using FFmpeg for proper metadata ---
        # Save the framed image as a temporary PNG
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            temp_png = Path(tmp_file.name)
        
        cv2.imwrite(str(temp_png), framed)
        
        # Use FFmpeg to create the video with proper duration metadata
        from slideshow.transitions.ffmpeg_paths import FFmpegPaths
        import subprocess
        
        total_frames = int(self.fps * self.duration)
        
        ffmpeg_cmd = [
            FFmpegPaths.ffmpeg(), "-y",
            "-loop", "1",
            "-i", str(temp_png),
            "-t", f"{self.duration:.3f}",
            "-r", str(self.fps),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(clip_path)
        ]
        
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        
        # Clean up temp file
        temp_png.unlink(missing_ok=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed for photo slide {self.path}:\n{result.stderr}")

        # Store result in cache for future use
        FFmpegCache.store_clip(self.path, cache_params, clip_path)

        if log_callback:
            log_callback(f"Photo slide rendered successfully: {clip_path} ({total_frames} frames @ {self.fps} fps)")

        return clip_path
    
    def rotate(self, degrees: int) -> bool:
        """
        Rotate this photo slide by the specified degrees and save.
        Overrides base class to provide photo rotation functionality.
        
        Args:
            degrees: Rotation angle (positive = counter-clockwise)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load the current image from disk
            img = Image.open(self.path)
            
            # Preserve EXIF data before any operations
            exif_data = img.info.get('exif', b'')
            
            # Apply EXIF orientation first to get the correct base orientation
            img = ImageOps.exif_transpose(img)
            
            # Rotate the image (PIL rotates counter-clockwise with positive angles)
            img_rotated = img.rotate(degrees, expand=True)
            
            # Save back to the same file, preserving EXIF data
            if exif_data:
                img_rotated.save(self.path, exif=exif_data)
            else:
                img_rotated.save(self.path)
            
            # Invalidate cached images since the source file changed
            self._to_image = None
            self._from_image = None
            self._is_portrait = None
            
            return True
            
        except Exception as e:
            return False
    
    def _load_preview_image(self) -> Image.Image:
        """Load the source photo image."""
        img = Image.open(self.path)
        # Apply EXIF orientation to get correct display
        img = ImageOps.exif_transpose(img)
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        return img
    
    def _check_orientation(self) -> bool:
        """Check if the photo is in portrait orientation by examining the image file."""
        try:
            with Image.open(self.path) as img:
                # Apply EXIF orientation to get correct dimensions
                img = ImageOps.exif_transpose(img)
                return img.height > img.width
        except Exception:
            # Fallback: assume landscape if we can't read the image
            return False

    def __repr__(self):
        return (f"{self.__class__.__name__}(path={self.path}, duration={self.duration}, "
                f"fps={self.fps}, resolution={self.resolution})")
