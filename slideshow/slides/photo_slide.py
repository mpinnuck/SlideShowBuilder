try:
    # Try absolute import first (when run from main app)
    from slideshow.slides.slide_item import SlideItem
except ModuleNotFoundError:
    # Fall back to relative import (when run directly)
    from .slide_item import SlideItem
from pathlib import Path
import cv2
import numpy as np

class PhotoSlide(SlideItem):
    def render(self, output_path: Path, resolution=(640, 360), fps=30):
        print(f"Rendering photo slide: {self.path} -> {output_path}")
        img = cv2.imread(str(self.path))
        if img is None:
            raise ValueError(f"Could not load image: {self.path}")
        
        # Get original dimensions
        h, w = img.shape[:2]
        target_w, target_h = resolution
        print(f"Original size: {w}x{h}, Target: {target_w}x{target_h}")
        
        # Calculate scaling to fit within target while preserving aspect ratio
        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)
        print(f"Scaled size: {new_w}x{new_h}, Scale factor: {scale:.3f}")
        
        # Resize image maintaining aspect ratio
        resized = cv2.resize(img, (new_w, new_h))
        
        # Create black background with target resolution using NumPy
        result = np.zeros((target_h, target_w, 3), dtype=img.dtype)
        
        # Center the resized image on the black background
        y_offset = (target_h - new_h) // 2
        x_offset = (target_w - new_w) // 2
        result[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
        
        # Write video with proper codec
        fourcc = cv2.VideoWriter_fourcc(*'H264')  # Use H264 codec
        out = cv2.VideoWriter(str(output_path), fourcc, fps, resolution)
        
        if not out.isOpened():
            print("H264 codec not available, trying mp4v...")
            # Fallback to mp4v if H264 not available
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(str(output_path), fourcc, fps, resolution)
        
        if not out.isOpened():
            raise RuntimeError(f"Could not open video writer for {output_path}")
        
        frame_count = int(self.duration * fps)
        print(f"Writing {frame_count} frames for {self.duration}s duration")
        for _ in range(frame_count):
            out.write(result)
        out.release()
        print(f"Photo slide rendered successfully: {output_path}")
