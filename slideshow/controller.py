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
        """Build and export slideshow based on the given config"""
        output_path = Path(config["output_folder"]) / f"{config['project_name']}.mp4"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            slideshow = Slideshow(config, log_callback=self.log_callback, progress_callback=self.progress_callback)
            slideshow.render(output_path)
            if self.log_callback:
                self.log_callback(f"[Controller] Slideshow successfully exported → {output_path}")
            return output_path
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"[Controller] Export failed: {e}")
            raise
