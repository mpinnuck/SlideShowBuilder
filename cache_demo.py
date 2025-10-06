#!/usr/bin/env python3
"""
FFmpeg Cache Demo Script

This script demonstrates the FFmpeg caching system for SlideShowBuilder.
It shows cache hits/misses and performance improvements.
"""

import time
from pathlib import Path
from slideshow.transitions.ffmpeg_cache import FFmpegCache
from slideshow.transitions.utils import extract_frame

def demo_cache():
    """Demonstrate the FFmpeg cache functionality."""
    print("=== FFmpeg Cache Demo ===\n")
    
    # Initialize cache in output folder structure
    cache_dir = Path("data/output/working/ffmpeg_cache")
    FFmpegCache.initialize(cache_dir)
    print(f"Using cache directory: {cache_dir}\n")
    
    # Show initial cache stats
    stats = FFmpegCache.get_cache_stats()
    print(f"Initial cache stats: {stats}\n")
    
    # Find a video file for testing
    test_video = None
    for video_path in Path("data/slides").glob("*.MOV"):
        if video_path.exists():
            test_video = video_path
            break
    
    if not test_video:
        print("No test video found in data/slides/")
        return
    
    print(f"Testing with video: {test_video.name}\n")
    
    # First extraction (should miss cache)
    print("🔄 First frame extraction (cache miss expected)...")
    start_time = time.time()
    frame1 = extract_frame(test_video, last=False)
    first_duration = time.time() - start_time
    print(f"✅ Completed in {first_duration:.2f}s - Frame size: {frame1.size}")
    
    # Second extraction (should hit cache)
    print("\n🔄 Second frame extraction (cache hit expected)...")
    start_time = time.time()
    frame2 = extract_frame(test_video, last=False)
    second_duration = time.time() - start_time
    print(f"✅ Completed in {second_duration:.2f}s - Frame size: {frame2.size}")
    
    # Calculate speedup
    if second_duration > 0:
        speedup = first_duration / second_duration
        print(f"\n🚀 Cache speedup: {speedup:.1f}x faster!")
    
    # Show final cache stats
    final_stats = FFmpegCache.get_cache_stats()
    print(f"\nFinal cache stats: {final_stats}")
    
    # Show cache directory contents
    cache_dir = Path(final_stats['cache_dir'])
    if cache_dir.exists():
        print(f"\nCache directory contents:")
        for subdir in ['clips', 'frames']:
            subpath = cache_dir / subdir
            if subpath.exists():
                files = list(subpath.glob("*"))
                print(f"  {subdir}/: {len(files)} files")
                for f in files[:3]:  # Show first 3 files
                    size_mb = f.stat().st_size / (1024 * 1024)
                    print(f"    - {f.name} ({size_mb:.2f} MB)")
                if len(files) > 3:
                    print(f"    ... and {len(files) - 3} more")
    
    print("\n=== Demo Complete ===")

if __name__ == "__main__":
    demo_cache()