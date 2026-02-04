# slideshow/transitions/utils.py

import subprocess, tempfile, os
from pathlib import Path
from PIL import Image
import numpy as np
from slideshow.config import cfg
from slideshow.transitions.ffmpeg_cache import FFmpegCache
from slideshow.transitions.ffmpeg_paths import FFmpegPaths

def get_video_info(video_path):
    """Return (width, height, fps) of a video using ffprobe."""
    cmd = [
        FFmpegPaths.ffprobe(), "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    width, height, fps_str = result.stdout.strip().split("\n")
    width, height = int(width), int(height)
    num, denom = fps_str.split("/")
    fps = float(num) / float(denom)
    return width, height, round(fps)

def get_video_duration(video_path):
    """Return the duration of a video in seconds using ffprobe."""
    cmd = [
        FFmpegPaths.ffprobe(), "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed to get duration: {result.stderr}")
    duration_str = result.stdout.strip()
    return float(duration_str)

def extract_frame(video_path, last=False):
    """Extract the first or last frame of a video to a PIL.Image (robust)."""
    
    # Create cache key parameters
    cache_params = {
        "operation": "extract_frame",
        "frame_type": "last" if last else "first",
        "format": "png"
    }
    
    # Check cache first
    cached_frame = FFmpegCache.get_cached_frame(Path(video_path), cache_params)
    if cached_frame:
        return Image.open(cached_frame).convert("RGB")
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
        tmp_path = tmpfile.name
    try:
        if last:
            # Seek slightly before end to avoid sseof=0 edge cases
            cmd = [FFmpegPaths.ffmpeg(), "-y", "-sseof", "-0.1", "-i", str(video_path),
                   "-vframes", "1", tmp_path]
        else:
            cmd = [FFmpegPaths.ffmpeg(), "-y", "-i", str(video_path), "-vframes", "1", tmp_path]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            # Fallback to seeking 1s before end
            cmd = [FFmpegPaths.ffmpeg(), "-y", "-sseof", "-1", "-i", str(video_path),
                   "-vframes", "1", tmp_path]
            subprocess.run(cmd, check=True, capture_output=True)  # Suppress verbose output

        # Store extracted frame in cache before returning
        FFmpegCache.store_frame(Path(video_path), cache_params, Path(tmp_path))
        
        return Image.open(tmp_path).convert("RGB")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def load_and_resize_image(image_or_path, target_size=(1920, 1080)):
    """
    Load an image (path or PIL.Image) and resize with letter/pillarboxing
    to exactly match the target resolution.
    """
    from PIL import ImageOps
    img = image_or_path if isinstance(image_or_path, Image.Image) else Image.open(image_or_path).convert("RGB")
    # Apply EXIF orientation correction (fixes upside-down/sideways images)
    img = ImageOps.exif_transpose(img)
    original_width, original_height = img.size
    target_width, target_height = target_size

    orig_aspect = original_width / original_height
    target_aspect = target_width / target_height

    # Create blank canvas at target resolution
    canvas = Image.new("RGB", target_size, (0, 0, 0))

    if orig_aspect > target_aspect:
        # Image is wider than target: fit width, adjust height
        new_width = target_width
        new_height = int(target_width / orig_aspect)
        x_offset, y_offset = 0, (target_height - new_height) // 2
    else:
        # Image is taller (or equal aspect): fit height, adjust width
        new_height = target_height
        new_width = int(target_height * orig_aspect)
        x_offset, y_offset = (target_width - new_width) // 2, 0

    resized = img.resize((new_width, new_height), Image.LANCZOS)
    canvas.paste(resized, (x_offset, y_offset))
    return canvas

def save_frames_as_video(frames, output_path, fps=25):
    """Save a list of numpy RGB frames as an MP4 video using ffmpeg."""
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        for i, frame in enumerate(frames):
            Image.fromarray(frame, "RGB").save(f"{tmp}/frame_{i:06d}.png")
        
        # Calculate exact duration from frame count and FPS
        duration = len(frames) / fps
        
        cmd = [
            FFmpegPaths.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
            "-r", str(fps),
            "-i", f"{tmp}/frame_%06d.png",
        ]
        cmd.extend(cfg.get_ffmpeg_encoding_params())  # Use project quality settings
        cmd.extend([
            "-pix_fmt", "yuv420p",
            "-t", f"{duration:.3f}",  # Explicit duration for proper metadata
            "-movflags", "+faststart",  # Optimize for streaming/concatenation
            str(output_path)
        ])
        subprocess.run(cmd, check=True, capture_output=True)  # Suppress verbose output


def add_soundtrack_with_fade(video_only_path, output_path, soundtrack_path, duration, progress_callback=None):
    """
    Add soundtrack to a video-only file with looping and fade-out.
    
    This is the standard workflow used by both:
    - SlideShowModel during initial video creation
    - VideoEditor when applying edits
    
    Process:
    1. If soundtrack exists: Loop it to match video duration, trim to exact length
    2. Apply 1-second fade-out at the end
    3. If no soundtrack: Just copy the video
    
    Args:
        video_only_path: Path to video file without audio
        output_path: Path for final output with audio
        soundtrack_path: Path to audio file (or None for video-only output)
        duration: Target duration in seconds
        progress_callback: Optional callback for progress messages
        
    Returns:
        True if successful, False otherwise
    """
    # if progress_callback:
    #     progress_callback(f"Adding soundtrack to video ({duration:.1f}s)...")
    
    has_soundtrack = bool(soundtrack_path) and Path(soundtrack_path).exists()
    
    if not has_soundtrack:
        # No soundtrack - just copy the video
        if progress_callback:
            progress_callback("No soundtrack - copying video...")
        import shutil
        shutil.copyfile(video_only_path, output_path)
        return True
    
    # Step 1: Mux soundtrack (looped) and apply fade in ONE pass
    # if progress_callback:
    #     progress_callback("Muxing soundtrack (looped) with fade...")
    
    # Build audio filter: fade out in last second (if duration > 1s)
    audio_filter = f"afade=out:st={duration-1:.2f}:d=1" if duration > 1.0 else None
    
    mux_cmd = [
        FFmpegPaths.ffmpeg(), "-y",
        "-hide_banner", "-loglevel", "error",
        "-progress", "pipe:2",  # Send progress to stderr
        "-i", str(video_only_path),
        "-stream_loop", "-1",  # Loop audio indefinitely
        "-i", str(soundtrack_path),
        "-map", "0:v",  # Video from first input
        "-map", "1:a",  # Audio from second input
        "-t", f"{duration:.3f}",  # Trim to exact duration
        "-c:v", "copy",  # Copy video (no re-encode)
        "-c:a", "aac",  # Encode audio
        "-b:a", "192k",  # High quality audio
    ]
    
    if audio_filter:
        mux_cmd.extend(["-af", audio_filter])  # Apply fade filter
    
    mux_cmd.extend([
        "-movflags", "+faststart",  # Web-friendly
        str(output_path)
    ])
    
    # Run with progress monitoring (silent - progress shown via progress bar, not log)
    import re
    process = subprocess.Popen(mux_cmd, stderr=subprocess.PIPE, text=True, bufsize=1)
    
    # Parse progress from stderr to keep progress bar active
    # (don't print to log - that would spam the console)
    for line in process.stderr:
        pass  # Just consume the output to prevent blocking
    
    process.wait()
    
    if process.returncode != 0:
        if progress_callback:
            progress_callback(f"Error muxing soundtrack")
        return False
    
    # if progress_callback:
    #     progress_callback("Soundtrack added successfully!")
    
    return True


def extract_audio_from_video(video_path, output_audio_path):
    """
    Extract audio track from a video file.
    
    Args:
        video_path: Source video file
        output_audio_path: Destination for extracted audio
        
    Returns:
        True if successful, False otherwise
    """
    cmd = [
        FFmpegPaths.ffmpeg(), "-y",
        "-i", str(video_path),
        "-vn",  # No video
        "-acodec", "copy",  # Copy audio codec
        str(output_audio_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0
