"""
FFmpeg Path Singleton
---------------------
Singleton utility to locate and cache ffmpeg/ffprobe executable paths.
Searches common installation locations once and returns cached paths.
"""

import subprocess
from typing import Optional


class FFmpegPaths:
    """Singleton to find and cache ffmpeg/ffprobe executable paths."""
    
    _instance = None
    _ffmpeg_path: Optional[str] = None
    _ffprobe_path: Optional[str] = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FFmpegPaths, cls).__new__(cls)
        return cls._instance
    
    def _find_executable(self, name: str) -> str:
        """
        Find an executable in common locations.
        
        Args:
            name: Executable name ('ffmpeg' or 'ffprobe')
            
        Returns:
            Path to executable, or the name itself if not found
        """
        # Try common locations for both Intel and Apple Silicon Macs
        search_paths = [
            name,  # Try PATH first
            f'/usr/local/bin/{name}',  # Homebrew Intel
            f'/opt/homebrew/bin/{name}',  # Homebrew Apple Silicon
            f'/usr/bin/{name}',  # System location
        ]
        
        for path in search_paths:
            try:
                subprocess.run(
                    [path, "-version"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                    timeout=2
                )
                return path
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                continue
        
        # Fallback to executable name and let it fail with a clear error
        return name
    
    def _initialize(self):
        """Initialize paths by searching for executables."""
        if not self._initialized:
            self._ffmpeg_path = self._find_executable('ffmpeg')
            self._ffprobe_path = self._find_executable('ffprobe')
            self._initialized = True
    
    def get_ffmpeg(self) -> str:
        """
        Get path to ffmpeg executable.
        
        Returns:
            Path to ffmpeg (cached after first call)
        """
        self._initialize()
        return self._ffmpeg_path
    
    def get_ffprobe(self) -> str:
        """
        Get path to ffprobe executable.
        
        Returns:
            Path to ffprobe (cached after first call)
        """
        self._initialize()
        return self._ffprobe_path
    
    def reset(self):
        """Reset cached paths (useful for testing or if paths change)."""
        self._ffmpeg_path = None
        self._ffprobe_path = None
        self._initialized = False
    
    @classmethod
    def ffmpeg(cls) -> str:
        """Convenience class method to get ffmpeg path."""
        return cls().get_ffmpeg()
    
    @classmethod
    def ffprobe(cls) -> str:
        """Convenience class method to get ffprobe path."""
        return cls().get_ffprobe()


# Convenience functions for backward compatibility
def get_ffmpeg_path() -> str:
    """Get cached path to ffmpeg executable."""
    return FFmpegPaths.ffmpeg()


def get_ffprobe_path() -> str:
    """Get cached path to ffprobe executable."""
    return FFmpegPaths.ffprobe()
