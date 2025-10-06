#!/usr/bin/env python3
"""
Cache inspection utility for SlideShowBuilder FFmpeg cache.
Shows the mapping between cached files and their source slides.
"""

import sys
from pathlib import Path
from slideshow.transitions.ffmpeg_cache import FFmpegCache

def inspect_cache(cache_dir=None):
    """Inspect and display cache contents with source file mappings."""
    
    if cache_dir is None:
        cache_dir = Path("data/output/working/ffmpeg_cache")
    else:
        cache_dir = Path(cache_dir)
    
    print(f"Inspecting FFmpeg Cache: {cache_dir}")
    print("=" * 60)
    
    # Initialize cache
    FFmpegCache.initialize(cache_dir)
    
    # Get basic stats
    stats = FFmpegCache.get_cache_stats()
    if not stats.get("enabled", False):
        print("Cache is disabled or not found.")
        return
    
    print(f"Cache Statistics:")
    print(f"  Total Entries: {stats['total_entries']}")
    print(f"  Video Clips: {stats['clip_count']}")  
    print(f"  Extracted Frames: {stats['frame_count']}")
    print(f"  Total Size: {stats['total_size_mb']:.1f} MB")
    print(f"  Hit Rate: {stats.get('hit_rate_percent', 0)}%")
    print()
    
    # Get detailed entries
    cache_data = FFmpegCache.get_cache_entries_with_sources()
    entries = cache_data.get("entries", [])
    
    if not entries:
        print("No cache entries found.")
        return
    
    # Group by operation type
    operations = {}
    for entry in entries:
        op = entry["operation"]
        if op not in operations:
            operations[op] = []
        operations[op].append(entry)
    
    for operation, op_entries in operations.items():
        print(f"\\n{operation.upper()} Operations ({len(op_entries)} entries):")
        print("-" * 40)
        
        for entry in op_entries:
            print(f"  Source: {entry['source_file']}")
            print(f"  Cache:  {entry['cache_key']}.{entry['type']}")
            print(f"  Size:   {entry['size_mb']} MB")
            
            # Show key parameters
            params = entry.get("params", {})
            if "duration" in params:
                print(f"  Duration: {params['duration']}s")
            if "resolution" in params:
                print(f"  Resolution: {params['resolution'][0]}x{params['resolution'][1]}")
            if "fps" in params:
                print(f"  FPS: {params['fps']}")
            print()

def main():
    cache_dir = None
    if len(sys.argv) > 1:
        cache_dir = sys.argv[1]
    
    try:
        inspect_cache(cache_dir)
    except Exception as e:
        print(f"Error inspecting cache: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()