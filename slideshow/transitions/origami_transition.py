from pathlib import Path
import subprocess
import math
import locale
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
    
    def _create_paper_geometry(self):
        """
        Create 3D geometry for paper surfaces
        
        Returns:
            Vertex data for paper quad meshes
        """
        # TODO: Implement paper mesh generation
        # - Create subdivided quads for smooth folding
        # - Set up UV coordinates for texture mapping
        # - Define fold lines and pivot points
        raise NotImplementedError("Paper geometry creation not yet implemented")
    
    def _calculate_fold_animation(self, time_progress: float) -> dict:
        """
        Calculate folding transformation matrices for given time
        
        Args:
            time_progress: Animation progress (0.0 to 1.0)
            
        Returns:
            Dictionary of transformation matrices for each paper surface
        """
        # TODO: Implement fold animation calculations
        # - Calculate rotation angles based on time
        # - Apply easing functions for smooth motion
        # - Handle different fold patterns (2, 3, 4 images)
        # - Add physics-based settling motion
        raise NotImplementedError("Fold animation calculation not yet implemented")
    
    def _apply_lighting_and_shadows(self):
        """
        Apply realistic lighting and shadow effects to paper surfaces
        """
        # TODO: Implement lighting system
        # - Set up directional lighting
        # - Calculate surface normals for shading
        # - Add subtle shadows between paper layers
        # - Enhance 3D depth perception
        raise NotImplementedError("Lighting and shadows not yet implemented")
    
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