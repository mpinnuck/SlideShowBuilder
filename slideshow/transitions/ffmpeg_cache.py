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
            cls._metadata.setdefault("stats", {})["misses"] = cls._metadata["stats"].get("misses", 0) + 1
            return None
            
        cache_key = cls._generate_cache_key(input_path, params)
        
        # Check if entry exists in metadata
        if cache_key not in cls._metadata.get("entries", {}):
            cls._metadata.setdefault("stats", {})["misses"] = cls._metadata["stats"].get("misses", 0) + 1
            cls._save_metadata()
            return None
            
        # Check if cached file actually exists
        cached_file = cls._cache_dir / "clips" / f"{cache_key}.mp4"
        if not cached_file.exists():
            # Clean up stale metadata entry
            del cls._metadata["entries"][cache_key]
            cls._metadata.setdefault("stats", {})["misses"] = cls._metadata["stats"].get("misses", 0) + 1
            cls._save_metadata()
            return None
        
        # Cache hit!
        cls._metadata.setdefault("stats", {})["hits"] = cls._metadata["stats"].get("hits", 0) + 1
        
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
            cls._metadata.setdefault("stats", {})["misses"] = cls._metadata["stats"].get("misses", 0) + 1
            return None
            
        cache_key = cls._generate_cache_key(input_path, params)
        
        # Check if entry exists in metadata
        if cache_key not in cls._metadata.get("entries", {}):
            cls._metadata.setdefault("stats", {})["misses"] = cls._metadata["stats"].get("misses", 0) + 1
            cls._save_metadata()
            return None
            
        # Check if cached file actually exists
        cached_file = cls._cache_dir / "frames" / f"{cache_key}.png"
        if not cached_file.exists():
            # Clean up stale metadata entry
            del cls._metadata["entries"][cache_key]
            cls._metadata.setdefault("stats", {})["misses"] = cls._metadata["stats"].get("misses", 0) + 1
            cls._save_metadata()
            return None
        
        # Cache hit!
        cls._metadata.setdefault("stats", {})["hits"] = cls._metadata["stats"].get("hits", 0) + 1
        
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
    def clear_cache(cls):
        """Clear all cached files and metadata."""
        if cls._cache_dir and cls._cache_dir.exists():
            shutil.rmtree(cls._cache_dir)
            cls._metadata = {"version": "1.0", "entries": {}, "stats": {"hits": 0, "misses": 0}}
            cls._initialized = False
            cls.configure(cls._cache_dir)
    
    @classmethod
    def get_cache_entries_with_sources(cls) -> Dict[str, Any]:
        """Get cache entries mapped to their source files for better visibility."""
        if not cls._cache_dir:
            return {"enabled": False, "entries": []}
        
        entries = cls._metadata.get("entries", {})
        mapped_entries = []
        
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
                "last_accessed": entry.get("last_accessed", entry.get("created", 0))
            })
        
        # Sort by source file name for easier browsing
        mapped_entries.sort(key=lambda x: x["source_file"])
        
        return {
            "enabled": cls._enabled,
            "total_entries": len(mapped_entries),
            "entries": mapped_entries
        }

    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """Get cache statistics."""
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
        """Reset cache hit/miss statistics."""
        cls._metadata.setdefault("stats", {})["hits"] = 0
        cls._metadata.setdefault("stats", {})["misses"] = 0
        cls._save_metadata()
    
    @classmethod
    def invalidate_file(cls, file_path: Union[str, Path]):
        """
        Invalidate all cache entries for a specific input file.
        
        This should be called when a file is modified (e.g., rotated),
        to ensure stale cached data is removed.
        
        Args:
            file_path: Path to the file whose cache entries should be invalidated
        """
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
        """Remove cache entries older than specified days."""
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