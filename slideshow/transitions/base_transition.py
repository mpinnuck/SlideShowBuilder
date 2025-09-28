from pathlib import Path
from abc import ABC, abstractmethod
import subprocess
from slideshow.slides.slide_item import SlideItem


class BaseTransition(ABC):
    """Base class for all slideshow transitions (SlideItem-based)."""

    def __init__(self, duration: float = 1.0):
        self.duration = duration
        self.name = self.__class__.__name__
        self.description = "Abstract base transition class"

    @abstractmethod
    def render(self, from_clip: Path, to_clip: Path, output_path: Path):
        """
        Render the transition between two SlideItem objects.

        Args:
            from_slide: SlideItem representing the previous slide
            to_slide: SlideItem representing the next slide
            output_path: Path where the transition video should be saved
        """
        pass

    def get_requirements(self) -> list:
        """
        Return list of required dependencies for this transition.
        Subclasses can override to specify e.g. ['ffmpeg', 'numpy'].
        """
        return []

    def is_available(self) -> bool:
        """
        Check if this transition can be used (all dependencies available).
        Maps 'Pillow' to 'PIL' for import since Pillow installs under PIL.
        """
        try:
            for requirement in self.get_requirements():
                if requirement == "ffmpeg":
                    subprocess.run(
                        ["ffmpeg", "-version"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True
                    )
                else:
                    module_name = "PIL" if requirement.lower() == "pillow" else requirement
                    __import__(module_name)
            return True
        except ImportError as e:
            print(f"[Transition] Missing Python package: {e.name}")
        except subprocess.CalledProcessError:
            print("[Transition] ffmpeg not available or not executable")
        except FileNotFoundError:
            print("[Transition] ffmpeg not found in PATH")
        return False


    def ensure_output_dir(self, output_path: Path):
        """
        Convenience helper to ensure output directory exists.
        Can be used by subclasses before writing the transition video.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

    def __str__(self):
        return f"{self.name} (Duration: {self.duration}s)"

    def __repr__(self):
        return f"{self.__class__.__name__}(duration={self.duration})"
