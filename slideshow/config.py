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
    "fps": 30,
    "resolution": [640, 360]
}

CONFIG_FILE = Path("slideshow_config.json")

def load_config(path: Path = CONFIG_FILE) -> dict:
    if not path.exists():
        return DEFAULT_CONFIG.copy()
    with open(path, "r") as f:
        return json.load(f)

def save_config(config: dict, path: Path = CONFIG_FILE):
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
