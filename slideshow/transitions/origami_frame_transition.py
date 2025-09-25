# origami_frame_transition.py
from .base_transition import BaseTransition
from abc import ABC, abstractmethod
from .utils import extract_frame, load_and_resize_image, save_frames_as_video

class OrigamiFrameTransition(BaseTransition, ABC):
    def __init__(self, duration=1.0, resolution=(1920,1080), fps=25):
        super().__init__(duration)
        self.resolution = resolution
        self.fps = fps

    def _prepare_images(self, from_path, to_path):
        from_img = load_and_resize_image(
            extract_frame(from_path, last=True) if self._is_video(from_path) else from_path,
            self.resolution)
        to_img = load_and_resize_image(
            extract_frame(to_path, last=False) if self._is_video(to_path) else to_path,
            self.resolution)
        return from_img, to_img

    def _is_video(self, path):
        return str(path).lower().endswith((".mov", ".mp4", ".m4v"))

    @abstractmethod
    def render_frames(self, from_img, to_img):
        pass

    def render(self, from_path, to_path, output_path):
        from_img, to_img = self._prepare_images(from_path, to_path)
        frames = self.render_frames(from_img, to_img)
        save_frames_as_video(frames, output_path, fps=self.fps)
