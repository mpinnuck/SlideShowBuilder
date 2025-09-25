# slideshow/transitions/utils.py

import subprocess, tempfile, os
from pathlib import Path
from PIL import Image
import numpy as np

def get_video_info(video_path):
    """Return (width, height, fps) of a video using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
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
        "ffprobe", "-v", "error",
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
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
        tmp_path = tmpfile.name
    try:
        if last:
            # Seek slightly before end to avoid sseof=0 edge cases
            cmd = ["ffmpeg", "-y", "-sseof", "-0.1", "-i", str(video_path),
                   "-vframes", "1", tmp_path]
        else:
            cmd = ["ffmpeg", "-y", "-i", str(video_path), "-vframes", "1", tmp_path]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            # Fallback to seeking 1s before end
            cmd = ["ffmpeg", "-y", "-sseof", "-1", "-i", str(video_path),
                   "-vframes", "1", tmp_path]
            subprocess.run(cmd, check=True)

        return Image.open(tmp_path).convert("RGB")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def load_and_resize_image(image_or_path, target_size=(1920, 1080)):
    """Load an image or use PIL.Image and resize with letter/pillarboxing."""
    img = image_or_path if isinstance(image_or_path, Image.Image) else Image.open(image_or_path).convert("RGB")
    original_width, original_height = img.size
    target_width, target_height = target_size

    orig_aspect = original_width / original_height
    target_aspect = target_width / target_height

    if abs(orig_aspect - target_aspect) < 0.01:
        return img.resize(target_size, Image.LANCZOS)

    canvas = Image.new("RGB", target_size, (0, 0, 0))
    if orig_aspect > target_aspect:
        new_width = target_width
        new_height = int(target_width / orig_aspect)
        x_offset, y_offset = 0, (target_height - new_height) // 2
    else:
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
        cmd = [
            "ffmpeg", "-y", "-r", str(fps),
            "-i", f"{tmp}/frame_%06d.png",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", str(output_path)
        ]
        subprocess.run(cmd, check=True)


def generate_full_screen_mesh(segments=20):
    """Generate a full-screen mesh for OpenGL rendering."""
    vertices, tex_coords, indices = [], [], []
    for y in range(segments + 1):
        for x in range(segments + 1):
            u, v = x / segments, y / segments
            world_x = (u - 0.5) * 2.0
            world_y = (v - 0.5) * 2.0
            vertices.extend([world_x, world_y, 0.0])
            tex_coords.extend([u, 1.0 - v])
            if x < segments and y < segments:
                tl = y * (segments + 1) + x
                tr = tl + 1
                bl = (y + 1) * (segments + 1) + x
                br = bl + 1
                indices.extend([tl, bl, tr, tr, bl, br])
    return (np.array(vertices, np.float32),
            np.array(tex_coords, np.float32),
            np.array(indices, np.uint32))
