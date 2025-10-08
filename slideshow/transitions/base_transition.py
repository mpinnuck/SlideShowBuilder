# slideshow/transitions/base_transition.py
from pathlib import Path
from abc import ABC, abstractmethod
import subprocess
from .ffmpeg_paths import FFmpegPaths

# slideshow/transitions/base_transition.py
from pathlib import Path
from abc import ABC, abstractmethod
import subprocess
from .ffmpeg_paths import FFmpegPaths

class BaseTransition(ABC):
    """Base class for all slideshow transitions (SlideItem-based)."""

    def __init__(self, duration: float = 1.0, config: dict = None):
        self.duration = duration
        self.config = config
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
        import os
        import traceback
        
        # Log to a file in user's home directory for debugging Finder launches
        debug_log = os.path.expanduser("~/slideshow_transition_debug.log")
        
        try:
            with open(debug_log, 'a') as f:
                f.write(f"\n=== Checking availability for {self.__class__.__name__} ===\n")
                f.write(f"Requirements: {self.get_requirements()}\n")
                
                for requirement in self.get_requirements():
                    if requirement == "ffmpeg":
                        # Use FFmpegPaths singleton to find ffmpeg
                        ffmpeg_path = FFmpegPaths.ffmpeg()
                        
                        try:
                            subprocess.run(
                                [ffmpeg_path, "-version"],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                check=True
                            )
                            f.write(f"✓ {requirement} available at {ffmpeg_path}\n")
                        except (subprocess.CalledProcessError, FileNotFoundError) as e:
                            raise FileNotFoundError(f"ffmpeg not found at {ffmpeg_path}")
                    else:
                        module_name = "PIL" if requirement.lower() == "pillow" else requirement
                        __import__(module_name)
                        f.write(f"✓ {module_name} imported successfully\n")
                
                f.write("✓ All requirements available\n")
            return True
            
        except ImportError as e:
            with open(debug_log, 'a') as f:
                f.write(f"✗ ImportError: {e}\n")
                f.write(f"Module name: {e.name if hasattr(e, 'name') else 'unknown'}\n")
                f.write(traceback.format_exc())
            print(f"[Transition] Missing Python package: {e.name if hasattr(e, 'name') else 'unknown'}")
            
        except subprocess.CalledProcessError as e:
            with open(debug_log, 'a') as f:
                f.write(f"✗ CalledProcessError: ffmpeg not available or not executable\n")
                f.write(traceback.format_exc())
            print("[Transition] ffmpeg not available or not executable")
            
        except FileNotFoundError as e:
            with open(debug_log, 'a') as f:
                f.write(f"✗ FileNotFoundError: {e}\n")
                f.write(f"PATH: {os.environ.get('PATH', 'NOT SET')}\n")
                f.write(traceback.format_exc())
            print("[Transition] ffmpeg not found in PATH")
            
        except Exception as e:
            with open(debug_log, 'a') as f:
                f.write(f"✗ Unexpected error: {e}\n")
                f.write(traceback.format_exc())
            print(f"[Transition] Unexpected error checking availability: {e}")
            
        return False

    def ensure_output_dir(self, output_path: Path):
        """Ensure output directory exists before writing the transition video."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

    def __str__(self):
        return f"{self.name} (Duration: {self.duration}s)"

    def __repr__(self):
        return f"{self.__class__.__name__}(duration={self.duration})"
