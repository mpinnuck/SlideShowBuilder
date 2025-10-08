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
from slideshow.config import Config
import os
from slideshow.transitions.ffmpeg_cache import FFmpegCache
from slideshow.transitions.ffmpeg_paths import FFmpegPaths


class IntroTitle:
    def __init__(self):
        """Initialize intro title from global config."""
        cfg = Config.instance().get_all()
        self.settings = cfg.get("intro_title", {})
        self.enabled = self.settings.get("enabled", False)
        self.text = self.settings.get("text", "")
        self.duration = self.settings.get("duration", 5.0)
        self.font_path = self.settings.get("font_path", "/System/Library/Fonts/Arial.ttf")
        self.font_size = self.settings.get("font_size", 120)
        self.font_weight = self.settings.get("font_weight", "normal")
        self.line_spacing = self.settings.get("line_spacing", 1.2)  # Line spacing multiplier
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

        # Create cache key based on intro title settings and background
        import hashlib
        bg_hash = hashlib.md5(background_image.tobytes()).hexdigest()[:8]
        
        virtual_path = Path(f"intro_title_{bg_hash}")
        
        cache_params = {
            "operation": "intro_title_render", 
            "text": self.text,
            "duration": self.duration,
            "font_path": self.font_path,
            "font_size": self.font_size,
            "font_weight": self.font_weight,
            "line_spacing": self.line_spacing,
            "text_color": self.text_color,
            "shadow_color": self.shadow_color,
            "shadow_offset": self.shadow_offset,
            "rotation_axis": self.rotation_axis,
            "clockwise": self.clockwise,
            "fps": self.fps,
            "resolution": self.resolution,
            "background_hash": bg_hash
        }
        
        # Check cache first
        cached_intro = FFmpegCache.get_cached_clip(virtual_path, cache_params)
        if cached_intro:
            # Copy cached intro to output path
            import shutil
            shutil.copy2(cached_intro, output_path)
            return output_path

        # Ensure background matches target resolution
        bg = background_image.convert("RGBA").resize(self.resolution)
        
        # Load font with smart weight-based selection
        font = self._load_font_with_weight()

        # Pre-render the text once to avoid font rendering on every frame
        text_img = self._create_text_image(font)
        
        rotation_duration = 6.0  # 6 seconds of rotation
        rotation_frames = int(rotation_duration * self.fps)
        static_duration = self.duration - rotation_duration  # remaining time is static
        
        # Angle step for 360° rotation in 6 seconds
        angle_step = (360 / rotation_frames) * (-1 if self.clockwise else 1)

        # Use FFmpeg pipe for direct frame streaming (much faster than temp files)
        cmd = [
            FFmpegPaths.ffmpeg(), "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
            "-s", f"{self.resolution[0]}x{self.resolution[1]}",
            "-pix_fmt", "rgba", "-r", str(self.fps), "-i", "-",
        ]
        cmd.extend(Config.instance().get_ffmpeg_encoding_params())  # Use project quality settings
        cmd.extend([
            "-pix_fmt", "yuv420p",
            str(output_path)
        ])
        
        # Start FFmpeg process
        ffmpeg_process = subprocess.Popen(cmd, stdin=subprocess.PIPE, 
                                        stdout=subprocess.DEVNULL, 
                                        stderr=subprocess.DEVNULL)
        
        try:
            # Render rotating frames (6 seconds)
            for i in range(rotation_frames):
                frame_angle = i * angle_step
                frame = self._render_frame_optimized(bg, text_img, frame_angle)
                # Convert to raw RGBA bytes and send to FFmpeg
                ffmpeg_process.stdin.write(frame.tobytes())
            
            # For static frames, render once and repeat using FFmpeg
            if static_duration > 0:
                # Render final static frame
                final_angle = 360 if self.clockwise else -360
                static_frame = self._render_frame_optimized(bg, text_img, final_angle)
                static_frame_bytes = static_frame.tobytes()
                
                # Send the same frame multiple times for static duration
                static_frames = int(static_duration * self.fps)
                for _ in range(static_frames):
                    ffmpeg_process.stdin.write(static_frame_bytes)
            
            # Close stdin to signal end of input
            ffmpeg_process.stdin.close()
            ffmpeg_process.wait()
            
            if ffmpeg_process.returncode != 0:
                raise RuntimeError("FFmpeg failed during intro title rendering")
                
        except Exception as e:
            ffmpeg_process.terminate()
            ffmpeg_process.wait()
            raise e

        # Store result in cache for future use
        FFmpegCache.store_clip(virtual_path, cache_params, output_path)

        return output_path

    def _load_font_with_weight(self):
        """Load font with smart fallbacks based on font weight setting and user config."""
        import os
        
        # Start with user-configured font path
        primary_font = self.font_path if self.font_path else "/System/Library/Fonts/Arial.ttf"
        
        # Font weight to font file mapping for macOS (as fallbacks)
        fallback_fonts = {
            "light": [
                "/System/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf"
            ],
            "normal": [
                "/System/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc", 
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf"
            ],
            "bold": [
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/System/Library/Fonts/Arial Bold.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "/Library/Fonts/Arial Bold.ttf"
            ]
        }
        
        # Create list of fonts to try: user font first, then fallbacks
        fonts_to_try = [primary_font] + fallback_fonts.get(self.font_weight, fallback_fonts["normal"])
        
        # Try each font path until one works
        for font_path in fonts_to_try:
            if font_path and os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, self.font_size)
                except (OSError, IOError) as e:
                    print(f"Failed to load font {font_path}: {e}")
                    continue
        
        # Final fallback to default font
        print(f"Warning: Could not load any specified fonts, using default")
        try:
            return ImageFont.load_default()
        except:
            # Create a very basic font as absolute last resort  
            return ImageFont.load_default()

    def _create_text_image(self, font: ImageFont.FreeTypeFont) -> Image.Image:
        """Pre-render the text to a transparent image for reuse, supporting multi-line text."""
        # Split text into lines, supporting both \n and actual line breaks
        lines = self.text.replace('\\n', '\n').split('\n')
        
        # Calculate line height with spacing
        line_height = int(font.size * self.line_spacing)
        
        # Calculate total dimensions needed
        max_width = 0
        total_height = 0
        
        temp_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        
        # Measure each line
        line_widths = []
        for line in lines:
            if line.strip():  # Skip empty lines for width calculation
                bbox = temp_draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
                line_widths.append(line_width)
                max_width = max(max_width, line_width)
            else:
                line_widths.append(0)
        
        # Calculate total height
        total_height = len(lines) * line_height
        if len(lines) > 1:
            total_height -= int(line_height * (1 - self.line_spacing))  # Adjust for last line
        
        # Create properly sized text image with padding
        padding = 20
        text_img = Image.new("RGBA", (max_width + padding * 2, total_height + padding * 2), (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_img)
        
        # Draw each line with shadow and text
        y_offset = padding
        for i, line in enumerate(lines):
            if line.strip():  # Only draw non-empty lines
                # Center each line horizontally
                line_width = line_widths[i]
                x_offset = padding + (max_width - line_width) // 2
                
                # Draw shadow
                shadow_pos = (x_offset + self.shadow_offset[0], y_offset + self.shadow_offset[1])
                text_draw.text(shadow_pos, line, font=font, fill=self.shadow_color)
                
                # Draw text
                text_draw.text((x_offset, y_offset), line, font=font, fill=self.text_color)
            
            y_offset += line_height
        
        return text_img

    def _render_frame_optimized(self, background: Image.Image, text_img: Image.Image, angle: float) -> np.ndarray:
        """Optimized frame rendering that reuses pre-rendered text."""
        frame = background.copy()
        
        # Apply 3D rotation to pre-rendered text
        rotated_text = self._rotate_3d(text_img, angle)
        
        # Center the rotated text on the frame
        text_w, text_h = rotated_text.size
        paste_x = (self.resolution[0] - text_w) // 2
        paste_y = (self.resolution[1] - text_h) // 2
        
        frame.alpha_composite(rotated_text, (paste_x, paste_y))
        
        # Convert to numpy array for FFmpeg
        return np.array(frame)

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
        Apply Y-axis rotation (horizontal plane rotation into/out of frame).
        The text rotates around a vertical axis through its center.
        
        Rotation phases:
        0°-90°: Forward text, getting narrower
        90°-180°: Backwards (mirrored) text, getting wider
        180°-270°: Backwards (mirrored) text, getting narrower  
        270°-360°: Forward text, getting wider
        """
        if angle == 0:
            return img
            
        w, h = img.size
        
        # Normalize angle to 0-360 range
        normalized_angle = angle % 360
        rad = math.radians(normalized_angle)
        
        # Calculate horizontal scaling factor based on cosine of rotation angle
        cos_angle = math.cos(rad)
        scale_factor = abs(cos_angle)
        
        # Prevent the text from disappearing completely when edge-on
        min_scale = 0.02  # Keep at least 2% width when edge-on
        scale_factor = max(min_scale, scale_factor)
        
        # Determine if text should be mirrored (facing away from viewer)
        # Between 90° and 270°, the text is facing away and should be mirrored
        should_mirror = 90 <= normalized_angle <= 270
        
        # Calculate new width with perspective scaling
        new_width = int(w * scale_factor)
        
        # Create result image with original dimensions
        result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        
        if new_width > 0:
            # Start with original image
            working_img = img.copy()
            
            # Mirror the text if it's facing away from viewer
            if should_mirror:
                working_img = working_img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            
            # Scale the image horizontally to simulate Y-axis rotation
            scaled = working_img.resize((new_width, h), Image.LANCZOS)
            
            # Center the scaled image horizontally
            paste_x = (w - new_width) // 2
            result.paste(scaled, (paste_x, 0), scaled)
            
            # Add subtle depth shading for more realistic 3D effect
            # Make it slightly darker when viewed from an angle
            if scale_factor < 0.9:  # When not facing directly forward
                overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                
                # Calculate shading based on how much it's angled away
                # More angled = darker
                shading_strength = int((1.0 - scale_factor) * 40)  # 0-40 alpha
                shade_color = (0, 0, 0, shading_strength)
                
                # Apply shading to the text area
                if new_width > 0:
                    overlay_draw.rectangle([paste_x, 0, paste_x + new_width, h], fill=shade_color)
                
                # Composite the shading
                result = Image.alpha_composite(result, overlay)
        
        return result
    