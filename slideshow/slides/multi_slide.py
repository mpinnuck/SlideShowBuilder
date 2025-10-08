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
from slideshow.config import Config
from slideshow.slides.slide_item import SlideItem
from slideshow.transitions.ffmpeg_cache import FFmpegCache
from slideshow.transitions.ffmpeg_paths import FFmpegPaths


class MultiSlide(SlideItem):
    def __init__(self, i, media_files, duration: float, resolution=(1920, 1080), fps=30):
        """
        Create a MultiSlide from a starting index and media files list.
        
        Args:
            i: Starting index in media_files
            media_files: List of media file paths
            duration: Duration for the slide
            resolution: Output resolution
            fps: Frame rate for video rendering
        """
        # Initialize super class with the first image path
        super().__init__(media_files[i], duration, resolution)
        
        self.index = i
        self.media_files = media_files
        self.fps = fps
        self.composite_image = None
        self.slide_count = 3  # Hard coded initially
        
    def get_slide_count(self):
        """Return the number of slides consumed by this MultiSlide."""
        return self.slide_count
    
    def _check_orientation(self) -> bool:
        """
        MultiSlide orientation is determined by the main image (first slide).
        """
        try:
            if self.index < len(self.media_files):
                main_file = self.media_files[self.index]
                if main_file.suffix.lower() in ['.jpg', '.jpeg', '.png']:
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
        """Create the composite image from the media files starting at index."""
        # Load the next 3 images starting from our index
        images = []
        for j in range(3):
            if self.index + j < len(self.media_files):
                file_path = self.media_files[self.index + j]
                # Only load image files
                if file_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
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
            # Extract frame from video at appropriate time
            video_path = media_source['path']
            
            # Calculate time position in the video
            time_position = (frame_num / total_frames) * self.duration
            
            # Use FFmpeg to extract the frame at this time
            cmd = [
                FFmpegPaths.ffmpeg(), "-y",
                "-i", str(video_path),
                "-ss", str(time_position),
                "-vframes", "1",
                "-f", "image2pipe",
                "-pix_fmt", "rgb24",
                "-vcodec", "rawvideo",
                "pipe:1"
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True)
                if result.returncode == 0 and result.stdout:
                    # Convert raw RGB data to PIL Image
                    import numpy as np
                    # We need to determine the video dimensions first
                    # For now, assume standard resolution and resize later
                    width, height = 1920, 1080  # Default assumption
                    frame_data = np.frombuffer(result.stdout, dtype=np.uint8)
                    if len(frame_data) >= width * height * 3:
                        frame_array = frame_data[:width * height * 3].reshape((height, width, 3))
                        return Image.fromarray(frame_array, 'RGB')
            except Exception as e:
                print(f"[MultiSlide] Warning: Failed to extract video frame: {e}")
            
            # Fallback: return a black image
            return Image.new('RGB', (1920, 1080), (0, 0, 0))
        
        return None
    
    def render(self, working_dir: Path, log_callback=None, progress_callback=None) -> Path:
        """Render the multi-slide as a video clip with dynamic frame generation."""
        working_dir.mkdir(parents=True, exist_ok=True)
        
        if log_callback:
            log_callback(f"[MultiSlide] Rendering composite video with dynamic frames")
        
        # Get the media files for this multislide
        media_paths = []
        for j in range(self.slide_count):
            if self.index + j < len(self.media_files):
                media_paths.append(self.media_files[self.index + j])
        
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
            "slide_count": self.slide_count
        }
        
        # Check cache first
        cached_clip = FFmpegCache.get_cached_clip(virtual_path, cache_params)
        if cached_clip:
            if log_callback:
                log_callback(f"[FFmpegCache] Using cached multi-slide clip: {cached_clip.name}")
            
            # Create a unique output filename in working directory
            import hashlib
            param_hash = hashlib.md5(str(cache_params).encode()).hexdigest()[:8]
            clip_path = working_dir / f"multi_{self.index}_{param_hash}.mp4"
            self._rendered_clip = clip_path
            
            # Copy cached clip to working directory
            import shutil
            shutil.copy2(cached_clip, clip_path)
            return clip_path

        # Create a unique output filename based on parameters
        import hashlib
        param_hash = hashlib.md5(str(cache_params).encode()).hexdigest()[:8]
        clip_path = working_dir / f"multi_{self.index}_{param_hash}.mp4"
        self._rendered_clip = clip_path
        
        # Calculate total frames needed
        total_frames = int(self.duration * self.fps)
        
        # Prepare media sources
        media_sources = []
        for path in media_paths:
            if path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                # Static image
                img = Image.open(path)
                # Apply EXIF orientation to display correctly
                img = ImageOps.exif_transpose(img)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                media_sources.append({'type': 'image', 'data': img})
            elif path.suffix.lower() in ['.mp4', '.mov']:
                # Video - we'll extract frames as needed
                media_sources.append({'type': 'video', 'path': path})
        
        # Create output video using FFmpeg with frame-by-frame input
        output_path = working_dir / f"{self.path.stem}.mp4"
        
        # Generate frames and pipe to FFmpeg
        import subprocess
        import numpy as np
        
        cmd = [
            FFmpegPaths.ffmpeg(), "-y",
            "-f", "rawvideo",
            "-pixel_format", "rgb24", 
            "-video_size", f"{self.resolution[0]}x{self.resolution[1]}",
            "-framerate", str(self.fps),
            "-i", "pipe:0",
        ]
        cmd.extend(Config.instance().get_ffmpeg_encoding_params())  # Use project quality settings
        cmd.extend([
            "-pix_fmt", "yuv420p",
            str(output_path)
        ])
        
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, 
                                  stdout=subprocess.DEVNULL, 
                                  stderr=subprocess.DEVNULL)  # Suppress verbose output
        
        try:
            for frame_num in range(total_frames):
                # Create composite frame
                composite_frame = self._create_composite_frame(media_sources, frame_num, total_frames)
                
                # Convert to numpy array and write to pipe
                frame_array = np.array(composite_frame)
                process.stdin.write(frame_array.tobytes())
                
                if progress_callback and frame_num % 30 == 0:  # Update every second
                    progress = (frame_num + 1) / total_frames
                    progress_callback(progress)
                    
        finally:
            process.stdin.close()
            process.wait()
        
        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg failed during MultiSlide rendering")
        
        # Store result in cache for future use
        FFmpegCache.store_clip(virtual_path, cache_params, output_path)
        
        self._rendered_clip = output_path
        return output_path