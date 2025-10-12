#!/usr/bin/env python3
"""
video_editor.py
---------------
Non-destructive video editor for slideshows.
Allows adding/removing slides without re-rendering unchanged content.

Key Concepts:
- Store metadata about each segment (slide/transition) in final video
- Use FFmpeg segment cutting for surgical edits
- Leverage cache to avoid re-rendering
- Track byte offsets and timestamps for quick seeking
"""

from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
import subprocess
from dataclasses import dataclass, asdict
from slideshow.transitions.ffmpeg_paths import FFmpegPaths
from slideshow.transitions.utils import add_soundtrack_with_fade, extract_audio_from_video
from slideshow.config import Config


@dataclass
class VideoSegment:
    """Metadata for a segment (slide or transition) in the final video."""
    index: int  # Position in sequence
    type: str  # "slide" or "transition"
    source_path: str  # Original media file path
    rendered_path: str  # Path to rendered clip
    duration: float  # Duration in seconds
    start_time: float  # Start timestamp in final video
    end_time: float  # End timestamp in final video
    byte_offset: int  # Starting byte position in final video (0 if unknown)
    byte_size: int  # Size in bytes (0 if unknown)
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**data)


class SlideshowMetadata:
    """Manages metadata for a complete slideshow video."""
    
    def __init__(self, video_path: Path):
        self.video_path = video_path
        self.metadata_path = video_path.with_suffix('.metadata.json')
        self.segments: List[VideoSegment] = []
        self.total_duration: float = 0.0
        self.total_size: int = 0
        self.soundtrack_path: Optional[str] = None  # Original soundtrack file
        
    def add_segment(self, segment: VideoSegment):
        """Add a segment to the metadata."""
        self.segments.append(segment)
        self.total_duration = segment.end_time
        
    def save(self):
        """Save metadata to JSON file."""
        data = {
            "video_path": str(self.video_path),
            "total_duration": self.total_duration,
            "total_size": self.total_size,
            "soundtrack_path": self.soundtrack_path,
            "segments": [seg.to_dict() for seg in self.segments]
        }
        with open(self.metadata_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, video_path: Path) -> Optional['SlideshowMetadata']:
        """Load metadata from JSON file."""
        metadata_path = video_path.with_suffix('.metadata.json')
        if not metadata_path.exists():
            return None
            
        with open(metadata_path, 'r') as f:
            data = json.load(f)
        
        metadata = cls(Path(data['video_path']))
        metadata.total_duration = data['total_duration']
        metadata.total_size = data.get('total_size', 0)
        metadata.soundtrack_path = data.get('soundtrack_path')
        metadata.segments = [VideoSegment.from_dict(seg) for seg in data['segments']]
        return metadata
    
    def find_segment_at_time(self, timestamp: float) -> Optional[VideoSegment]:
        """Find which segment is at a given timestamp."""
        for seg in self.segments:
            if seg.start_time <= timestamp < seg.end_time:
                return seg
        return None
    
    def get_segment_by_index(self, index: int) -> Optional[VideoSegment]:
        """Get segment by its index."""
        for seg in self.segments:
            if seg.index == index:
                return seg
        return None
    
    def get_total_duration(self) -> float:
        """Get total duration of all segments."""
        if self.segments:
            return self.segments[-1].end_time
        return 0.0
    
    def get_segment_count(self) -> int:
        """Get total number of segments."""
        return len(self.segments)


class VideoEditor:
    """
    Non-destructive video editor for slideshows.
    Performs surgical edits without re-rendering unchanged content.
    """
    
    def __init__(self, video_path: Path, metadata: SlideshowMetadata):
        self.video_path = video_path
        self.metadata = metadata
        
    @classmethod
    def from_video(cls, video_path: Path) -> Optional['VideoEditor']:
        """Create editor from existing video with metadata."""
        metadata = SlideshowMetadata.load(video_path)
        if not metadata:
            return None
        return cls(video_path, metadata)
    
    def remove_segments(self, indices: list, output_path: Path, progress_callback=None) -> bool:
        """
        Remove multiple segments from the video in ONE FFmpeg command.
        
        Strategy:
        1. Build FFmpeg select filter to keep only desired time ranges
        2. Single FFmpeg command extracts and concatenates in one pass
        3. Add back soundtrack with looping/fade
        
        Args:
            indices: List of segment indices to remove
            output_path: Where to save the edited video
            progress_callback: Optional function(progress_pct, status_msg) for progress updates
        """
        # Build list of segments to keep (exclude all indices)
        indices_set = set(indices)
        segments_to_keep = [seg for seg in self.metadata.segments if seg.index not in indices_set]
        
        if not segments_to_keep:
            return False
        
        # Build time ranges for FFmpeg select filter
        # Format: "between(t,start,end)+between(t,start2,end2)+..."
        time_ranges = []
        for seg in segments_to_keep:
            time_ranges.append(f"between(t,{seg.start_time:.3f},{seg.end_time:.3f})")
        
        select_expr = "+".join(time_ranges)
        
        # SINGLE FFmpeg command: select time ranges, re-encode with quality settings
        temp_video_only = output_path.parent / "temp_video_only.mp4"
        cmd = [
            FFmpegPaths.ffmpeg(), "-y",
            "-progress", "pipe:1",  # Output progress to stdout
            "-i", str(self.video_path),
            "-vf", f"select='{select_expr}',setpts=N/FRAME_RATE/TB",  # Select segments and reset timestamps
            "-af", f"aselect='{select_expr}',asetpts=N/SR/TB",  # Select audio segments
        ]
        # Use project quality settings
        cmd.extend(Config.instance().get_ffmpeg_encoding_params())
        cmd.extend(["-vsync", "0"])  # Don't duplicate/drop frames
        cmd.append(str(temp_video_only))
        
        if progress_callback:
            progress_callback(5, "Processing video (selecting and re-encoding segments)...")
        
        # Run FFmpeg and parse progress in real-time
        import subprocess
        import re
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                   universal_newlines=True, bufsize=1)
        
        # Calculate expected duration for progress estimation
        expected_duration = sum(seg.duration for seg in segments_to_keep)
        
        for line in process.stdout:
            if progress_callback and "out_time_ms=" in line:
                # Parse current time from FFmpeg progress
                match = re.search(r'out_time_ms=(\d+)', line)
                if match:
                    current_time_ms = int(match.group(1))
                    current_time = current_time_ms / 1000000.0  # Convert microseconds to seconds
                    progress_pct = min(int((current_time / expected_duration) * 70) + 5, 75)  # 5-75%
                    progress_callback(progress_pct, f"Processing video ({current_time:.1f}s / {expected_duration:.1f}s)...")
        
        process.wait()
        if process.returncode != 0:
            return False
        
        if progress_callback:
            progress_callback(80, "Removing audio track...")
        
        # Extract video only (no audio) and add back looped soundtrack
        temp_video_no_audio = output_path.parent / "temp_video_no_audio.mp4"
        cmd_no_audio = [
            FFmpegPaths.ffmpeg(), "-y",
            "-i", str(temp_video_only),
            "-an",  # Remove audio
            "-c:v", "copy",  # Copy video stream
            str(temp_video_no_audio)
        ]
        subprocess.run(cmd_no_audio, capture_output=True, check=True)
        
        if progress_callback:
            progress_callback(80, "Adding soundtrack with fade...")
        
        # Add back the original soundtrack, looped/trimmed to match new duration
        new_duration = sum(seg.duration for seg in segments_to_keep)
        self._add_soundtrack_to_video(temp_video_no_audio, output_path, new_duration)
        
        # Cleanup
        if temp_video_only.exists():
            temp_video_only.unlink()
        if temp_video_no_audio.exists():
            temp_video_no_audio.unlink()
        
        return True
    
    def remove_segment(self, index: int, output_path: Path) -> bool:
        """Remove a single segment (calls remove_segments internally)"""
        return self.remove_segments([index], output_path)
    
    def insert_segment(self, index: int, new_clip_path: Path, output_path: Path) -> bool:
        """
        Insert a new segment at the specified position.
        
        Strategy:
        1. Split video at insertion point
        2. Concatenate: before + new_clip + after
        3. Use copy codec where possible
        """
        # Find insertion point
        insert_after = None
        for seg in self.metadata.segments:
            if seg.index == index - 1:
                insert_after = seg
                break
        
        if insert_after is None and index > 0:
            return False
        
        # Get duration of new clip
        new_duration = self._get_clip_duration(new_clip_path)
        if new_duration is None:
            return False
        
        # Build concat list
        concat_file = output_path.parent / "concat_list.txt"
        with open(concat_file, 'w') as f:
            # Before insertion point
            if insert_after:
                before_end = insert_after.end_time
                temp_before = output_path.parent / "temp_before.mp4"
                self._extract_segment(0, before_end, temp_before)
                f.write(f"file '{temp_before.absolute()}'\n")
            
            # New clip
            f.write(f"file '{new_clip_path.absolute()}'\n")
            
            # After insertion point
            after_start = insert_after.end_time if insert_after else 0
            after_duration = self.metadata.total_duration - after_start
            if after_duration > 0:
                temp_after = output_path.parent / "temp_after.mp4"
                self._extract_segment(after_start, after_duration, temp_after)
                f.write(f"file '{temp_after.absolute()}'\n")
        
        # Concatenate
        cmd = [
            FFmpegPaths.ffmpeg(), "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Cleanup
        concat_file.unlink()
        for temp_file in ["temp_before.mp4", "temp_after.mp4"]:
            temp_path = output_path.parent / temp_file
            if temp_path.exists():
                temp_path.unlink()
        
        return result.returncode == 0
    
    def replace_segment(self, index: int, new_clip_path: Path, output_path: Path) -> bool:
        """
        Replace a segment with a new clip.
        More efficient than remove + insert.
        """
        segment = self.metadata.get_segment_by_index(index)
        if not segment:
            return False
        
        # Build concat list
        concat_file = output_path.parent / "concat_list.txt"
        with open(concat_file, 'w') as f:
            for seg in self.metadata.segments:
                if seg.index == index:
                    # Use new clip instead of original
                    f.write(f"file '{new_clip_path.absolute()}'\n")
                else:
                    # Extract original segment
                    temp_seg = output_path.parent / f"temp_seg_{seg.index}.mp4"
                    self._extract_segment(seg.start_time, seg.duration, temp_seg)
                    f.write(f"file '{temp_seg.absolute()}'\n")
        
        # Concatenate
        cmd = [
            FFmpegPaths.ffmpeg(), "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Cleanup
        concat_file.unlink()
        for seg in self.metadata.segments:
            if seg.index != index:
                temp_seg = output_path.parent / f"temp_seg_{seg.index}.mp4"
                if temp_seg.exists():
                    temp_seg.unlink()
        
        return result.returncode == 0
    
    def _extract_segment(self, start_time: float, duration: float, output_path: Path):
        """Extract a video segment WITHOUT audio (video only)."""
        # Fast extraction using stream copy - no re-encoding!
        # Put -ss before -i for faster seeking
        cmd = [
            FFmpegPaths.ffmpeg(), "-y",
            "-ss", f"{start_time:.3f}",  # Seek before input (faster)
            "-i", str(self.video_path),
            "-t", f"{duration:.3f}",
            "-c:v", "copy",  # Stream copy - no re-encode!
            "-an",  # NO AUDIO - video only
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True)
    
    def _get_clip_duration(self, clip_path: Path) -> Optional[float]:
        """Get duration of a video clip using ffprobe."""
        cmd = [
            FFmpegPaths.ffprobe(),
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(clip_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            try:
                return float(result.stdout.strip())
            except ValueError:
                return None
        return None
    
    def _add_soundtrack_to_video(self, video_path: Path, output_path: Path, target_duration: float):
        """Add original soundtrack back to edited video, looped/trimmed to match duration."""
        # Determine soundtrack source
        soundtrack_source = None
        
        if self.metadata.soundtrack_path and Path(self.metadata.soundtrack_path).exists():
            # Use original soundtrack file from metadata
            soundtrack_source = self.metadata.soundtrack_path
        else:
            # Extract audio from original video
            temp_audio = video_path.parent / "temp_original_audio.aac"
            if extract_audio_from_video(self.video_path, temp_audio):
                soundtrack_source = str(temp_audio)
        
        # Use shared utility to add soundtrack with fade
        success = add_soundtrack_with_fade(
            video_path,
            output_path,
            soundtrack_source,
            target_duration
        )
        
        # Cleanup temp audio if we extracted it
        if soundtrack_source and soundtrack_source.endswith("temp_original_audio.aac"):
            temp_audio_path = Path(soundtrack_source)
            if temp_audio_path.exists():
                temp_audio_path.unlink()
        
        return success
    
    def preview_edit(self, operation: str, index: int, new_clip: Optional[Path] = None) -> Tuple[float, List[str]]:
        """
        Preview what an edit would do without actually performing it.
        
        Returns:
            (new_duration, affected_segments_description)
        """
        if operation == "remove":
            segment = self.metadata.get_segment_by_index(index)
            if not segment:
                return self.metadata.total_duration, ["Segment not found"]
            
            new_duration = self.metadata.total_duration - segment.duration
            desc = [
                f"Remove segment {index}: {segment.type}",
                f"Duration: {segment.duration:.2f}s",
                f"New total: {new_duration:.2f}s (was {self.metadata.total_duration:.2f}s)"
            ]
            return new_duration, desc
            
        elif operation == "insert" and new_clip:
            new_clip_duration = self._get_clip_duration(new_clip)
            if new_clip_duration is None:
                return self.metadata.total_duration, ["Cannot determine new clip duration"]
            
            new_duration = self.metadata.total_duration + new_clip_duration
            desc = [
                f"Insert new clip at position {index}",
                f"Duration: {new_clip_duration:.2f}s",
                f"New total: {new_duration:.2f}s (was {self.metadata.total_duration:.2f}s)"
            ]
            return new_duration, desc
            
        elif operation == "replace" and new_clip:
            segment = self.metadata.get_segment_by_index(index)
            new_clip_duration = self._get_clip_duration(new_clip)
            if not segment or new_clip_duration is None:
                return self.metadata.total_duration, ["Cannot preview replacement"]
            
            duration_change = new_clip_duration - segment.duration
            new_duration = self.metadata.total_duration + duration_change
            desc = [
                f"Replace segment {index}: {segment.type}",
                f"Old duration: {segment.duration:.2f}s",
                f"New duration: {new_clip_duration:.2f}s",
                f"New total: {new_duration:.2f}s (was {self.metadata.total_duration:.2f}s)"
            ]
            return new_duration, desc
        
        return self.metadata.total_duration, ["Unknown operation"]
