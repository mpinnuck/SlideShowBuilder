# slideshow/transitions/base_transition.py
from pathlib import Path
from abc import ABC, abstractmethod
import subprocess
from .ffmpeg_paths import FFmpegPaths
from .utils import get_video_duration
from .ffmpeg_paths import FFmpegPaths

class BaseTransition(ABC):
    """Base class for all slideshow transitions (SlideItem-based)."""

    def __init__(self, duration: float = 1.0):
        self.duration = duration
        self.name = self.__class__.__name__
        self.description = "Abstract base transition class"

    @abstractmethod
    def render(self, index: int, slides: list, output_path: Path) -> int:
        """
        Render the transition using slides from the array.

        Args:
            index: Current slide index in the slideshow
            slides: Array of all slides in the slideshow
            output_path: Path where the transition video should be saved
            
        Returns:
            Number of slides consumed by this transition:
            - 0: Skip this transition (no video created)
            - 1: Standard transition (consumed current slide)
            - 2+: Multi-slide transition (consumed multiple slides)
        """
        raise NotImplementedError("Subclasses must implement render()")

    def get_requirements(self) -> list:
        """Return list of required dependencies for this transition."""
        return []

    def get_slides_consumed(self, slide_index: int, slides: list) -> int:
        """
        Return the number of slides this transition will consume.
        
        Args:
            slide_index: Current slide index in the slideshow
            slides: Array of all slides in the slideshow
            
        Returns:
            Number of slides that will be consumed:
            - 1: Standard transition (default)
            - 2+: Multi-slide transition (override in subclasses)
        """
        return 1

    def is_available(self) -> bool:
        """Check if this transition can be used (all dependencies available)."""
        try:
            for requirement in self.get_requirements():
                if requirement == "ffmpeg":
                    # Use FFmpegPaths singleton to find ffmpeg
                    ffmpeg_path = FFmpegPaths.ffmpeg()
                    subprocess.run(
                        [ffmpeg_path, "-version"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=True
                    )
                else:
                    module_name = "PIL" if requirement.lower() == "pillow" else requirement
                    __import__(module_name)
            return True
            
        except ImportError as e:
            print(f"[Transition] Missing Python package: {e.name if hasattr(e, 'name') else 'unknown'}")
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("[Transition] ffmpeg not found or not executable")
            
        except Exception as e:
            print(f"[Transition] Unexpected error checking availability: {e}")
            
        return False

    def ensure_output_dir(self, output_path: Path):
        """Ensure output directory exists before writing the transition video."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
    
    def get_metadata(self, index: int, start_time: float, rendered_path: Path):
        """Generate metadata for this transition."""
        from slideshow.video_editor import VideoSegment
        
        if not rendered_path or not rendered_path.exists():
            raise RuntimeError(f"Cannot generate metadata: transition not rendered yet ({rendered_path})")
        
        duration = get_video_duration(str(rendered_path)) or 0.0
        
        return VideoSegment(
            index=index,
            type="transition",
            source_path=None,
            rendered_path=str(rendered_path.resolve()),
            duration=duration,
            start_time=start_time,
            end_time=start_time + duration,
            byte_offset=0,
            byte_size=0
        )

    def __str__(self):
        return f"{self.name} (Duration: {self.duration}s)"

    def __repr__(self):
        return f"{self.__class__.__name__}(duration={self.duration})"
