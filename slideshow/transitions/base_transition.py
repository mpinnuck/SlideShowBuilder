from pathlib import Path
from abc import ABC, abstractmethod

class BaseTransition(ABC):
    """Base class for all slideshow transitions"""
    
    def __init__(self, duration=1.0):
        self.duration = duration
        self.name = "Base Transition"
        self.description = "Abstract base transition class"
    
    @abstractmethod
    def render(self, from_path: Path, to_path: Path, output_path: Path):
        """
        Render the transition between two video files
        
        Args:
            from_path: Path to the source video file
            to_path: Path to the destination video file  
            output_path: Path where the transition video should be saved
        """
        pass
    
    @abstractmethod
    def get_requirements(self) -> list:
        """
        Return list of required dependencies for this transition
        
        Returns:
            List of required packages/dependencies
        """
        pass
    
    def is_available(self) -> bool:
        """
        Check if this transition can be used (all dependencies available)
        
        Returns:
            True if transition can be used, False otherwise
        """
        try:
            requirements = self.get_requirements()
            for requirement in requirements:
                if requirement == "ffmpeg":
                    # Check if ffmpeg is available
                    import subprocess
                    subprocess.run(["ffmpeg", "-version"], 
                                 stdout=subprocess.DEVNULL, 
                                 stderr=subprocess.DEVNULL, 
                                 check=True)
                else:
                    # Check if Python package is available
                    __import__(requirement)
            return True
        except (ImportError, subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def validate_inputs(self, from_path: Path, to_path: Path, output_path: Path) -> bool:
        """
        Validate that input files exist and output path is writable
        
        Args:
            from_path: Source video file path
            to_path: Destination video file path
            output_path: Output video file path
            
        Returns:
            True if inputs are valid, False otherwise
        """
        if not from_path.exists():
            raise FileNotFoundError(f"Source video not found: {from_path}")
        
        if not to_path.exists():
            raise FileNotFoundError(f"Destination video not found: {to_path}")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        return True
    
    def __str__(self):
        return f"{self.name} (Duration: {self.duration}s)"
    
    def __repr__(self):
        return f"{self.__class__.__name__}(duration={self.duration})"