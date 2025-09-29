# origami_frame_transition.py
from .base_transition import BaseTransition
from abc import ABC, abstractmethod
from .utils import extract_frame, load_and_resize_image, save_frames_as_video

class OrigamiFrameTransition(BaseTransition, ABC):
    def __init__(self, duration=1.0, resolution=(1920,1080), fps=25):
        super().__init__(duration)
        self.resolution = resolution
        self.fps = fps

    @abstractmethod
    def render_frames(self, from_img, to_img):
        pass

    def render(self, from_slide, to_slide, output_path):
        from_img = from_slide.get_from_image()
        to_img = to_slide.get_to_image()
        frames = self.render_frames(from_img, to_img)
        save_frames_as_video(frames, output_path, fps=self.fps)
