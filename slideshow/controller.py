from slideshow.config import load_config
from slideshow.slideshowmodel import Slideshow
from pathlib import Path

class SlideshowController:
    def __init__(self):
        self.config = load_config()
        self.slideshow = Slideshow(self.config)
        self.progress_callback = None
        self.log_callback = None
    
    def register_progress_callback(self, progress_callback):
        """Register a callback for progress updates (current, total, message)"""
        self.progress_callback = progress_callback
    
    def register_log_callback(self, log_callback):
        """Register a callback for log messages"""
        self.log_callback = log_callback

    def export(self):
        def progress_handler(current, total, message=None):
            if self.progress_callback:
                self.progress_callback(current, total)
            if message and self.log_callback:
                self.log_callback(message)
        
        output_path = Path(self.config["output_folder"]) / f"{self.config['project_name']}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.slideshow.render(output_path, progress_handler)
        return output_path
