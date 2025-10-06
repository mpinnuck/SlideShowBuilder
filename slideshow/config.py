import json
from pathlib import Path

DEFAULT_CONFIG = {
    "project_name": "MyProject",
    "input_folder": "media/input",
    "output_folder": "media/output",
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
    "multislide_frequency": 10,  # Create composite slide every N slides (0 = disabled)
    
    # Intro title settings
    "intro_title": {
        "enabled": False,
        "text": "",
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

CONFIG_FILE = Path("slideshow_config.json")

def load_config(path: Path = CONFIG_FILE) -> dict:
    """
    Load config from JSON file and merge with DEFAULT_CONFIG to ensure all keys exist.
    User-specified values override defaults, but missing keys are filled from defaults.
    """
    config = DEFAULT_CONFIG.copy()
    if path.exists():
        try:
            with open(path, "r") as f:
                user_config = json.load(f)
                if isinstance(user_config, dict):
                    config.update(user_config)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Config] WARNING: Failed to load config ({e}), using defaults.")
    return config

def save_config(config: dict, path: Path = CONFIG_FILE):
    """
    Save configuration to disk. Missing keys will not be stripped — 
    we always persist a complete config merged with defaults.
    """
    merged = DEFAULT_CONFIG.copy()
    merged.update(config)
    with open(path, "w") as f:
        json.dump(merged, f, indent=2)
