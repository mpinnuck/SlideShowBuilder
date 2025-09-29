from abc import ABC, abstractmethod
from pathlib import Path
from PIL import Image
from typing import Optional
from slideshow.transitions.utils import extract_frame, load_and_resize_image


class SlideItem(ABC):
    def __init__(self, path: Path, duration: float, resolution=(1920, 1080)):
        self.path = path
        self.duration = duration
        self.resolution = resolution
        self._to_image: Optional[Image.Image] = None
        self._from_image: Optional[Image.Image] = None
        self._rendered_clip: Optional[Path] = None

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

    def get_rendered_clip(self) -> Optional[Path]:
        """Return the path to the rendered clip (if render() has been called)."""
        return self._rendered_clip

    def exists(self) -> bool:
        """Check if the underlying media file still exists on disk."""
        return self.path.exists()

    def __str__(self):
        return f"{self.path.name} (Duration: {self.duration:.2f}s)"

    def __repr__(self):
        return f"{self.__class__.__name__}(path={self.path}, duration={self.duration})"