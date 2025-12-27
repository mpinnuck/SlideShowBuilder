# slideshow/transitions/ffmpeg_cache.py
"""
FFmpeg output cache system for SlideShowBuilder.
Caches rendered video clips to avoid expensive re-computation.
"""

import hashlib
import json
import shutil
from pathlib import Path
from typing import Optional, Union, Dict, Any
import os
from slideshow.config import cfg


class FFmpegCache:
    """
    Global singleton cache for FFmpeg outputs to avoid expensive re-computation.
    
    Unlike GPU shader caching, this caches the actual output files produced
    by FFmpeg operations since FFmpeg is an external process, not compiled code.
    
    Usage:
        1. Call configure(cache_dir) once at the start of export
        2. All cache operations then work automatically with zero overhead
        3. Can call configure() multiple times - it's idempotent
    
    Cache keys are based on:
    - Input file path and modification time
    - FFmpeg command parameters (resolution, fps, duration, etc.)
    - Output format specifications
    
    Cache structure:
    cache_dir/
        metadata.json     # Cache metadata and index
        clips/           # Cached video clips
            {hash}.mp4
        frames/          # Cached frame extractions  
            {hash}.png
        temp/            # Temporary processing files
    """
    
    _cache_dir: Optional[Path] = None
    _metadata: Dict[str, Any] = {}
    _enabled = True
    _initialized = False
    
    @classmethod
    def configure(cls, cache_dir: Union[str, Path]):
        """
        Configure the cache with a directory path. Idempotent - safe to call multiple times.
        Creates directories and loads metadata immediately.
        
        Args:
            cache_dir: Path to the cache directory
        """
        cache_dir = Path(cache_dir)
        
        # If already configured with same directory, skip re-initialization
        if cls._initialized and cls._cache_dir == cache_dir:
            return
        
        # If reconfiguring with a different directory, reset state
        if cls._cache_dir != cache_dir:
            cls._cache_dir = cache_dir
            cls._initialized = False
            cls._metadata = {}
        
        try:
            cls._cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Create subdirectories
            (cls._cache_dir / "clips").mkdir(exist_ok=True)
            (cls._cache_dir / "frames").mkdir(exist_ok=True)
            (cls._cache_dir / "temp").mkdir(exist_ok=True)
        except (OSError, PermissionError) as e:
            # If we can't create the cache directory, disable caching
            print(f"[FFmpegCache] Warning: Could not create cache directory: {e}")
            cls._enabled = False
            cls._initialized = True  # Mark as "initialized" even if failed to prevent retries
            return
        
        # Load or create metadata
        metadata_file = cls._cache_dir / "metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    cls._metadata = json.load(f)
            except (json.JSONDecodeError, IOError):
                cls._metadata = {"version": "1.0", "entries": {}, "stats": {"hits": 0, "misses": 0}}
        else:
            cls._metadata = {"version": "1.0", "entries": {}, "stats": {"hits": 0, "misses": 0}}
        
        # Ensure stats section exists for older cache files
        if "stats" not in cls._metadata:
            cls._metadata["stats"] = {"hits": 0, "misses": 0}
        
        cls._initialized = True
        cls._enabled = True
    
    @classmethod
    def auto_configure(cls):
        """
        Automatically configure the cache if not already configured.
        Determines cache directory from global config and calls configure().
        
        This is called automatically by cache methods, so callers don't need
        to worry about configuring the cache before use.
        """
        # If already configured, nothing to do
        if cls._initialized and cls._cache_dir:
            return
        
        # Try to determine cache directory from global config
        try:
            output_folder = cfg.get("output_folder", "")
            if output_folder:
                working_dir = Path(output_folder) / "working"
                cache_dir = working_dir / "ffmpeg_cache"
                cls.configure(cache_dir)
        except Exception as e:
            # If we can't auto-configure, cache will remain disabled
            # This is not fatal - the application will just skip caching
            pass
    
    @classmethod
    def _save_metadata(cls):
        """Save metadata to disk."""
        if cls._cache_dir:
            metadata_file = cls._cache_dir / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(cls._metadata, f, indent=2)
    
    @classmethod
    def _generate_cache_key(cls, input_path: Path, params: Dict[str, Any]) -> str:
        """Generate a unique cache key based on input file and parameters."""
        # Use filename and size for file identity
        # Size is important: if user replaces the file, size likely changes → cache miss → re-render
        file_stats = {
            "name": input_path.name,
            "size": input_path.stat().st_size if input_path.exists() else 0
        }
        
        # Combine file stats with processing parameters
        cache_data = {
            "file": file_stats,
            "params": params
        }
        
        # Create hash from the combined data
        cache_str = json.dumps(cache_data, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()[:16]
    
    @classmethod
    def get_cached_clip(cls, input_path: Path, params: Dict[str, Any]) -> Optional[Path]:
        """Check if a cached clip exists for the given input and parameters."""
        if not cls._enabled or not cls._cache_dir:
            stats = cls._metadata.setdefault("stats", {})
            stats["misses"] = stats.get("misses", 0) + 1
            return None
            
        cache_key = cls._generate_cache_key(input_path, params)
        
        # Check if entry exists in metadata
        if cache_key not in cls._metadata.get("entries", {}):
            stats = cls._metadata.setdefault("stats", {})
            stats["misses"] = stats.get("misses", 0) + 1
            cls._save_metadata()
            return None
            
        # Check if cached file actually exists
        cached_file = cls._cache_dir / "clips" / f"{cache_key}.mp4"
        if not cached_file.exists():
            # Clean up stale metadata entry
            del cls._metadata["entries"][cache_key]
            stats = cls._metadata.setdefault("stats", {})
            stats["misses"] = stats.get("misses", 0) + 1
            cls._save_metadata()
            return None
        
        # Cache hit!
        stats = cls._metadata.setdefault("stats", {})
        stats["hits"] = stats.get("hits", 0) + 1
        
        # Update access time for the entry
        cls._metadata["entries"][cache_key]["last_accessed"] = cached_file.stat().st_mtime
        cls._save_metadata()
        
        return cached_file
    
    @classmethod
    def store_clip(cls, input_path: Path, params: Dict[str, Any], output_path: Path) -> Optional[Path]:
        """Store a rendered clip in the cache."""
        if not cls._enabled or not cls._cache_dir or not output_path.exists():
            return None
            
        cache_key = cls._generate_cache_key(input_path, params)
        cached_file = cls._cache_dir / "clips" / f"{cache_key}.mp4"
        
        try:
            # Copy the output file to cache
            shutil.copy2(output_path, cached_file)
            
            # Update metadata
            cls._metadata["entries"][cache_key] = {
                "type": "clip",
                "input_path": str(input_path),
                "params": params,
                "created": cached_file.stat().st_mtime,
                "last_accessed": cached_file.stat().st_mtime,
                "size": cached_file.stat().st_size
            }
            cls._save_metadata()
            
            return cached_file
            
        except (IOError, OSError) as e:
            # Failed to cache - not fatal, just log and continue
            print(f"[FFmpegCache] Warning: Failed to cache clip: {e}")
            return None
    
    @classmethod
    def get_cached_frame(cls, input_path: Path, params: Dict[str, Any]) -> Optional[Path]:
        """Check if a cached frame exists for the given input and parameters."""
        if not cls._enabled or not cls._cache_dir:
            stats = cls._metadata.setdefault("stats", {})
            stats["misses"] = stats.get("misses", 0) + 1
            return None
            
        cache_key = cls._generate_cache_key(input_path, params)
        
        # Check if entry exists in metadata
        if cache_key not in cls._metadata.get("entries", {}):
            stats = cls._metadata.setdefault("stats", {})
            stats["misses"] = stats.get("misses", 0) + 1
            cls._save_metadata()
            return None
            
        # Check if cached file actually exists
        cached_file = cls._cache_dir / "frames" / f"{cache_key}.png"
        if not cached_file.exists():
            # Clean up stale metadata entry
            del cls._metadata["entries"][cache_key]
            stats = cls._metadata.setdefault("stats", {})
            stats["misses"] = stats.get("misses", 0) + 1
            cls._save_metadata()
            return None
        
        # Cache hit!
        stats = cls._metadata.setdefault("stats", {})
        stats["hits"] = stats.get("hits", 0) + 1
        
        # Update access time for the entry
        cls._metadata["entries"][cache_key]["last_accessed"] = cached_file.stat().st_mtime
        cls._save_metadata()
        
        return cached_file
    
    @classmethod
    def store_frame(cls, input_path: Path, params: Dict[str, Any], output_path: Path) -> Optional[Path]:
        """Store an extracted frame in the cache."""
        if not cls._enabled or not cls._cache_dir or not output_path.exists():
            return None
            
        cache_key = cls._generate_cache_key(input_path, params)
        cached_file = cls._cache_dir / "frames" / f"{cache_key}.png"
        
        try:
            # Copy the output file to cache
            shutil.copy2(output_path, cached_file)
            
            # Update metadata
            cls._metadata["entries"][cache_key] = {
                "type": "frame",
                "input_path": str(input_path),
                "params": params,
                "created": cached_file.stat().st_mtime,
                "last_accessed": cached_file.stat().st_mtime,
                "size": cached_file.stat().st_size
            }
            cls._save_metadata()
            
            return cached_file
            
        except (IOError, OSError) as e:
            # Failed to cache - not fatal, just log and continue
            print(f"[FFmpegCache] Warning: Failed to cache frame: {e}")
            return None
    
    @classmethod
    def clear_cache(cls) -> bool:
        """
        Clear all cached files and metadata.
        Only clears if cache is already configured.
        Returns True if cache was cleared, False if skipped.
        """
        # Only clear if already configured - don't auto-configure
        # to avoid clearing the wrong cache directory
        if not cls._initialized or not cls._cache_dir:
            # Silently skip - cache not configured yet, nothing to clear
            return False
            
        if cls._cache_dir.exists():
            try:
                # Get stats before clearing
                entries_before = len(cls._metadata.get("entries", {}))
                
                # Delete the entire cache directory
                shutil.rmtree(cls._cache_dir)
                
                # Reset metadata
                cls._metadata = {"version": "1.0", "entries": {}, "stats": {"hits": 0, "misses": 0}}
                cls._initialized = False
                
                # Recreate the empty cache directory structure
                cls.configure(cls._cache_dir)
                
                # Force save the empty metadata to disk
                cls._save_metadata()
                
                print(f"[FFmpegCache] Successfully cleared {entries_before} cache entries from {cls._cache_dir}")
                return True
                
            except Exception as e:
                print(f"[FFmpegCache] Error clearing cache: {e}")
                return False
        
        return False
    
    @classmethod
    def get_cache_entries_with_sources(cls) -> Dict[str, Any]:
        """Get cache entries mapped to their source files for better visibility. Automatically configures cache if needed."""
        cls.auto_configure()
        
        if not cls._cache_dir:
            return {"enabled": False, "entries": []}
        
        entries = cls._metadata.get("entries", {})
        mapped_entries = []
        
        # First pass: collect all slides and build a sequence map
        slide_operations = ["photo_slide_render", "video_slide_render", "multi_slide_render"]
        slides_by_source = {}  # Maps source path to (mtime, sequence_index)
        
        for cache_key, entry in entries.items():
            source_path = Path(entry.get("input_path", "Unknown"))
            operation = entry.get("params", {}).get("operation", "unknown")
            
            # Collect slide entries to build sequence
            if operation in slide_operations and source_path.exists():
                try:
                    source_mtime = source_path.stat().st_mtime
                    source_key = str(source_path.absolute())
                    slides_by_source[source_key] = source_mtime
                except (OSError, IOError):
                    pass
        
        # Sort slides by mtime to get chronological sequence
        sorted_slides = sorted(slides_by_source.items(), key=lambda x: x[1])
        slide_sequence = {path: idx for idx, (path, mtime) in enumerate(sorted_slides)}
        
        # Second pass: build mapped entries with sequence info
        for cache_key, entry in entries.items():
            source_path = Path(entry.get("input_path", "Unknown"))
            operation = entry.get("params", {}).get("operation", "unknown")
            entry_type = entry.get("type", "unknown")
            size_mb = entry.get("size", 0) / (1024 * 1024)
            
            # Get the cached file path
            if entry_type == "clip":
                cached_file = cls._cache_dir / "clips" / f"{cache_key}.mp4"
            elif entry_type == "frame":
                cached_file = cls._cache_dir / "frames" / f"{cache_key}.png"
            else:
                cached_file = None
            
            # Determine sequence position
            sequence_pos = 999999  # Default for unknown
            sequence_sub = 0  # 0 for slides, 1 for transitions, 2 for frames
            
            if operation == "intro_title_render":
                sequence_pos = -1  # Intro comes first
            elif operation in slide_operations:
                # Regular slide - use its position in the sorted list
                source_key = str(source_path.absolute())
                sequence_pos = slide_sequence.get(source_key, 999999)
            elif operation == "extract_frame":
                # Frame extraction - match to source slide by filename
                # input_path is like "/path/to/IMG_6653_1c397474.mp4" (rendered clip)
                # Extract base name without hash: IMG_6653
                source_name = source_path.stem  # e.g., "IMG_6653_1c397474"
                
                # Remove hash suffix - find the last underscore followed by hex chars
                # IMG_6653_1c397474 -> IMG_6653
                # IMG_6659 -> IMG_6659 (no hash)
                if '_' in source_name:
                    # Split and check if last part looks like a hash (8 hex chars)
                    parts = source_name.rsplit('_', 1)
                    if len(parts) == 2 and len(parts[1]) == 8 and all(c in '0123456789abcdef' for c in parts[1]):
                        base_name = parts[0]
                    else:
                        base_name = source_name
                else:
                    base_name = source_name
                
                # Find matching slide in sequence by exact filename match
                for slide_path, idx in slide_sequence.items():
                    slide_filename = Path(slide_path).stem
                    # Exact match on base name
                    if base_name == slide_filename:
                        sequence_pos = idx
                        sequence_sub = 2  # Frames sort after transitions for same slide
                        break
            elif operation in ["fade_transition", "origami_transition_render"]:
                # Transition - figure out which slide it follows
                # For fade transitions, check params
                from_slide_path = entry.get("params", {}).get("from_slide", "")
                from_slide_name = None
                
                if from_slide_path:
                    # Fade transition: from_slide contains path to rendered clip
                    from_slide_stem = Path(from_slide_path).stem
                    # Remove hash suffix if present (e.g., "IMG_3819_abc123" -> "IMG_3819")
                    from_slide_name = from_slide_stem.split('_')[0] if '_' in from_slide_stem else from_slide_stem
                else:
                    # Origami transition: input_path is like "IMG_6653.HEIC (Duration: 3.00s)_to_IMG_6654.HEIC (Duration: 3.00s)"
                    input_path_str = entry.get("input_path", "")
                    if "_to_" in input_path_str:
                        from_part = input_path_str.split("_to_")[0]
                        # Extract just the filename (remove duration info)
                        if " (Duration:" in from_part:
                            from_slide_name = from_part.split(" (Duration:")[0]
                        else:
                            from_slide_name = from_part
                
                # Find matching slide in sequence
                if from_slide_name:
                    for slide_path, idx in slide_sequence.items():
                        slide_filename = Path(slide_path).name
                        if from_slide_name in slide_filename or slide_filename.startswith(from_slide_name):
                            sequence_pos = idx
                            sequence_sub = 1  # Comes after the slide
                            break
            
            # Get cached file modification time for frames (used for sorting)
            cached_file_mtime = 0
            if cached_file and cached_file.exists():
                try:
                    cached_file_mtime = cached_file.stat().st_mtime
                except (OSError, IOError):
                    pass
            
            mapped_entries.append({
                "cache_key": cache_key,
                "source_file": source_path.name,
                "source_path": str(source_path),
                "operation": operation,
                "type": entry_type,
                "size_mb": round(size_mb, 2),
                "cached_file": str(cached_file) if cached_file else "Unknown",
                "params": entry.get("params", {}),
                "created": entry.get("created", 0),
                "last_accessed": entry.get("last_accessed", entry.get("created", 0)),
                "sequence_pos": sequence_pos,
                "sequence_sub": sequence_sub,
                "cached_file_mtime": cached_file_mtime
            })
        
        # Separate clips and frames for different sorting strategies
        clips = [e for e in mapped_entries if e["type"] == "clip"]
        frames = [e for e in mapped_entries if e["type"] == "frame"]
        
        # Sort clips in video concatenation order: intro → slide1 → transition1 → slide2 → transition2 → ...
        clips.sort(key=lambda x: (x["sequence_pos"], x["sequence_sub"]))
        
        # Sort frames by their cached file modification time (chronological creation order)
        frames.sort(key=lambda x: x["cached_file_mtime"])
        
        # Combine for backward compatibility with existing code
        all_entries = clips + frames
        
        return {
            "enabled": cls._enabled,
            "total_entries": len(all_entries),
            "entries": all_entries,
            "clips": clips,
            "frames": frames
        }

    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """Get cache statistics. Automatically configures cache if needed."""
        cls.auto_configure()
        
        if not cls._cache_dir:
            return {"enabled": False}
            
        entries = cls._metadata.get("entries", {})
        stats = cls._metadata.get("stats", {"hits": 0, "misses": 0})
        total_size = 0
        clip_count = 0
        frame_count = 0
        
        # Count operations by type
        operation_counts = {}
        for entry in entries.values():
            total_size += entry.get("size", 0)
            entry_type = entry.get("type")
            operation = entry.get("params", {}).get("operation", "unknown")
            
            if entry_type == "clip":
                clip_count += 1
            elif entry_type == "frame":
                frame_count += 1
                
            operation_counts[operation] = operation_counts.get(operation, 0) + 1
        
        # Calculate cache effectiveness
        total_requests = stats.get("hits", 0) + stats.get("misses", 0)
        hit_rate = (stats.get("hits", 0) / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "enabled": cls._enabled,
            "cache_dir": str(cls._cache_dir),
            "total_entries": len(entries),
            "clip_count": clip_count,
            "frame_count": frame_count,
            "total_size_mb": total_size / (1024 * 1024),
            "cache_hits": stats.get("hits", 0),
            "cache_misses": stats.get("misses", 0),
            "hit_rate_percent": round(hit_rate, 1),
            "total_requests": total_requests,
            "operations": operation_counts
        }
    
    @classmethod
    def enable(cls, enabled: bool = True):
        """Enable or disable caching."""
        cls._enabled = enabled
    
    @classmethod
    def reset_stats(cls):
        """Reset cache hit/miss statistics. Automatically configures cache if needed."""
        cls.auto_configure()
        
        stats = cls._metadata.setdefault("stats", {})
        stats["hits"] = 0
        stats["misses"] = 0
        cls._save_metadata()
    
    @classmethod
    def invalidate_file(cls, file_path: Union[str, Path]):
        """
        Invalidate all cache entries for a specific input file.
        Automatically configures cache if needed.
        
        This should be called when a file is modified (e.g., rotated),
        to ensure stale cached data is removed.
        
        Args:
            file_path: Path to the file whose cache entries should be invalidated
        """
        cls.auto_configure()
        
        if not cls._cache_dir:
            return
        
        file_path = Path(file_path)
        filename = file_path.name
        entries_to_remove = []
        
        # Find all cache entries that reference this file
        for cache_key, entry in cls._metadata.get("entries", {}).items():
            entry_input = entry.get("input_path", "")
            if Path(entry_input).name == filename:
                entries_to_remove.append(cache_key)
                
                # Remove the actual cached file
                if entry.get("type") == "clip":
                    cached_file = cls._cache_dir / "clips" / f"{cache_key}.mp4"
                elif entry.get("type") == "frame":
                    cached_file = cls._cache_dir / "frames" / f"{cache_key}.png"
                else:
                    continue
                    
                if cached_file.exists():
                    try:
                        cached_file.unlink()
                    except OSError:
                        pass  # Ignore errors during cleanup
        
        # Remove metadata entries
        for cache_key in entries_to_remove:
            if cache_key in cls._metadata.get("entries", {}):
                del cls._metadata["entries"][cache_key]
        
        if entries_to_remove:
            cls._save_metadata()
            print(f"[FFmpegCache] Invalidated {len(entries_to_remove)} cache entries for {filename}")
    
    @classmethod
    def cleanup_old_entries(cls, max_age_days: int = 30):
        """Remove cache entries older than specified days. Automatically configures cache if needed."""
        cls.auto_configure()
        
        if not cls._cache_dir:
            return
            
        import time
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        entries_to_remove = []
        
        for cache_key, entry in cls._metadata.get("entries", {}).items():
            if entry.get("created", 0) < cutoff_time:
                entries_to_remove.append(cache_key)
                
                # Remove the actual file
                if entry.get("type") == "clip":
                    cached_file = cls._cache_dir / "clips" / f"{cache_key}.mp4"
                elif entry.get("type") == "frame":
                    cached_file = cls._cache_dir / "frames" / f"{cache_key}.png"
                else:
                    continue
                    
                if cached_file.exists():
                    cached_file.unlink()
        
        # Remove metadata entries
        for cache_key in entries_to_remove:
            if cache_key in cls._metadata.get("entries", {}):
                del cls._metadata["entries"][cache_key]
        
        if entries_to_remove:
            cls._save_metadata()
            print(f"[FFmpegCache] Cleaned up {len(entries_to_remove)} old cache entries")