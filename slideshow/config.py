import json
from pathlib import Path
import os

# Global app settings directory
APP_SETTINGS_DIR = Path.home() / "SlideshowBuilder"
APP_SETTINGS_FILE = APP_SETTINGS_DIR / "slideshow_settings.json"

# Default app-level settings
DEFAULT_APP_SETTINGS = {
    "last_project_path": "",
    "project_history": []  # List of recent project names (strings), newest first (max 10)
}

# Default project-level settings
DEFAULT_CONFIG = {
    "project_name": "MyProject",
    "input_folder": str(Path.home() / "SlideshowBuilder" / "MyProject" / "Slides"),
    "output_folder": str(Path.home() / "SlideshowBuilder" / "MyProject" / "Output"),
    "photo_duration": 3.0,
    "video_duration": 5.0,
    "transition_duration": 1.0,
    "transition_type": "fade",
    "fps": 30,  # ✅ Default for Apple devices
    "resolution": [1920, 1080],  # ✅ Default to Full HD
    
    # Origami transition settings
    "origami_easing": "quad",
    "origami_lighting": True,
    "origami_fold": "",  # Empty means random
    
    # Multislide settings
    "multislide_frequency": 5,  # Create composite slide after N slides (photos + videos, 0 = disabled)
    
    # Video quality settings
    "video_quality": "maximum",  # Encoding quality: "maximum", "high", "medium", "fast"
    
    # Intro title settings
    "intro_title": {
        "enabled": False,
        "text": "Project Title\nHere",
        "duration": 5.0,
        "font_path": "/System/Library/Fonts/Arial.ttf",  # User-configurable font path
        "font_size": 120,
        "font_weight": "normal",  # "normal", "bold", "light" - affects font selection
        "line_spacing": 1.2,  # Line spacing multiplier (1.0 = single spacing, 1.5 = 1.5x spacing)
        "text_color": [255, 255, 255, 255],
        "shadow_color": [0, 0, 0, 180],
        "shadow_offset": [4, 4],
        "rotation": {
            "axis": "y",
            "clockwise": True
        }
    },
    
    # Advanced settings
    "hardware_acceleration": False,
    "temp_directory": "",
    "auto_cleanup": True,
    "keep_intermediate_frames": False
}

# ============================================================================
# FFmpeg Encoding Quality Presets
# ============================================================================
# Centralized video encoding parameters for consistent quality across all
# FFmpeg operations (final assembly, transitions, multi-slides, etc.)
#
# Quality Levels:
#   "maximum"  - Visually lossless, large file size, slow encoding (~18-25 Mbps)
#   "high"     - Excellent quality, good compression, balanced speed (~12-18 Mbps)
#   "medium"   - Good quality, smaller files, faster encoding (~8-12 Mbps)
#   "fast"     - Acceptable quality, small files, very fast (~5-8 Mbps)
#
# To change quality globally: Update FFMPEG_QUALITY_PRESET
# ============================================================================

FFMPEG_QUALITY_PRESET = "maximum"  # Change this to adjust all encoding quality

FFMPEG_ENCODING_PRESETS = {
    "maximum": {
        # Visually lossless quality - best for archival and USB playback
        "crf": "18",              # Lower = better quality (18 = near lossless)
        "preset": "slow",         # Encoding speed: slower = better compression
        "profile": "high",        # H.264 profile (high = most features)
        "level": "4.1",          # H.264 level (4.1 = supports higher bitrates)
        "description": "Maximum quality - visually lossless, ~18-25 Mbps"
    },
    "high": {
        # Excellent quality with good compression - recommended for most uses
        "crf": "20",
        "preset": "medium",
        "profile": "high",
        "level": "4.1",
        "description": "High quality - excellent balance, ~12-18 Mbps"
    },
    "medium": {
        # Good quality with smaller file size - good for streaming
        "crf": "23",
        "preset": "medium",
        "profile": "main",
        "level": "4.0",
        "description": "Medium quality - good compression, ~8-12 Mbps"
    },
    "fast": {
        # Acceptable quality, fast encoding - for testing/preview
        "crf": "25",
        "preset": "fast",
        "profile": "main",
        "level": "4.0",
        "description": "Fast encoding - smaller files, ~5-8 Mbps"
    }
}

def get_ffmpeg_encoding_params(quality_preset: str = None, config: dict = None) -> list:
    """
    Get FFmpeg encoding parameters for the specified quality preset.
    
    Args:
        quality_preset: Quality level ("maximum", "high", "medium", "fast")
                       If None, uses config["video_quality"] or FFMPEG_QUALITY_PRESET
        config: Project configuration dictionary (optional)
    
    Returns:
        List of FFmpeg command-line arguments for video encoding
        
    Example:
        cmd = [FFmpegPaths.ffmpeg(), "-i", input_file]
        cmd.extend(get_ffmpeg_encoding_params(config=self.config))
        cmd.extend(["-pix_fmt", "yuv420p", output_file])
    """
    # Determine which preset to use
    if quality_preset:
        preset_name = quality_preset
    elif config and "video_quality" in config:
        preset_name = config["video_quality"]
    else:
        preset_name = FFMPEG_QUALITY_PRESET
    
    if preset_name not in FFMPEG_ENCODING_PRESETS:
        raise ValueError(f"Unknown quality preset: {preset_name}. "
                        f"Valid options: {list(FFMPEG_ENCODING_PRESETS.keys())}")
    
    preset = FFMPEG_ENCODING_PRESETS[preset_name]
    
    return [
        "-c:v", "libx264",
        "-preset", preset["preset"],
        "-crf", preset["crf"],
        "-profile:v", preset["profile"],
        "-level", preset["level"],
    ]

def get_quality_description(quality_preset: str = None) -> str:
    """Get human-readable description of the current quality preset."""
    preset_name = quality_preset or FFMPEG_QUALITY_PRESET
    if preset_name in FFMPEG_ENCODING_PRESETS:
        return FFMPEG_ENCODING_PRESETS[preset_name]["description"]
    return "Unknown quality preset"

# Project config file name (stored in output folder)
PROJECT_CONFIG_FILE = "slideshow_config.json"

def load_app_settings() -> dict:
    """
    Load global app settings from ~/SlideshowBuilder/slideshow_settings.json
    Contains last project path and other app-level preferences.
    """
    settings = DEFAULT_APP_SETTINGS.copy()
    
    if APP_SETTINGS_FILE.exists():
        try:
            with open(APP_SETTINGS_FILE, "r") as f:
                user_settings = json.load(f)
                if isinstance(user_settings, dict):
                    settings.update(user_settings)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Config] WARNING: Failed to load app settings ({e}), using defaults.")
    
    return settings

def save_app_settings(settings: dict):
    """
    Save global app settings to ~/SlideshowBuilder/slideshow_settings.json
    """
    # Ensure directory exists
    APP_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    
    merged = DEFAULT_APP_SETTINGS.copy()
    merged.update(settings)
    
    try:
        with open(APP_SETTINGS_FILE, "w") as f:
            json.dump(merged, f, indent=2)
    except OSError as e:
        print(f"[Config] WARNING: Failed to save app settings ({e})")

def add_to_project_history(project_name: str):
    """
    Add a project name to the history list, maintaining the last 10 projects.
    
    Args:
        project_name: Name of the project
    """
    if not project_name:
        return
    
    settings = load_app_settings()
    history = settings.get("project_history", [])
    
    # Ensure history is a list (handle old format)
    if not isinstance(history, list):
        history = []
    
    # Remove if already exists (to move to top)
    history = [name for name in history if isinstance(name, str) and name != project_name]
    
    # Add to front
    history.insert(0, project_name)
    
    # Keep only last 10
    history = history[:10]
    
    # Update settings
    settings["project_history"] = history
    save_app_settings(settings)

def get_project_history() -> list:
    """
    Get the list of recent project names.
    
    Returns:
        List of project name strings
    """
    settings = load_app_settings()
    history = settings.get("project_history", [])
    
    # Ensure we only return valid strings (handle old format)
    if not isinstance(history, list):
        return []
    
    return [name for name in history if isinstance(name, str) and name.strip()]

def get_project_config_path(output_folder: str) -> Path:
    """
    Get the path to the project config file in the output folder.
    """
    if not output_folder:
        return Path(PROJECT_CONFIG_FILE)  # Fallback to current directory
    
    output_path = Path(output_folder)
    return output_path / PROJECT_CONFIG_FILE

def load_config(output_folder: str = None) -> dict:
    """
    Load project config from slideshow_config.json in the output folder.
    If output_folder is not specified, tries to load from last project.
    User-specified values override defaults, but missing keys are filled from defaults.
    """
    config = DEFAULT_CONFIG.copy()
    
    # Determine config path
    if output_folder:
        config_path = get_project_config_path(output_folder)
    else:
        # Try to load from last project
        app_settings = load_app_settings()
        last_project = app_settings.get("last_project_path", "")
        if last_project:
            config_path = Path(last_project)
        else:
            config_path = Path(PROJECT_CONFIG_FILE)  # Fallback to current directory
    
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                user_config = json.load(f)
                if isinstance(user_config, dict):
                    config.update(user_config)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Config] WARNING: Failed to load config from {config_path} ({e}), using defaults.")
    
    return config

def save_config(config: dict, output_folder: str):
    """
    Save project configuration to slideshow_config.json in the output folder.
    Also updates the app settings to remember this as the last project.
    If the output folder is new, creates it with ffmpeg_cache structure.
    """
    if not output_folder:
        print("[Config] WARNING: No output folder specified, cannot save config")
        return
    
    # Get project config path
    config_path = get_project_config_path(output_folder)
    
    # Check if this is a new output folder
    is_new_folder = not config_path.parent.exists()
    
    # Ensure output folder exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # If this is a new folder, create the ffmpeg_cache structure
    if is_new_folder:
        cache_dir = config_path.parent / "working" / "ffmpeg_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Config] Created new project folder structure with cache at: {cache_dir}")
    
    # Merge with defaults and save
    merged = DEFAULT_CONFIG.copy()
    merged.update(config)
    
    try:
        with open(config_path, "w") as f:
            json.dump(merged, f, indent=2)
        
        # Update app settings to remember this project
        app_settings = load_app_settings()
        app_settings["last_project_path"] = str(config_path)
        save_app_settings(app_settings)
        
    except OSError as e:
        print(f"[Config] WARNING: Failed to save config to {config_path} ({e})")
