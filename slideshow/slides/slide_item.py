from abc import ABC, abstractmethod
from pathlib import Path
from PIL import Image
from typing import Optional

class SlideItem(ABC):
    def __init__(self, path: Path, duration: float, resolution=(1920, 1080)):
        self.path = path
        self.duration = duration
        self.resolution = resolution
        self._open_image: Optional[Image.Image] = None
        self._close_image: Optional[Image.Image] = None

    @abstractmethod
    def render(self, output_path: Path):
        """Render this slide into a CFR video file."""
        pass

    @abstractmethod
    def _load_image(self, close: bool):
        """
        Abstract helper to extract/resize an image from the slide.
        - close=False → Opening frame
        - close=True  → Closing frame
        Subclasses implement this differently for photos vs. videos.
        """
        pass

    def get_open_image(self):
        """Return the opening frame, caching it to avoid repeated extraction."""
        if self._open_image is None:
            self._open_image = self._load_image(close=False)
        return self._open_image

    def get_close_image(self):
        """Return the closing frame, caching it to avoid repeated extraction."""
        if self._close_image is None:
            self._close_image = self._load_image(close=True)
        return self._close_image

    def exists(self) -> bool:
        """Check if the underlying media file still exists on disk."""
        return self.path.exists()

    def __str__(self):
        return f"{self.path.name} (Duration: {self.duration:.2f}s)"

    def __repr__(self):
        return f"{self.__class__.__name__}(path={self.path}, duration={self.duration})"
    