#!/usr/bin/env python3
"""
multi_slide.py
--------------
A slide that composites multiple input images into a single slide with 70/30 layout.
"""

from pathlib import Path
from PIL import Image, ImageOps
import tempfile
import subprocess
import shutil

from slideshow.config import cfg
from slideshow.slides.slide_item import SlideItem
from slideshow.transitions.ffmpeg_cache import FFmpegCache
from slideshow.transitions.ffmpeg_paths import FFmpegPaths
from slideshow.transitions.utils import get_video_duration


class MultiSlide(SlideItem):
    def __init__(self, media_files, duration: float, resolution=(1920, 1080), fps=30, creation_date: float = None):
        """
        Create a MultiSlide from a list of media files (exactly 3).
        
        Args:
            media_files: List of exactly 3 media file paths to composite
            duration: Duration for the slide
            resolution: Output resolution
            fps: Frame rate for video rendering
            creation_date: Creation timestamp of the first image
        """
        # Initialize super class with the first image path
        super().__init__(media_files[0], duration, resolution, creation_date)
        
        self.media_files = media_files
        self.fps = fps
        self.composite_image = None
        self.slide_count = len(media_files)  # Should be 3
        self.selected_component = 0  # Default to main image (component 0)
        
    def get_slide_count(self):
        """Return the number of slides consumed by this MultiSlide."""
        return self.slide_count
    
    def select_component(self, component_index: int) -> bool:
        """
        Select which component image to operate on (for rotation, etc.).
        
        Args:
            component_index: Index of the component to select (0-2)
            
        Returns:
            True if valid index, False otherwise
        """
        if 0 <= component_index < len(self.media_files):
            self.selected_component = component_index
            return True
        return False
    
    def get_selected_component(self) -> int:
        """Get the currently selected component index."""
        return self.selected_component
    
    def rotate(self, degrees: int) -> bool:
        """
        Rotate the currently selected component image of this MultiSlide.
        Overrides base class to provide rotation for the selected image.
        Use select_component() to choose which image to rotate.
        
        Args:
            degrees: Rotation angle (positive = counter-clockwise)
            
        Returns:
            True if successful, False otherwise
        """
        return self.rotate_component(self.selected_component, degrees)
    
    def rotate_component(self, component_index: int, degrees: int) -> bool:
        """
        Rotate one of the component images in this MultiSlide.
        
        Args:
            component_index: Index of the image to rotate (0-2)
            degrees: Rotation angle (positive = counter-clockwise)
            
        Returns:
            True if successful, False otherwise
        """
        if component_index < 0 or component_index >= len(self.media_files):
            return False
        
        image_path = self.media_files[component_index]
        
        try:
            # Load the image from disk
            img = Image.open(image_path)
            
            # Preserve EXIF data
            exif_data = img.info.get('exif', b'')
            
            # Apply EXIF orientation first
            img = ImageOps.exif_transpose(img)
            
            # Rotate the image
            img_rotated = img.rotate(degrees, expand=True)
            
            # Save back to the same file
            if exif_data:
                img_rotated.save(image_path, exif=exif_data)
            else:
                img_rotated.save(image_path)
            
            # Invalidate composite cache since source changed
            self.composite_image = None
            self._to_image = None
            self._from_image = None
            self._is_portrait = None
            
            return True
            
        except Exception as e:
            return False
    
    def _check_orientation(self) -> bool:
        """
        MultiSlide orientation is determined by the main image (first slide).
        """
        try:
            if len(self.media_files) > 0:
                main_file = self.media_files[0]
                if main_file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.heic']:
                    with Image.open(main_file) as img:
                        # Apply EXIF orientation to get correct dimensions
                        img = ImageOps.exif_transpose(img)
                        return img.height > img.width
                elif main_file.suffix.lower() in ['.mp4', '.mov']:
                    # Use ffprobe for video files
                    cmd = [
                        FFmpegPaths.ffprobe(), "-v", "quiet",
                        "-select_streams", "v:0", 
                        "-show_entries", "stream=width,height",
                        "-of", "csv=s=x:p=0",
                        str(main_file)
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0 and result.stdout.strip():
                        dimensions = result.stdout.strip()
                        if 'x' in dimensions:
                            width, height = map(int, dimensions.split('x'))
                            return height > width
        except Exception:
            pass
        
        # Fallback: assume landscape
        return False
        
    def _create_composite(self):
        """Create the composite image from the provided media files (exactly 3)."""
        # Load the 3 images from our media_files list
        images = []
        for j in range(len(self.media_files)):
            file_path = self.media_files[j]
            # Only load image files
            if file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.heic']:
                img = Image.open(file_path)
                # Apply EXIF orientation to display correctly
                img = ImageOps.exif_transpose(img)
                # Convert to RGB if needed
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                images.append(img)
        
        if len(images) < 3:
            raise ValueError("MultiSlide requires at least 3 image files")
            
        # Get dimensions
        canvas_width, canvas_height = self.resolution
        
        # Create composite with black background
        composite = Image.new('RGB', (canvas_width, canvas_height), (0, 0, 0))
        
        # Layout: 70% main image, 30% preview area (split vertically)
        main_width = int(canvas_width * 0.7)
        preview_width = canvas_width - main_width
        preview_height = canvas_height // 2
        
        # Main image (left 70%)
        main_img = self._fit_image_to_area(images[0], (main_width, canvas_height))
        composite.paste(main_img, (0, 0))
        
        # Top preview (right 30%, top 50%)
        preview1_img = self._fit_image_to_area(images[1], (preview_width, preview_height))
        composite.paste(preview1_img, (main_width, 0))
        
        # Bottom preview (right 30%, bottom 50%)
        preview2_img = self._fit_image_to_area(images[2], (preview_width, preview_height))
        composite.paste(preview2_img, (main_width, preview_height))
        
        return composite
    
    def _fit_image_to_area(self, image, target_size, preserve_aspect=True):
        """
        Fit an image to its target area with proper portrait/landscape handling.
        
        For portrait images: Fit to height (may have black bars on sides)
        For landscape images: Fit to width (may have black bars on top/bottom)
        
        Args:
            image: PIL Image to fit
            target_size: (width, height) tuple for target area
            preserve_aspect: If True, preserve aspect ratio with black bars
            
        Returns:
            PIL Image that fits the target area
        """
        target_width, target_height = target_size
        img_width, img_height = image.size
        
        # Check if source image is portrait or landscape
        is_portrait = img_height > img_width
        
        if preserve_aspect:
            # Calculate scale factors
            scale_width = target_width / img_width
            scale_height = target_height / img_height
            
            if is_portrait:
                # Portrait: fit to height, center horizontally
                scale = scale_height
                new_width = int(img_width * scale)
                new_height = target_height
                
                # Resize image
                resized_img = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Create target canvas with black background
                result = Image.new('RGB', (target_width, target_height), (0, 0, 0))
                
                # Center the image horizontally
                x_offset = (target_width - new_width) // 2
                result.paste(resized_img, (x_offset, 0))
                
            else:
                # Landscape: fit to width, center vertically  
                scale = scale_width
                new_width = target_width
                new_height = int(img_height * scale)
                
                # Resize image
                resized_img = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Create target canvas with black background
                result = Image.new('RGB', (target_width, target_height), (0, 0, 0))
                
                # Center the image vertically
                y_offset = (target_height - new_height) // 2
                result.paste(resized_img, (0, y_offset))
                
        else:
            # Original behavior: stretch to fill (may distort aspect ratio)
            img_ratio = img_width / img_height
            target_ratio = target_width / target_height
            
            if img_ratio > target_ratio:
                # Image is wider than target - scale to fill height, crop width
                new_height = target_height
                new_width = int(new_height * img_ratio)
                resized_img = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Crop to fit width (center crop)
                left = (new_width - target_width) // 2
                result = resized_img.crop((left, 0, left + target_width, target_height))
            else:
                # Image is taller than target - scale to fill width, crop height
                new_width = target_width
                new_height = int(new_width / img_ratio)
                resized_img = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Crop to fit height (center crop)
                top = (new_height - target_height) // 2
                result = resized_img.crop((0, top, target_width, top + target_height))
        
        return result
    
    def _create_composite_frame(self, media_sources, frame_num, total_frames):
        """
        Create a single composite frame for the given frame number.
        
        Args:
            media_sources: List of media source dictionaries
            frame_num: Current frame number (0-based)
            total_frames: Total number of frames in the video
            
        Returns:
            PIL Image for this frame
        """
        # Get dimensions
        canvas_width, canvas_height = self.resolution
        
        # Create composite with black background
        composite = Image.new('RGB', (canvas_width, canvas_height), (0, 0, 0))
        
        # Layout: 70% main image, 30% preview area (split vertically)
        main_width = int(canvas_width * 0.7)
        preview_width = canvas_width - main_width
        preview_height = canvas_height // 2
        
        # Main media (left 70%) - preserve aspect ratio for portrait images
        main_img = self._get_frame_from_source(media_sources[0], frame_num, total_frames)
        if main_img:
            main_resized = self._fit_image_to_area(main_img, (main_width, canvas_height), preserve_aspect=True)
            composite.paste(main_resized, (0, 0))
        
        # Top preview (right 30%, top 50%) - crop to fill, no gaps
        if len(media_sources) > 1:
            preview1_img = self._get_frame_from_source(media_sources[1], frame_num, total_frames)
            if preview1_img:
                preview1_fitted = self._fit_image_to_area(preview1_img, (preview_width, preview_height), preserve_aspect=False)
                composite.paste(preview1_fitted, (main_width, 0))
        
        # Bottom preview (right 30%, bottom 50%) - crop to fill, no gaps
        if len(media_sources) > 2:
            preview2_img = self._get_frame_from_source(media_sources[2], frame_num, total_frames)
            if preview2_img:
                preview2_fitted = self._fit_image_to_area(preview2_img, (preview_width, preview_height), preserve_aspect=False)
                composite.paste(preview2_fitted, (main_width, preview_height))
        
        return composite
    
    def _extract_all_video_frames(self, media_source, total_frames, temp_dir):
        """
        Extract ALL video frames needed for this slide in a single FFmpeg call.
        This is MUCH faster than extracting frames one at a time (40s -> 2s).
        
        Args:
            media_source: Video media source dictionary
            total_frames: Total number of frames needed
            temp_dir: Temporary directory for frame files
            
        Returns:
            Dictionary mapping frame_num -> PIL Image
        """
        video_path = media_source['path']
        video_duration = media_source.get('duration')
        
        # Calculate all timestamps we'll need
        timestamps = []
        for frame_num in range(total_frames):
            time_position = (frame_num / total_frames) * self.duration
            if video_duration and video_duration > 0:
                time_position = time_position % video_duration
                time_position = min(time_position, video_duration - 0.01)
            timestamps.append((frame_num, time_position))
        
        # Extract frames to a temporary directory using FFmpeg
        # Use trim+setpts to extract a looping video segment
        frames_dict = {}
        
        # Create temp directory for this video's frames
        video_temp_dir = temp_dir / f"video_{video_path.stem}"
        video_temp_dir.mkdir(exist_ok=True)
        
        # Extract all frames using fps filter - this is the KEY optimization!
        # Instead of 90 separate FFmpeg calls, we make ONE call that outputs all frames
        cmd = [
            FFmpegPaths.ffmpeg(), "-y",
            "-i", str(video_path),
            "-vf", f"fps={self.fps}",  # Sample at our target fps
            "-t", str(self.duration),  # Duration of output
            "-start_number", "0",
            f"{video_temp_dir}/frame_%04d.png"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                # Load all extracted frames
                for frame_num in range(total_frames):
                    frame_path = video_temp_dir / f"frame_{frame_num:04d}.png"
                    if frame_path.exists():
                        img = Image.open(frame_path)
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        frames_dict[frame_num] = img
                    else:
                        # Frame missing, use black
                        frames_dict[frame_num] = Image.new('RGB', (1920, 1080), (0, 0, 0))
        except Exception as e:
            print(f"[MultiSlide] ERROR: Bulk frame extraction failed: {e}")
        
        return frames_dict
    
    def _get_frame_from_source(self, media_source, frame_num, total_frames):
        """
        Get a frame from a media source (image or video).
        
        Args:
            media_source: Dictionary with 'type' and 'data'/'path'
            frame_num: Current frame number
            total_frames: Total frames (for video timing)
            
        Returns:
            PIL Image for this frame
        """
        if media_source['type'] == 'image':
            # Return the same image for all frames
            return media_source['data']
        
        elif media_source['type'] == 'video':
            # Use pre-extracted frames (should always be available now)
            if 'frames' in media_source:
                return media_source['frames'].get(frame_num)
            
            # Fallback: return black (should never happen)
            return Image.new('RGB', (1920, 1080), (0, 0, 0))
        
        return None
    
    def render(self, working_dir: Path, log_callback=None, progress_callback=None) -> Path:
        """
        Render the multi-slide as a video clip using FFmpeg complex filter.
        
        Performance: 
        - Static images only: ~7 seconds for 3-second slide
        - Mixed (images + video): ~10 seconds for 3-second slide
        - Previous Python-based approach: 40+ seconds
        
        The key optimization is using FFmpeg's complex filter to do all compositing
        in hardware-accelerated C code instead of Python PIL frame-by-frame processing.
        """
        working_dir.mkdir(parents=True, exist_ok=True)
        
        if log_callback:
            log_callback(f"[MultiSlide] Rendering composite video with dynamic frames")
        
        # Get the media files for this multislide (should be exactly 3)
        media_paths = self.media_files
        
        if len(media_paths) < 3:
            raise ValueError("MultiSlide requires at least 3 media files")

        # Create cache key parameters for this specific multi-slide
        # Use a composite "virtual" path that represents all constituent files
        media_file_info = []
        for path in media_paths:
            if path.exists():
                media_file_info.append({
                    "name": path.name,  # Use filename only, not absolute path
                    "size": path.stat().st_size
                })
        
        # Create a virtual path for cache key (use first file as base)
        virtual_path = media_paths[0] if media_paths else Path("unknown")
        
        cache_params = {
            "operation": "multi_slide_render",
            "duration": self.duration,
            "fps": self.fps,
            "resolution": self.resolution,
            "format": "mp4",
            "media_files": media_file_info,  # Include all constituent files
            "slide_count": self.slide_count,
            "video_quality": cfg.get('video_quality', 'maximum')  # Include quality in cache key
        }
        
        # Check cache first
        cached_clip = FFmpegCache.get_cached_clip(virtual_path, cache_params)
        if cached_clip:
            if log_callback:
                log_callback(f"[FFmpegCache] Using cached multi-slide clip: {cached_clip.name}")
            
            # Create a unique output filename in working directory
            import hashlib
            param_hash = hashlib.md5(str(cache_params).encode()).hexdigest()[:8]
            # Use first filename as identifier instead of index
            first_file_stem = Path(self.media_files[0]).stem
            clip_path = working_dir / f"multi_{first_file_stem}_{param_hash}.mp4"
            self._rendered_clip = clip_path
            
            # Copy cached clip to working directory
            import shutil
            shutil.copy2(cached_clip, clip_path)
            return clip_path

        # Create a unique output filename based on parameters
        import hashlib
        param_hash = hashlib.md5(str(cache_params).encode()).hexdigest()[:8]
        # Use first filename as identifier instead of index
        first_file_stem = Path(self.media_files[0]).stem
        clip_path = working_dir / f"multi_{first_file_stem}_{param_hash}.mp4"
        self._rendered_clip = clip_path
        
        # NEW APPROACH: Use FFmpeg to composite everything in ONE pass
        # This is 10-20x faster than Python PIL frame-by-frame compositing
        if log_callback:
            log_callback(f"[MultiSlide] Using FFmpeg complex filter for fast compositing...")
        
        # Check if all inputs are static images (no video) - we can optimize this case
        all_static = all(path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.heic'] 
                        for path in media_paths)
        
        if all_static:
            # OPTIMIZED PATH: Direct composite without intermediate files
            if log_callback:
                log_callback(f"[MultiSlide] All static images - using direct composite...")
            
            # Convert HEIC to temp JPEG if needed (faster than PNG)
            temp_heic_files = []
            input_paths = []
            for path in media_paths:
                if path.suffix.lower() == '.heic':
                    temp_jpg = working_dir / f"temp_heic_{path.stem}_{param_hash}.jpg"
                    temp_heic_files.append(temp_jpg)
                    img = Image.open(path)
                    img = ImageOps.exif_transpose(img)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    # Resize to reasonable size for faster processing (FFmpeg will scale anyway)
                    # Max dimension 2048 is plenty for compositing
                    if max(img.size) > 2048:
                        img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                    # Save as JPEG with quality 85 (much faster than PNG, still good quality)
                    img.save(temp_jpg, 'JPEG', quality=85, optimize=False)
                    input_paths.append(temp_jpg)
                else:
                    input_paths.append(path)
            
            try:
                # Build complex filter for direct composite
                canvas_w, canvas_h = self.resolution
                main_w = int(canvas_w * 0.7)
                preview_w = canvas_w - main_w
                preview_h = canvas_h // 2
                
                filter_complex = (
                    # Scale main image to fit 70% area (preserve aspect)
                    f"[0:v]scale={main_w}:{canvas_h}:force_original_aspect_ratio=decrease,"
                    f"pad={main_w}:{canvas_h}:({main_w}-iw)/2:({canvas_h}-ih)/2:black[main];"
                    
                    # Scale preview 1 to fill 30% x 50% area (crop to fill)
                    f"[1:v]scale={preview_w}:{preview_h}:force_original_aspect_ratio=increase,"
                    f"crop={preview_w}:{preview_h}[prev1];"
                    
                    # Scale preview 2 to fill 30% x 50% area (crop to fill)
                    f"[2:v]scale={preview_w}:{preview_h}:force_original_aspect_ratio=increase,"
                    f"crop={preview_w}:{preview_h}[prev2];"
                    
                    # Create black canvas
                    f"color=black:s={canvas_w}x{canvas_h}:d={self.duration}[bg];"
                    
                    # Overlay all
                    f"[bg][main]overlay=0:0[tmp1];"
                    f"[tmp1][prev1]overlay={main_w}:0[tmp2];"
                    f"[tmp2][prev2]overlay={main_w}:{preview_h}[out]"
                )
                
                # Direct composite command
                cmd = [
                    FFmpegPaths.ffmpeg(), "-y",
                    "-loop", "1", "-i", str(input_paths[0]),
                    "-loop", "1", "-i", str(input_paths[1]),
                    "-loop", "1", "-i", str(input_paths[2]),
                    "-filter_complex", filter_complex,
                    "-map", "[out]",
                    "-t", str(self.duration),
                    "-r", str(self.fps),
                ]
                # Add quality settings from config
                cmd.extend(cfg.get_ffmpeg_encoding_params())
                cmd.append(str(clip_path))
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise RuntimeError(f"FFmpeg direct composite failed: {result.stderr}")
                
                # Store in cache and return
                FFmpegCache.store_clip(virtual_path, cache_params, clip_path)
                if log_callback:
                    log_callback(f"[MultiSlide] Composite complete: {clip_path.name}")
                return clip_path
                
            finally:
                # Clean up temp HEIC files
                for temp_heic in temp_heic_files:
                    try:
                        if temp_heic.exists():
                            temp_heic.unlink()
                    except Exception:
                        pass
        
        # FALLBACK PATH: For videos, create intermediate clips then composite
        # Step 1: Prepare input sources as video clips
        temp_clips = []
        temp_heic_files = []  # Track HEIC->JPEG conversions for cleanup
        try:
            for i, path in enumerate(media_paths):
                # Create a temporary video clip from this source
                temp_clip = working_dir / f"temp_source_{i}_{param_hash}.mp4"
                temp_clips.append(temp_clip)
                
                # Handle HEIC files - convert to temp JPEG first (faster than PNG)
                input_path = path
                if path.suffix.lower() == '.heic':
                    temp_jpg = working_dir / f"temp_heic_{i}_{param_hash}.jpg"
                    temp_heic_files.append(temp_jpg)
                    
                    # Convert HEIC to JPEG using PIL (faster than PNG)
                    img = Image.open(path)
                    img = ImageOps.exif_transpose(img)
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    # Resize to reasonable size for faster processing
                    if max(img.size) > 2048:
                        img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
                    img.save(temp_jpg, 'JPEG', quality=85, optimize=False)
                    input_path = temp_jpg
                
                if input_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    # Convert static image to video clip (fast, low quality for intermediate)
                    cmd = [
                        FFmpegPaths.ffmpeg(), "-y",
                        "-loop", "1",
                        "-i", str(input_path),
                        "-t", str(self.duration),
                        "-r", str(self.fps),
                        "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
                        "-pix_fmt", "yuv420p",
                        "-c:v", "libx264",
                        "-preset", "veryfast",  # Faster than ultrafast for encoding
                        "-crf", "30",  # Lower quality = faster (this is just an intermediate)
                        str(temp_clip)
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        raise RuntimeError(f"Failed to create video from image: {result.stderr}")
                        
                elif input_path.suffix.lower() in ['.mp4', '.mov']:
                    # For videos, ensure they loop/trim to correct duration
                    try:
                        video_duration = get_video_duration(path)
                    except Exception:
                        video_duration = self.duration
                    
                    if video_duration < self.duration:
                        # Video is too short - loop it
                        cmd = [
                            FFmpegPaths.ffmpeg(), "-y",
                            "-stream_loop", "-1",  # Infinite loop
                            "-i", str(path),
                            "-t", str(self.duration),
                            "-r", str(self.fps),
                            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
                            "-c:v", "libx264",
                            "-preset", "veryfast",
                            "-crf", "30",
                            str(temp_clip)
                        ]
                    else:
                        # Video is long enough - just trim
                        cmd = [
                            FFmpegPaths.ffmpeg(), "-y",
                            "-i", str(path),
                            "-t", str(self.duration),
                            "-r", str(self.fps),
                            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
                            "-c:v", "libx264",
                            "-preset", "veryfast",
                            "-crf", "30",
                            str(temp_clip)
                        ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        raise RuntimeError(f"Failed to prepare video {path.name}: {result.stderr}")
            
            # Step 2: Use FFmpeg complex filter to composite the three sources
            # Verify all temp clips were created successfully
            for i, temp_clip in enumerate(temp_clips):
                if not temp_clip.exists():
                    raise RuntimeError(f"Temp clip {i} was not created: {temp_clip.name} (source: {media_paths[i].name})")
            
            # Layout: 70% main (left), 30% split vertically (right)
            canvas_w, canvas_h = self.resolution
            main_w = int(canvas_w * 0.7)
            preview_w = canvas_w - main_w
            preview_h = canvas_h // 2
            
            # Build complex filter graph
            # [0:v] = main image (scaled to 70% width, preserve aspect, centered)
            # [1:v] = top preview (scaled to 30% width, 50% height, crop to fill)
            # [2:v] = bottom preview (scaled to 30% width, 50% height, crop to fill)
            
            filter_complex = (
                # Scale main image to fit 70% area (preserve aspect)
                f"[0:v]scale={main_w}:{canvas_h}:force_original_aspect_ratio=decrease,"
                f"pad={main_w}:{canvas_h}:({main_w}-iw)/2:({canvas_h}-ih)/2:black[main];"
                
                # Scale preview 1 to fill 30% x 50% area (crop to fill, no black bars)
                f"[1:v]scale={preview_w}:{preview_h}:force_original_aspect_ratio=increase,"
                f"crop={preview_w}:{preview_h}[prev1];"
                
                # Scale preview 2 to fill 30% x 50% area (crop to fill, no black bars)
                f"[2:v]scale={preview_w}:{preview_h}:force_original_aspect_ratio=increase,"
                f"crop={preview_w}:{preview_h}[prev2];"
                
                # Create black canvas
                f"color=black:s={canvas_w}x{canvas_h}:d={self.duration}[bg];"
                
                # Overlay main on left
                f"[bg][main]overlay=0:0[tmp1];"
                
                # Overlay preview1 on top right
                f"[tmp1][prev1]overlay={main_w}:0[tmp2];"
                
                # Overlay preview2 on bottom right
                f"[tmp2][prev2]overlay={main_w}:{preview_h}[out]"
            )
            
            # Build final FFmpeg command
            cmd = [
                FFmpegPaths.ffmpeg(), "-y",
                "-i", str(temp_clips[0]),
                "-i", str(temp_clips[1]),
                "-i", str(temp_clips[2]),
                "-filter_complex", filter_complex,
                "-map", "[out]",
                "-r", str(self.fps),
            ]
            # Add quality settings from config
            cmd.extend(cfg.get_ffmpeg_encoding_params())
            cmd.append(str(clip_path))
            
            if log_callback:
                log_callback(f"[MultiSlide] Compositing with FFmpeg complex filter...")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg compositing failed: {result.stderr}")
            
            # Store result in cache
            FFmpegCache.store_clip(virtual_path, cache_params, clip_path)
            
            if log_callback:
                log_callback(f"[MultiSlide] Composite complete: {clip_path.name}")
            
            # Clean up temporary clips on success only
            for temp_clip in temp_clips:
                try:
                    if temp_clip.exists():
                        temp_clip.unlink()
                except Exception:
                    pass
            # Clean up temporary HEIC conversions
            for temp_heic in temp_heic_files:
                try:
                    if temp_heic.exists():
                        temp_heic.unlink()
                except Exception:
                    pass
            
            return clip_path
            
        except Exception:
            # On error, preserve temp files for debugging
            raise
