# slideshow/transitions/origami_fold_multi_slide.py

import numpy as np
import moderngl
from PIL import Image, ImageEnhance, ImageDraw, ImageFont
from slideshow.transitions.origami_frame_transition import OrigamiFrameTransition
from slideshow.transitions.origami_render import draw_fullscreen_image, render_flap_fold


class OrigamiFoldMultiSlide(OrigamiFrameTransition):
    """
    Multi-slide origami transition that creates a composite preview showing the next slides.
    Uses context-aware rendering to access multiple future slides.
    The destination frame shows:
    - Main slide (next): Left 80% of canvas, full height  
    - Preview slide 2: Right 20%, top half
    - Preview slide 3: Right 20%, bottom half
    If fewer than 4 slides available, falls back to normal left-to-right transition.
    """
    
    def __init__(self, easing="quad", lighting=True, **kwargs):
        super().__init__(**kwargs)
        self.easing = easing
        self.lighting = lighting

    def get_requirements(self):
        return ["moderngl", "numpy", "Pillow", "ffmpeg"]

    def render(self, slide_index: int, slides: list, output_path) -> int:
        """
        Render method that can access multiple slides for composite preview.
        
        Args:
            slide_index: Current slide index in the slideshow
            slides: Array of all slides
            output_path: Output file path for the transition
            
        Returns:
            Number of slides consumed by this transition (1 for normal, 3 for multi-slide)
        """
        remaining_slides = len(slides) - slide_index - 1
        
        # Check if we have enough slides for multi-slide transition (need at least 3 more)
        if remaining_slides < 3:
            # Fall back to normal left-to-right transition
            return self._render_normal_transition(slides[slide_index], slides[slide_index + 1], output_path)
        
        # Multi-slide transition: use slides i+1, i+2, i+3 to create composite
        from_slide = slides[slide_index]
        main_slide = slides[slide_index + 1]
        preview_slide2 = slides[slide_index + 2] 
        preview_slide3 = slides[slide_index + 3]
        
        # Create composite destination and render multi-slide transition
        self._render_multi_slide_transition(from_slide, main_slide, preview_slide2, preview_slide3, output_path)
        
        # Return 3 to skip the next 2 slides (since we consumed them in the composite)
        return 3

    def _render_normal_transition(self, from_slide, to_slide, output_path):
        """Render a normal left-to-right fold transition."""
        # Use the standard render method for normal transition
        self.render(from_slide, to_slide, output_path)
        return 1

    def _create_composite_destination(self, main_slide, preview_slide2, preview_slide3):
        """
        Create a composite destination frame with main slide + 2 preview slides.
        
        Args:
            main_slide: PIL Image for the main (next) slide  
            preview_slide2: Slide object for the second preview slide
            preview_slide3: Slide object for the third preview slide
        
        Returns:
            PIL Image of the composite destination
        """
        width, height = main_slide.size
        
        # Create a new composite image
        composite = Image.new('RGB', (width, height), (0, 0, 0))
        
        # Main slide: Left 80% of canvas, full height
        main_width = int(width * 0.8)
        main_resized = main_slide.resize((main_width, height), Image.Resampling.LANCZOS)
        composite.paste(main_resized, (0, 0))
        
        # Preview area: Right 20% of canvas
        preview_width = width - main_width
        preview_height = height // 2
        
        # Preview slide 2: Right 20%, top half
        preview2_img = preview_slide2.get_from_image()
        preview2_resized = preview2_img.resize((preview_width, preview_height), Image.Resampling.LANCZOS)
        
        # Apply slight brightness adjustment to differentiate
        enhancer = ImageEnhance.Brightness(preview2_resized)
        preview2_resized = enhancer.enhance(0.8)  # Slightly darker
        composite.paste(preview2_resized, (main_width, 0))
        
        # Preview slide 3: Right 20%, bottom half  
        preview3_img = preview_slide3.get_from_image()
        preview3_resized = preview3_img.resize((preview_width, preview_height), Image.Resampling.LANCZOS)
        
        # Apply color saturation adjustment
        enhancer = ImageEnhance.Color(preview3_resized)
        preview3_resized = enhancer.enhance(0.7)  # Less saturated
        composite.paste(preview3_resized, (main_width, preview_height))
        
        # Add subtle borders to separate the preview areas
        draw = ImageDraw.Draw(composite)
        
        # Vertical border between main and preview
        border_color = (64, 64, 64)  # Dark gray
        border_width = 2
        for i in range(border_width):
            draw.line([(main_width + i, 0), (main_width + i, height)], fill=border_color)
        
        # Horizontal border between preview slides
        mid_y = height // 2
        for i in range(border_width):
            draw.line([(main_width, mid_y + i), (width, mid_y + i)], fill=border_color)
        
        return composite

    def _render_multi_slide_transition(self, from_slide, main_slide, preview_slide2, preview_slide3, output_path):
        """Render the multi-slide transition with composite destination."""
        # Get from image
        from_img = from_slide.get_from_image()
        main_img = main_slide.get_from_image()
        
        # Create composite destination
        composite_img = self._create_composite_destination(main_img, preview_slide2, preview_slide3)
        
        # Create ModernGL context
        ctx = moderngl.create_context(standalone=True, require=330)
        
        # Create textures
        from_tex = ctx.texture(from_img.size, 3, np.array(from_img.convert("RGB")).tobytes())
        to_tex = ctx.texture(composite_img.size, 3, np.array(composite_img.convert("RGB")).tobytes())
        
        # Render the transition frames using left-to-right fold
        frames = self._render_left_right_fold(ctx, from_tex, to_tex, from_img.size)
        
        # Save frames as video
        self._save_frames_as_video(frames, output_path)

    def _render_left_right_fold(self, ctx, from_tex, to_tex, size):
        """Render left-to-right origami fold transition."""
        width, height = size
        frames = []
        
        # Calculate frames using configured duration
        total_frames = int(self.duration * self.fps)
        
        # Use render_flap_fold for the left-to-right transition
        fold_frames = render_flap_fold(ctx, from_tex, to_tex,
                                     width, height,
                                     0.0, width, 0.0, height, seam_x=width/2,
                                     num_frames=total_frames,
                                     previous_frame=None,
                                     easing=self.easing,
                                     lighting=self.lighting)
        
        return fold_frames

    def _save_frames_as_video(self, frames, output_path):
        """Save frames as MP4 video using ffmpeg."""
        import subprocess
        import tempfile
        import os
        
        # Create temporary directory for frames
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save frames as images
            for i, frame in enumerate(frames):
                frame_path = os.path.join(temp_dir, f"frame_{i:04d}.png")
                Image.fromarray(frame).save(frame_path)
            
            # Use ffmpeg to create video
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-framerate", str(self.fps),
                "-i", os.path.join(temp_dir, "frame_%04d.png"),
                "-c:v", "libx264",
                "-preset", "fast",
                "-pix_fmt", "yuv420p",
                str(output_path)
            ]
            
            subprocess.run(ffmpeg_cmd, check=True, capture_output=True)

    def render_phase1_frames(self, ctx, from_img, to_img, num_frames: int):
        """
        Legacy render method for backward compatibility.
        This will create a simple composite using the same slide for preview.
        """
        # For legacy compatibility, create simple composite
        composite_img = self._create_simple_composite(to_img)
        
        # Create textures
        from_tex = ctx.texture(from_img.size, 3, np.array(from_img.convert("RGB")).tobytes())
        to_tex = ctx.texture(composite_img.size, 3, np.array(composite_img.convert("RGB")).tobytes())
        
        # Render simple left-to-right fold
        return self._render_left_right_fold(ctx, from_tex, to_tex, from_img.size)

    def _create_simple_composite(self, main_slide):
        """Create a simple composite using the same slide for preview areas."""
        width, height = main_slide.size
        composite = Image.new('RGB', (width, height), (0, 0, 0))
        
        # Main slide: Left 80%
        main_width = int(width * 0.8)
        main_resized = main_slide.resize((main_width, height), Image.Resampling.LANCZOS)
        composite.paste(main_resized, (0, 0))
        
        # Preview areas: Use same slide with effects
        preview_width = width - main_width
        preview_height = height // 2
        
        # Top preview (darkened)
        preview_resized = main_slide.resize((preview_width, preview_height), Image.Resampling.LANCZOS)
        enhancer = ImageEnhance.Brightness(preview_resized)
        preview_resized = enhancer.enhance(0.6)
        composite.paste(preview_resized, (main_width, 0))
        
        # Bottom preview (desaturated)
        preview_resized = main_slide.resize((preview_width, preview_height), Image.Resampling.LANCZOS)
        enhancer = ImageEnhance.Color(preview_resized)
        preview_resized = enhancer.enhance(0.4)
        composite.paste(preview_resized, (main_width, preview_height))
        
        return composite

    def render_phase2_frames(self, ctx, from_img, to_img, num_frames: int):
        return []
        frames.append(frame0.copy())

        # Calculate frames using configured duration
        total_frames = int(self.duration * self.fps)
        
        print(f"Multi-slide timing: {total_frames} total frames")
        
        previous_frame = frame0

        # Apply a left-to-right origami fold to reveal the composite destination
        fold_frames = render_flap_fold(ctx, from_tex, to_tex,
                                   width, height,
                                   -1.0, 0.0, 0.0, 1.0, seam_x=0.0,  # Fold from left edge
                                   num_frames=total_frames,
                                   previous_frame=previous_frame,
                                   easing=self.easing,
                                   lighting=self.lighting)
        frames += fold_frames

        return frames

    def render_phase2_frames(self, ctx, from_img, to_img, num_frames: int):
        return []

    def __repr__(self):
        return f"<{self.__class__.__name__} duration={self.duration}s fps={self.fps} slides={len(self.next_slides)}>"


class OrigamiFoldMultiSlideManager:
    """
    Manager class to handle multi-slide transitions in the slideshow context.
    This gets the next slides from the slideshow and creates the transition.
    """
    
    @staticmethod
    def create_multi_slide_transition(slideshow_slides, current_index, duration, resolution, fps, easing="quad", lighting=True):
        """
        Create a multi-slide transition with the appropriate next slides.
        
        Args:
            slideshow_slides: List of all slides in the slideshow
            current_index: Index of the current slide
            duration: Transition duration
            resolution: Output resolution
            fps: Frame rate
            easing: Easing function
            lighting: Enable lighting
            
        Returns:
            OrigamiFoldMultiSlide instance with next slides loaded
        """
        # Get the next 3 slides for the composite (main + 2 previews)
        next_slides = []
        for i in range(1, 4):  # Get slides at indices current+1, current+2, current+3
            slide_index = current_index + i
            if slide_index < len(slideshow_slides):
                try:
                    # Load the slide image
                    slide_path = slideshow_slides[slide_index]
                    slide_img = Image.open(slide_path).convert('RGB')
                    # Resize to match the transition resolution
                    slide_img = slide_img.resize(resolution, Image.Resampling.LANCZOS)
                    next_slides.append(slide_img)
                except Exception as e:
                    print(f"Warning: Could not load slide {slide_path}: {e}")
                    break
            else:
                break  # No more slides available
        
        return OrigamiFoldMultiSlide(
            next_slides=next_slides,
            duration=duration,
            resolution=resolution,
            fps=fps,
            easing=easing,
            lighting=lighting
        )