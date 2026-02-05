from abc import ABC, abstractmethod
from pathlib import Path
from PIL import Image
from typing import Optional
from slideshow.transitions.utils import extract_frame, load_and_resize_image, get_video_duration


class SlideItem(ABC):
    def __init__(self, path: Path, duration: float, resolution=(1920, 1080), creation_date: float = None):
        self.path = path
        self.duration = duration
        self.resolution = resolution
        self.creation_date = creation_date  # Timestamp, read once from EXIF/file stats
        self._to_image: Optional[Image.Image] = None
        self._from_image: Optional[Image.Image] = None
        self._preview_image: Optional[Image.Image] = None
        self._rendered_clip: Optional[Path] = None
        self._is_portrait: Optional[bool] = None  # Cache for orientation check

    def render(self, working_dir: Path, log_callback=None, progress_callback=None) -> Path:
        """
        Template method for rendering a slide.
        - working_dir: Path to folder where rendered clip will be stored.
        """
        working_dir.mkdir(parents=True, exist_ok=True)

        output_filename = working_dir / f"{self.path.stem}.mp4"
        self._rendered_clip = output_filename
        return output_filename

    def _load_image(self, From: bool):
        """
        Extract and resize either the first or last frame of the rendered clip.
        close=False → first frame (open)
        close=True → last frame (close)
        """
        if not self._rendered_clip:
            raise RuntimeError(f"Cannot extract frame: video not rendered yet ({self.path.name})")
        frame = extract_frame(self._rendered_clip, last=From)
        return frame

    def get_to_image(self):
        """Return the opening frame, caching it to avoid repeated extraction."""
        if self._to_image is None:
            self._to_image = self._load_image(From=False)
        return self._to_image

    def get_from_image(self):
        """Return the closing frame, caching it to avoid repeated extraction."""
        if self._from_image is None:
            self._from_image = self._load_image(From=True)
        return self._from_image
    
    def get_preview_image(self) -> Image.Image:
        """Return a preview image from the source media, caching it to avoid repeated loading."""
        if self._preview_image is None:
            self._preview_image = self._load_preview_image()
        return self._preview_image
    
    @abstractmethod
    def _load_preview_image(self) -> Image.Image:
        """Load a preview image from the source media. Must be implemented by child classes."""
        pass
    
    def get_metadata(self, index: int, start_time: float):
        """Generate metadata for this slide."""
        from slideshow.video_editor import VideoSegment
        
        if not self._rendered_clip:
            raise RuntimeError(f"Cannot generate metadata: slide not rendered yet ({self.path.name})")
        
        duration = get_video_duration(str(self._rendered_clip)) or 0.0
        slide_type = "multi_slide" if "multi_" in self._rendered_clip.name else "slide"
        
        return VideoSegment(
            index=index,
            type=slide_type,
            source_path=str(self.path),
            rendered_path=str(self._rendered_clip.resolve()),
            duration=duration,
            start_time=start_time,
            end_time=start_time + duration,
            byte_offset=0,
            byte_size=0
        )

    def get_rendered_clip(self) -> Optional[Path]:
        """Return the path to the rendered clip (if render() has been called)."""
        return self._rendered_clip

    def is_portrait(self) -> bool:
        """
        Check if this slide's content is in portrait orientation.
        Abstract method - must be implemented by child classes.
        Result is cached after first call.
        """
        if self._is_portrait is None:
            self._is_portrait = self._check_orientation()
        return self._is_portrait
    
    def rotate(self, degrees: int) -> bool:
        """
        Rotate this slide by the specified degrees and save.
        Default implementation returns False (not supported).
        Child classes should override to provide rotation functionality.
        
        Args:
            degrees: Rotation angle (positive = counter-clockwise)
            
        Returns:
            True if successful, False if not supported or failed
        """
        return False
    
    @abstractmethod
    def _check_orientation(self) -> bool:
        """
        Check the orientation of the source media file.
        Must be implemented by child classes (PhotoSlide, VideoSlide, etc.)
        
        Returns:
            True if portrait (height > width), False if landscape
        """
        pass

    def exists(self) -> bool:
        """Check if the underlying media file still exists on disk."""
        return self.path.exists()

    def __str__(self):
        return f"{self.path.name} (Duration: {self.duration:.2f}s)"

    def __repr__(self):
        return f"{self.__class__.__name__}(path={self.path}, duration={self.duration})"