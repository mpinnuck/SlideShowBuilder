from slideshow.config import load_config
from slideshow.slideshowmodel import Slideshow
from pathlib import Path

class SlideshowController:
    def __init__(self):
        self.progress_callback = None
        self.log_callback = None
    
    def register_progress_callback(self, progress_callback):
        """Register a callback for progress updates (current, total, message)"""
        self.progress_callback = progress_callback
    
    def register_log_callback(self, log_callback):
        """Register a callback for log messages"""
        self.log_callback = log_callback

    def export(self, config: dict):
        # Create slideshow model with provided config
        slideshow = Slideshow(config)
        
        output_path = Path(config["output_folder"]) / f"{config['project_name']}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        slideshow.render(output_path, self.progress_callback, self.log_callback)
        return output_path
