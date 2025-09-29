#!/usr/bin/env python3
"""
intro_title.py
--------------
Renders a rotating 3D text intro over the first frame of the first slide.

Configuration is loaded from the project's config.json.
"""

import tempfile
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import math
import os
import slideshow.config  


class IntroTitle:
    def __init__(self):
        """Initialize intro title from global config."""
        cfg = slideshow.config.load_config()
        self.settings = cfg.get("intro_title", {})
        self.enabled = self.settings.get("enabled", False)
        self.text = self.settings.get("text", "")
        self.duration = self.settings.get("duration", 5.0)
        self.font_path = self.settings.get("font_path", "/System/Library/Fonts/Supplemental/Arial Bold.ttf")
        self.font_size = self.settings.get("font_size", 120)
        self.text_color = tuple(self.settings.get("text_color", [255, 255, 255, 255]))
        self.shadow_color = tuple(self.settings.get("shadow_color", [0, 0, 0, 180]))
        self.shadow_offset = tuple(self.settings.get("shadow_offset", [4, 4]))
        self.rotation_axis = self.settings.get("rotation", {}).get("axis", "y")
        self.clockwise = self.settings.get("rotation", {}).get("clockwise", True)
        self.fps = cfg.get("fps", 30)
        self.resolution = tuple(cfg.get("resolution", [1920, 1080]))

    def render(self, background_image: Image.Image, output_path: Path):
        """
        Render the intro title over a static background image.

        Args:
            background_image (PIL.Image): Frame to use as background.
            output_path (Path): Path where the intro video will be saved.
        """
        if not self.enabled:
            return None

        # Ensure background matches target resolution
        bg = background_image.convert("RGBA").resize(self.resolution)

        font = ImageFont.truetype(self.font_path, self.font_size)

        total_frames = int(self.duration * self.fps)
        angle_step = (360 / total_frames) * (-1 if self.clockwise else 1)

        tmp_dir = tempfile.mkdtemp(prefix="intro_title_")
        for i in range(total_frames):
            frame_angle = i * angle_step
            frame = self._render_frame(bg, font, frame_angle)
            frame_path = Path(tmp_dir) / f"frame_{i:06d}.png"
            frame.save(frame_path, format="PNG")

        # Encode with ffmpeg
        cmd = [
            "ffmpeg", "-y", "-r", str(self.fps),
            "-i", f"{tmp_dir}/frame_%06d.png",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-crf", "18", str(output_path)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Clean up frames
        for f in Path(tmp_dir).glob("frame_*.png"):
            f.unlink()
        os.rmdir(tmp_dir)

        return output_path

    def _render_frame(self, background: Image.Image, font: ImageFont.FreeTypeFont, angle: float) -> Image.Image:
        """Render a single frame with rotated text."""
        frame = background.copy()
        draw = ImageDraw.Draw(frame)

        # Create text as separate image (so we can rotate cleanly)
        text_img = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_img)

        text_bbox = text_draw.textbbox((0, 0), self.text, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]
        text_x = (self.resolution[0] - text_w) // 2
        text_y = (self.resolution[1] - text_h) // 2

        # Shadow first
        shadow_pos = (text_x + self.shadow_offset[0], text_y + self.shadow_offset[1])
        text_draw.text(shadow_pos, self.text, font=font, fill=self.shadow_color)
        text_draw.text((text_x, text_y), self.text, font=font, fill=self.text_color)

        # Apply a fake 3D rotation effect using affine transform (skew horizontally)
        rotated = self._rotate_3d(text_img, angle)
        frame.alpha_composite(rotated)
        return frame

    def _rotate_3d(self, img: Image.Image, angle: float) -> Image.Image:
        """
        Simulate 3D rotation by applying horizontal skew scaling.
        This is a visual trick since true 3D would require OpenGL.
        """
        w, h = img.size
        rad = math.radians(angle)
        scale = abs(math.cos(rad))  # squash horizontally based on angle
        new_w = int(w * scale)
        if new_w < 1:
            new_w = 1
        return img.resize((new_w, h), Image.BICUBIC).crop((0, 0, w, h)).transpose(Image.Transpose.FLIP_LEFT_RIGHT if self.clockwise else Image.Transpose.FLIP_TOP_BOTTOM)
    