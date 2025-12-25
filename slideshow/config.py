import json
from pathlib import Path
import os
import threading

# ============================================================================
# Config Singleton - Global Configuration Class
# ============================================================================

class Config:
    """
    Singleton configuration class - ALL configuration access through this class.
    
    Usage:
        # Load config at app startup
        Config.instance().load(output_folder="/path/to/project")
        
        # Access anywhere in the codebase
        quality = Config.instance().get('video_quality', 'maximum')
        params = Config.instance().get_ffmpeg_encoding_params()
        
        # Save changes
        Config.instance().update({"video_quality": "high"})
        Config.instance().save(output_folder="/path/to/project")
        
        # App settings (project history, last project)
        Config.instance().add_to_project_history("MyProject")
        history = Config.instance().get_project_history()
    """
    
    # Class constants
    APP_SETTINGS_DIR = Path.home() / "SlideShowBuilder"
    APP_SETTINGS_FILE = APP_SETTINGS_DIR / "slideshow_settings.json"
    PROJECT_CONFIG_FILE = "slideshow_config.json"
    
    # Default app-level settings
    DEFAULT_APP_SETTINGS = {
        "last_project_path": "",
        "project_history": [],  # List of recent projects {"name": str, "path": str}, newest first (max 10)
        "slideshows_base_dir": str(Path.home() / "SlideShowBuilder")  # Base directory for slideshows
    }
    
    # Default project-level settings
    DEFAULT_CONFIG = {
        "project_name": "MyProject",
        "input_folder": str(APP_SETTINGS_DIR / "MyProject" / "Slides"),
        "output_folder": str(APP_SETTINGS_DIR / "MyProject" / "Output"),
        "photo_duration": 3.0,
        "video_duration": 5.0,
        "transition_duration": 1.0,
        "transition_type": "fade",
        "fps": 30,
        "resolution": [1920, 1080],
        "origami_easing": "quad",
        "origami_lighting": True,
        "origami_fold": "",
        "multislide_frequency": 5,
        "video_quality": "maximum",
        "intro_title": {
            "enabled": False,
            "text": "Project Title\nHere",
            "duration": 5.0,
            "font_path": "/System/Library/Fonts/Arial.ttf",
            "font_size": 120,
            "font_weight": "normal",
            "line_spacing": 1.2,
            "text_color": [255, 255, 255, 255],
            "shadow_color": [0, 0, 0, 180],
            "shadow_offset": [4, 4],
            "rotation": {"axis": "y", "clockwise": True}
        },
        "hardware_acceleration": False,
        "temp_directory": "",
        "auto_cleanup": True,
        "keep_intermediate_frames": False
    }
    
    # FFmpeg encoding quality presets
    FFMPEG_ENCODING_PRESETS = {
        "maximum": {
            "crf": "18", "preset": "slow", "profile": "high", "level": "4.1",
            "description": "Maximum quality - visually lossless, ~18-25 Mbps"
        },
        "high": {
            "crf": "20", "preset": "medium", "profile": "high", "level": "4.1",
            "description": "High quality - excellent balance, ~12-18 Mbps"
        },
        "medium": {
            "crf": "23", "preset": "medium", "profile": "main", "level": "4.0",
            "description": "Medium quality - good compression, ~8-12 Mbps"
        },
        "fast": {
            "crf": "25", "preset": "fast", "profile": "main", "level": "4.0",
            "description": "Fast encoding - smaller files, ~5-8 Mbps"
        }
    }
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        if Config._instance is not None:
            raise RuntimeError("Use Config.instance() instead of creating new instances")
        self._config = None
    
    @classmethod
    def instance(cls):
        """Get the singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    # =================================================================
    # Project Configuration Methods
    # =================================================================
    
    def set(self, config: dict):
        """Set the current configuration dictionary."""
        self._config = config.copy() if config else None
    
    def get_all(self) -> dict:
        """Get the entire configuration dictionary."""
        return self._config.copy() if self._config else {}
    
    def get(self, key: str, default=None):
        """Get a configuration value by key."""
        if self._config is None:
            return default
        return self._config.get(key, default)
    
    def update(self, updates: dict):
        """Update configuration with new values."""
        if self._config is None:
            self._config = self.DEFAULT_CONFIG.copy()
        self._config.update(updates)
    
    def clear(self):
        """Clear the configuration (mainly for testing)."""
        self._config = None
    
    # =================================================================
    # Disk I/O Methods
    # =================================================================
    
    def load(self, output_folder: str = None) -> dict:
        """
        Load project config from disk and set as current config.
        If output_folder not specified, tries to load from last project.
        """
        config = self.DEFAULT_CONFIG.copy()
        
        # Determine config path
        if output_folder:
            config_path = self._get_project_config_path(output_folder)
        else:
            # Try to load from last project
            app_settings = self.load_app_settings()
            last_project = app_settings.get("last_project_path", "")
            config_path = Path(last_project) if last_project else Path(self.PROJECT_CONFIG_FILE)
        
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    user_config = json.load(f)
                    if isinstance(user_config, dict):
                        config.update(user_config)
            except (json.JSONDecodeError, OSError) as e:
                print(f"[Config] WARNING: Failed to load from {config_path} ({e}), using defaults.")
        
        self.set(config)
        return config
    
    def save(self, output_folder: str):
        """
        Save current configuration to disk.
        Also updates app settings to remember this as the last project.
        """
        if not output_folder:
            print("[Config] WARNING: No output folder specified, cannot save config")
            return
        
        if self._config is None:
            print("[Config] WARNING: No config to save")
            return
        
        config_path = self._get_project_config_path(output_folder)
        is_new_folder = not config_path.parent.exists()
        
        # Ensure project folder exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create output folder and cache structure for new folders
        if is_new_folder:
            output_path = Path(output_folder)
            output_path.mkdir(parents=True, exist_ok=True)
            cache_dir = output_path / "working" / "ffmpeg_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            print(f"[Config] Created project folder structure with cache at: {cache_dir}")
        
        # Merge with defaults and save
        merged = self.DEFAULT_CONFIG.copy()
        merged.update(self._config)
        
        try:
            with open(config_path, "w") as f:
                json.dump(merged, f, indent=2)
            
            # Update app settings to remember this project
            app_settings = self.load_app_settings()
            app_settings["last_project_path"] = str(config_path)
            self.save_app_settings(app_settings)
            
        except OSError as e:
            print(f"[Config] WARNING: Failed to save to {config_path} ({e})")
    
    def _get_project_config_path(self, output_folder: str) -> Path:
        """Get the path to the project config file."""
        if not output_folder:
            return Path(self.PROJECT_CONFIG_FILE)
        # Config file is in the parent folder (project folder), not the output folder
        project_folder = Path(output_folder).parent
        return project_folder / self.PROJECT_CONFIG_FILE
    
    # =================================================================
    # App Settings Methods (project history, last project)
    # =================================================================
    
    def load_app_settings(self) -> dict:
        """Load global app settings from ~/SlideShowBuilder/slideshow_settings.json"""
        settings = self.DEFAULT_APP_SETTINGS.copy()
        
        if self.APP_SETTINGS_FILE.exists():
            try:
                with open(self.APP_SETTINGS_FILE, "r") as f:
                    user_settings = json.load(f)
                    if isinstance(user_settings, dict):
                        settings.update(user_settings)
            except (json.JSONDecodeError, OSError) as e:
                print(f"[Config] WARNING: Failed to load app settings ({e}), using defaults")
        
        return settings
    
    def save_app_settings(self, settings: dict):
        """Save global app settings to ~/SlideShowBuilder/slideshow_settings.json"""
        self.APP_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        
        merged = self.DEFAULT_APP_SETTINGS.copy()
        merged.update(settings)
        
        try:
            with open(self.APP_SETTINGS_FILE, "w") as f:
                json.dump(merged, f, indent=2)
        except OSError as e:
            print(f"[Config] WARNING: Failed to save app settings ({e})")
    
    def add_to_project_history(self, project_name: str, project_path: str = None):
        """Add project to history (most recent first, max 10).
        
        Args:
            project_name: Name of the project
            project_path: Optional path to the project folder. If not provided, assumes ~/SlideShowBuilder/
        """
        if not project_name or not project_name.strip():
            return
        
        settings = self.load_app_settings()
        history = settings.get("project_history", [])
        
        # Ensure history is a list
        if not isinstance(history, list):
            history = []
        
        # Normalize history entries - convert old string format to dict format
        normalized_history = []
        for entry in history:
            if isinstance(entry, str):
                # Old format: just a string name, assume default path
                normalized_history.append({"name": entry, "path": ""})
            elif isinstance(entry, dict) and "name" in entry:
                # New format: dict with name and path
                normalized_history.append(entry)
        
        # Determine project path
        if project_path is None:
            project_path = ""  # Empty means default ~/SlideShowBuilder/
        
        # Remove if already exists (to move to top)
        normalized_history = [
            entry for entry in normalized_history 
            if entry["name"] != project_name
        ]
        
        # Add to front
        normalized_history.insert(0, {"name": project_name, "path": project_path})
        
        # Keep only last 10
        normalized_history = normalized_history[:10]
        
        settings["project_history"] = normalized_history
        self.save_app_settings(settings)
    
    def get_project_history(self) -> list:
        """Get list of recent projects as dicts with 'name' and 'path' keys.
        
        Returns:
            List of dicts: [{"name": "ProjectName", "path": "/path/to/project"}, ...]
            Path may be empty string if using default ~/SlideShowBuilder/ location
        """
        settings = self.load_app_settings()
        history = settings.get("project_history", [])
        
        if not isinstance(history, list):
            return []
        
        # Normalize history entries - convert old string format to dict format
        normalized = []
        for entry in history:
            if isinstance(entry, str):
                # Old format: just a string name, assume default path
                normalized.append({"name": entry, "path": ""})
            elif isinstance(entry, dict) and "name" in entry:
                # New format: dict with name and path
                # Ensure path key exists
                path = entry.get("path", "")
                name = entry["name"]
                if name and name.strip():
                    normalized.append({"name": name, "path": path})
        
        return normalized
    
    def get_project_history_names(self) -> list:
        """Get list of recent project names only (for backward compatibility).
        
        Returns:
            List of project name strings
        """
        history = self.get_project_history()
        return [entry["name"] for entry in history]
    
    # =================================================================
    # FFmpeg Encoding Methods
    # =================================================================
    
    def get_ffmpeg_encoding_params(self, quality_preset: str = None) -> list:
        """
        Get FFmpeg encoding parameters based on quality preset.
        
        Args:
            quality_preset: Optional override quality ("maximum", "high", "medium", "fast")
                          If None, uses current config["video_quality"]
        
        Returns:
            List of FFmpeg command-line arguments
        """
        # Determine which preset to use
        if quality_preset:
            preset_name = quality_preset
        elif self._config and "video_quality" in self._config:
            preset_name = self._config["video_quality"]
        else:
            preset_name = "maximum"  # Default fallback
        
        if preset_name not in self.FFMPEG_ENCODING_PRESETS:
            raise ValueError(f"Unknown quality preset: {preset_name}. "
                           f"Valid: {list(self.FFMPEG_ENCODING_PRESETS.keys())}")
        
        preset = self.FFMPEG_ENCODING_PRESETS[preset_name]
        
        return [
            "-c:v", "libx264",
            "-preset", preset["preset"],
            "-crf", preset["crf"],
            "-profile:v", preset["profile"],
            "-level", preset["level"],
        ]
    
    def get_quality_description(self, quality_preset: str = None) -> str:
        """Get human-readable description of quality preset."""
        preset_name = quality_preset or self.get('video_quality', 'maximum')
        if preset_name in self.FFMPEG_ENCODING_PRESETS:
            return self.FFMPEG_ENCODING_PRESETS[preset_name]["description"]
        return "Unknown quality preset"


# ============================================================================
# Backward Compatibility Wrappers
# ============================================================================
# These functions maintain compatibility with existing code that uses the old API.
# New code should use Config.instance() directly.
# ============================================================================

# Expose class constants as module-level for backward compatibility
DEFAULT_CONFIG = Config.DEFAULT_CONFIG
DEFAULT_APP_SETTINGS = Config.DEFAULT_APP_SETTINGS
FFMPEG_ENCODING_PRESETS = Config.FFMPEG_ENCODING_PRESETS
PROJECT_CONFIG_FILE = Config.PROJECT_CONFIG_FILE
APP_SETTINGS_DIR = Config.APP_SETTINGS_DIR
APP_SETTINGS_FILE = Config.APP_SETTINGS_FILE

def get_ffmpeg_encoding_params(quality_preset: str = None, config: dict = None) -> list:
    """Backward compatibility wrapper. New code should use Config.instance().get_ffmpeg_encoding_params()"""
    if config:
        # Create temp instance just for this call
        temp_config = Config()
        temp_config._config = config
        return temp_config.get_ffmpeg_encoding_params(quality_preset)
    return Config.instance().get_ffmpeg_encoding_params(quality_preset)

def get_quality_description(quality_preset: str = None) -> str:
    """Backward compatibility wrapper. New code should use Config.instance().get_quality_description()"""
    return Config.instance().get_quality_description(quality_preset)

def load_app_settings() -> dict:
    """Backward compatibility wrapper. New code should use Config.instance().load_app_settings()"""
    return Config.instance().load_app_settings()

def save_app_settings(settings: dict):
    """Backward compatibility wrapper. New code should use Config.instance().save_app_settings()"""
    Config.instance().save_app_settings(settings)

def add_to_project_history(project_name: str, project_path: str = None):
    """Backward compatibility wrapper. New code should use Config.instance().add_to_project_history()"""
    Config.instance().add_to_project_history(project_name, project_path)

def get_project_history() -> list:
    """Backward compatibility wrapper. New code should use Config.instance().get_project_history()
    Returns list of dicts with 'name' and 'path' keys.
    """
    return Config.instance().get_project_history()

def get_project_history_names() -> list:
    """Backward compatibility wrapper. New code should use Config.instance().get_project_history_names()
    Returns list of project name strings only.
    """
    return Config.instance().get_project_history_names()

def get_project_config_path(output_folder: str) -> Path:
    """Backward compatibility wrapper. New code should use Config.instance()._get_project_config_path()"""
    return Config.instance()._get_project_config_path(output_folder)

def load_config(output_folder: str = None) -> dict:
    """Backward compatibility wrapper. New code should use Config.instance().load()"""
    return Config.instance().load(output_folder)

def save_config(config: dict, output_folder: str):
    """Backward compatibility wrapper. New code should use Config.instance().save()"""
    Config.instance().set(config)
    Config.instance().save(output_folder)


# ============================================================================
# Module-level convenience: Shorthand for Config.instance()
# ============================================================================
# Usage: from slideshow.config import cfg
#        params = cfg.get_ffmpeg_encoding_params()
cfg = Config.instance()
