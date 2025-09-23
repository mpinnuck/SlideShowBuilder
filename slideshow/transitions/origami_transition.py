from pathlib import Path
import subprocess
import math
import locale
import numpy as np
try:
    import moderngl
    import pyrr
    from PIL import Image
    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False
    moderngl = None
    pyrr = None
    Image = None
from .base_transition import BaseTransition

class OrigamiTransition(BaseTransition):
    """3D Origami-style transition with folding paper effects"""
    
    def __init__(self, duration=2.0, num_images=2, swing_duration=0.5):
        super().__init__(duration)
        self.name = "Origami"
        self.description = "3D folding paper transition with physics-based animation"
        self.num_images = num_images  # 2, 3, or 4 images in the fold
        self.swing_duration = swing_duration  # Duration of settling/swing motion
        
        # Animation parameters
        self.fold_start_time = 0.0
        self.fold_end_time = duration - swing_duration
        self.swing_start_time = self.fold_end_time
        self.swing_end_time = duration
        
        # Framerate based on locale/region
        self.frame_rate = self._get_locale_framerate()
        
    def _get_locale_framerate(self) -> int:
        """
        Determine appropriate framerate based on locale/electrical grid frequency
        
        Returns:
            Framerate (25fps for 50Hz regions, 30fps for 60Hz regions)
        """
        try:
            # Get current locale
            current_locale = locale.getlocale()[0] or locale.getdefaultlocale()[0] or ""
            
            # 50Hz regions (PAL) - use 25fps
            pal_regions = [
                'en_AU',  # Australia
                'en_GB',  # United Kingdom
                'de_DE',  # Germany
                'fr_FR',  # France
                'it_IT',  # Italy
                'es_ES',  # Spain
                'nl_NL',  # Netherlands
                'sv_SE',  # Sweden
                'da_DK',  # Denmark
                'no_NO',  # Norway
                'fi_FI',  # Finland
                'ru_RU',  # Russia
                'zh_CN',  # China
                'ja_JP',  # Japan (50Hz in eastern regions)
                'ko_KR',  # South Korea
                'th_TH',  # Thailand
                'vi_VN',  # Vietnam
                'id_ID',  # Indonesia
                'hi_IN',  # India
                'ar_SA',  # Saudi Arabia
                'he_IL',  # Israel
                'tr_TR',  # Turkey
                'pt_BR',  # Brazil (mixed, but generally 60Hz - exception handled below)
            ]
            
            # 60Hz regions (NTSC) - use 30fps
            ntsc_regions = [
                'en_US',  # United States
                'en_CA',  # Canada
                'es_MX',  # Mexico
                'pt_BR',  # Brazil (actually 60Hz despite being in PAL list above)
                'ja_JP',  # Japan (60Hz in western regions, defaulting to 30fps)
                'ko_KR',  # South Korea (mixed, but 60Hz more common)
                'zh_TW',  # Taiwan
                'es_CO',  # Colombia
                'es_VE',  # Venezuela
                'es_PE',  # Peru
                'es_CL',  # Chile
                'es_AR',  # Argentina
            ]
            
            # Check for specific overrides first
            if current_locale in ['pt_BR', 'en_US', 'en_CA', 'es_MX', 'zh_TW']:
                return 30  # 60Hz regions
            elif current_locale in pal_regions:
                return 25  # 50Hz regions
            elif current_locale in ntsc_regions:
                return 30  # 60Hz regions
            else:
                # Default fallback based on common patterns
                if current_locale.startswith(('en_US', 'en_CA', 'es_MX')):
                    return 30  # North America
                elif current_locale.startswith(('en_AU', 'en_GB', 'de_', 'fr_', 'it_', 'es_ES')):
                    return 25  # Europe/Australia
                else:
                    # Global default - use 25fps (more common worldwide)
                    return 25
                    
        except Exception:
            # Fallback to 25fps if locale detection fails
            return 25
        
    def get_requirements(self) -> list:
        """Origami transition requires OpenGL and additional 3D libraries"""
        return ["ffmpeg", "moderngl", "PIL", "numpy", "pyrr"]
    
    def is_available(self) -> bool:
        """Check if OpenGL and 3D dependencies are available"""
        if not OPENGL_AVAILABLE:
            return False
        
        try:
            # Check basic requirements from parent
            if not super().is_available():
                return False
            
            # Test OpenGL context creation
            self._test_opengl_context()
            return True
            
        except Exception:
            return False
    
    def _test_opengl_context(self):
        """Test that we can create an OpenGL context"""
        try:
            # Create a minimal OpenGL context for testing
            ctx = moderngl.create_context(standalone=True, size=(64, 64))
            ctx.release()
        except Exception as e:
            raise RuntimeError(f"OpenGL context creation failed: {e}")
    
    def _create_opengl_context(self, width: int, height: int):
        """Create OpenGL context for 3D rendering"""
        try:
            # Create offscreen OpenGL context
            ctx = moderngl.create_context(standalone=True, size=(width, height))
            
            # Enable depth testing and blending
            ctx.enable(moderngl.DEPTH_TEST)
            ctx.enable(moderngl.BLEND)
            ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            
            return ctx
            
        except Exception as e:
            raise RuntimeError(f"Failed to create OpenGL context: {e}")
    
    def _create_paper_geometry(self, width: int, height: int, segments: int = 20):
        """
        Create paper folding geometry (vertices and triangles)
        
        Args:
            width: Paper width in pixels
            height: Paper height in pixels
            segments: Number of segments for folding detail
            
        Returns:
            Tuple of (vertices, indices, texture_coords)
        """
        # Create a grid of vertices for the paper surface
        vertices = []
        indices = []
        tex_coords = []
        
        # Generate grid vertices
        for y in range(segments + 1):
            for x in range(segments + 1):
                # Normalized coordinates (0 to 1)
                u = x / segments
                v = y / segments
                
                # Convert to world coordinates
                world_x = (u - 0.5) * width
                world_y = (v - 0.5) * height
                world_z = 0.0  # Start flat
                
                vertices.extend([world_x, world_y, world_z])
                tex_coords.extend([u, v])
        
        # Generate triangle indices
        for y in range(segments):
            for x in range(segments):
                # Current quad vertices
                top_left = y * (segments + 1) + x
                top_right = top_left + 1
                bottom_left = (y + 1) * (segments + 1) + x
                bottom_right = bottom_left + 1
                
                # Two triangles per quad
                indices.extend([
                    top_left, bottom_left, top_right,
                    top_right, bottom_left, bottom_right
                ])
        
        return np.array(vertices, dtype=np.float32), np.array(indices, dtype=np.uint32), np.array(tex_coords, dtype=np.float32)
    
    def _calculate_fold_transforms(self, progress: float, fold_type: str = "horizontal"):
        """
        Calculate transformation matrices for folding animation
        
        Args:
            progress: Animation progress (0.0 to 1.0)
            fold_type: "horizontal", "vertical", or "diagonal"
            
        Returns:
            List of transformation matrices for each paper segment
        """
        transforms = []
        
        if fold_type == "horizontal":
            # Fold along horizontal center
            fold_angle = progress * math.pi  # 0 to 180 degrees
            
            # Left half rotates around Y axis
            left_matrix = pyrr.matrix44.create_from_y_rotation(fold_angle)
            # Right half rotates in opposite direction
            right_matrix = pyrr.matrix44.create_from_y_rotation(-fold_angle)
            
            transforms.append({
                'region': 'left',
                'matrix': left_matrix,
                'pivot': np.array([-0.25, 0.0, 0.0])  # Fold line offset
            })
            transforms.append({
                'region': 'right', 
                'matrix': right_matrix,
                'pivot': np.array([0.25, 0.0, 0.0])
            })
            
        elif fold_type == "vertical":
            # Fold along vertical center
            fold_angle = progress * math.pi
            
            # Top half rotates around X axis
            top_matrix = pyrr.matrix44.create_from_x_rotation(fold_angle)
            # Bottom half rotates in opposite direction
            bottom_matrix = pyrr.matrix44.create_from_x_rotation(-fold_angle)
            
            transforms.append({
                'region': 'top',
                'matrix': top_matrix,
                'pivot': np.array([0.0, 0.25, 0.0])
            })
            transforms.append({
                'region': 'bottom',
                'matrix': bottom_matrix, 
                'pivot': np.array([0.0, -0.25, 0.0])
            })
            
        elif fold_type == "diagonal":
            # Diagonal fold creates 4 triangular sections
            fold_angle = progress * math.pi * 0.7  # Slightly less dramatic
            
            # Four diagonal transforms
            for i, (name, angle_mult, pivot_offset) in enumerate([
                ('top_left', 1.0, np.array([-0.25, 0.25, 0.0])),
                ('top_right', -1.0, np.array([0.25, 0.25, 0.0])),
                ('bottom_left', -1.0, np.array([-0.25, -0.25, 0.0])),
                ('bottom_right', 1.0, np.array([0.25, -0.25, 0.0]))
            ]):
                # Diagonal rotation (combination of X and Y)
                x_rot = pyrr.matrix44.create_from_x_rotation(fold_angle * angle_mult * 0.7)
                y_rot = pyrr.matrix44.create_from_y_rotation(fold_angle * angle_mult * 0.3)
                matrix = pyrr.matrix44.multiply(x_rot, y_rot)
                
                transforms.append({
                    'region': name,
                    'matrix': matrix,
                    'pivot': pivot_offset
                })
        
        return transforms
    
    def _add_physics_swing(self, base_progress: float, swing_amplitude: float = 0.1):
        """
        Add realistic swinging motion after the main fold
        
        Args:
            base_progress: Base folding progress (0.0 to 1.0)
            swing_amplitude: How much swing motion to add
            
        Returns:
            Modified progress with swing physics
        """
        if base_progress >= 1.0:
            # Add dampened oscillation after fold completes
            time_since_complete = base_progress - 1.0
            
            # Damped sine wave for natural swinging
            damping = math.exp(-time_since_complete * 3.0)  # Exponential decay
            swing_freq = 8.0  # Swing frequency
            swing_offset = math.sin(time_since_complete * swing_freq) * swing_amplitude * damping
            
            return 1.0 + swing_offset
        
        return base_progress
    def render(self, from_path: Path, to_path: Path, output_path: Path):
        """
        Render an origami folding transition between two video files
        
        This will create a 3D folding paper effect that combines multiple images
        with realistic physics-based swinging motion.
        
        Args:
            from_path: Path to the source video file
            to_path: Path to the destination video file
            output_path: Path where the transition video should be saved
        """
        # Validate inputs
        self.validate_inputs(from_path, to_path, output_path)
        
        if not self.is_available():
            raise RuntimeError("Origami transition dependencies not available. "
                             "Install with: pip install moderngl pillow pyrr")
        
        try:
            # Extract frames from input videos
            frame_sequences = self._extract_frames(from_path, to_path)
            
            # Generate 3D animation frames
            animation_frames = self._generate_3d_animation(frame_sequences)
            
            # Compose final video
            self._compose_video(animation_frames, output_path)
            
        except Exception as e:
            # Fallback to simple fade if 3D rendering fails
            print(f"Origami transition failed, falling back to fade: {e}")
            self._fallback_fade(from_path, to_path, output_path)
    
    def _extract_frames(self, from_path: Path, to_path: Path) -> dict:
        """
        Extract frames from input videos for 3D processing
        
        Returns:
            Dictionary containing frame sequences and metadata
        """
        # Create working directory in data folder
        working_dir = Path("data/working/origami_frames")
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Clear any existing frames
        for existing_frame in working_dir.glob("*.png"):
            existing_frame.unlink()
        
        frame_sequences = {
            'from_frames': [],
            'to_frames': [],
            'working_dir': working_dir
        }
        
        try:
            # Extract a few key frames from source video
            from_frames_dir = working_dir / "from"
            from_frames_dir.mkdir(exist_ok=True)
            
            # Extract frames using FFmpeg with locale-appropriate framerate
            cmd_from = [
                "ffmpeg", "-i", str(from_path.resolve()),
                "-vf", f"fps={self.frame_rate},scale=1920:1080", # Use locale-appropriate framerate
                "-t", "1.0",  # Only extract first second
                str(from_frames_dir / "frame_%04d.png")
            ]
            
            result_from = subprocess.run(cmd_from, capture_output=True, text=True)
            if result_from.returncode != 0:
                raise RuntimeError(f"Failed to extract frames from {from_path}: {result_from.stderr}")
            
            # Extract frames from destination video  
            to_frames_dir = working_dir / "to"
            to_frames_dir.mkdir(exist_ok=True)
            
            cmd_to = [
                "ffmpeg", "-i", str(to_path.resolve()),
                "-vf", f"fps={self.frame_rate},scale=1920:1080",  # Use locale-appropriate framerate
                "-t", "1.0",  # Only extract first second
                str(to_frames_dir / "frame_%04d.png")
            ]
            
            result_to = subprocess.run(cmd_to, capture_output=True, text=True)
            if result_to.returncode != 0:
                raise RuntimeError(f"Failed to extract frames from {to_path}: {result_to.stderr}")
            
            # Collect extracted frame paths
            frame_sequences['from_frames'] = sorted(list(from_frames_dir.glob("frame_*.png")))
            frame_sequences['to_frames'] = sorted(list(to_frames_dir.glob("frame_*.png")))
            
            # Add metadata
            frame_sequences['frame_rate'] = self.frame_rate  # Locale-appropriate framerate
            frame_sequences['resolution'] = (1920, 1080)
            frame_sequences['duration'] = self.duration
            
            print(f"Extracted {len(frame_sequences['from_frames'])} frames from source")
            print(f"Extracted {len(frame_sequences['to_frames'])} frames from destination")
            print(f"Using {self.frame_rate}fps (locale-based framerate)")
            
            return frame_sequences
            
        except Exception as e:
            # Clean up on error
            if working_dir.exists():
                for cleanup_file in working_dir.rglob("*"):
                    if cleanup_file.is_file():
                        cleanup_file.unlink()
            raise RuntimeError(f"Frame extraction failed: {e}")
    
    def _generate_3d_animation(self, frame_sequences: dict) -> list:
        """
        Generate 3D folding animation using OpenGL
        
        Args:
            frame_sequences: Extracted frames and metadata
            
        Returns:
            List of rendered animation frames
        """
        # TODO: Implement 3D rendering
        # - Create OpenGL context
        # - Set up 3D scene with paper surfaces
        # - Apply textures from input frames
        # - Animate folding transformation
        # - Add physics-based swinging motion
        # - Render to frame sequence
        raise NotImplementedError("3D animation generation not yet implemented")
    
    def _compose_video(self, animation_frames: list, output_path: Path):
        """
        Compose final video from rendered animation frames
        
        Args:
            animation_frames: List of rendered frame images
            output_path: Output video file path
        """
        # TODO: Implement video composition
        # - Combine frames into video sequence
        # - Apply proper timing and frame rate
        # - Add audio handling if needed
        # - Use FFmpeg for final encoding
        raise NotImplementedError("Video composition not yet implemented")
    
    def _fallback_fade(self, from_path: Path, to_path: Path, output_path: Path):
        """
        Fallback to simple fade transition if 3D rendering fails
        """
        from .fade_transition import FadeTransition
        fade = FadeTransition(self.duration)
        fade.render(from_path, to_path, output_path)
    
    def get_fold_patterns(self) -> dict:
        """
        Get available folding patterns based on number of images
        
        Returns:
            Dictionary mapping num_images to fold pattern descriptions
        """
        return {
            2: "Simple center fold (like opening a book)",
            3: "Tri-fold with two fold lines", 
            4: "Quad-fold in cross pattern"
        }
    
    def estimate_render_time(self) -> float:
        """
        Estimate rendering time based on complexity
        
        Returns:
            Estimated render time in seconds
        """
        # 3D rendering is significantly slower than simple transitions
        base_time = self.duration * 10  # Base multiplier for 3D complexity
        complexity_multiplier = self.num_images * 0.5  # More images = more complexity
        return base_time * complexity_multiplier