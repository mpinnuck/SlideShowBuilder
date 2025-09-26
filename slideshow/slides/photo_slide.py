from pathlib import Path
import cv2
import numpy as np
from slideshow.config import DEFAULT_CONFIG

class PhotoSlide:
    def __init__(self, path: Path, duration: float, fps: int = None, resolution: tuple = None):
        self.path = path
        self.duration = duration
        self.fps = fps if fps is not None else DEFAULT_CONFIG["fps"]
        self.resolution = resolution if resolution is not None else tuple(DEFAULT_CONFIG["resolution"])

    def render(self, output_path: Path, log_callback=None, progress_callback=None):

        if log_callback:
            log_callback(f"[Slideshow] Rendering slide: {self.path.name} ({self.duration:.2f}s, {self.fps} fps)")

        cap = cv2.imread(str(self.path))
        if cap is None:
            raise RuntimeError(f"Cannot load image: {self.path}")

        h, w = cap.shape[:2]
        if log_callback:
            log_callback(f"Rendering photo slide: {self.path} -> {output_path}\n"
                         f"Original size: {w}x{h}, Target: {self.resolution[0]}x{self.resolution[1]}")

        # --- Resize and pad ---
        target_w, target_h = self.resolution
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(cap, (new_w, new_h))

        top = (target_h - new_h) // 2
        bottom = target_h - new_h - top
        left = (target_w - new_w) // 2
        right = target_w - new_w - left
        framed = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(0, 0, 0))

        # --- Write video using CFR ---
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
        out = cv2.VideoWriter(str(output_path), fourcc, self.fps, (target_w, target_h))
        total_frames = int(self.fps * self.duration)

        for i in range(total_frames):
            out.write(framed)
            if progress_callback and (i % max(total_frames // 10, 1) == 0):
                progress_callback(i / total_frames)

        out.release()

        if log_callback:
            log_callback(f"Photo slide rendered successfully: {output_path} ({total_frames} frames @ {self.fps} fps)")
