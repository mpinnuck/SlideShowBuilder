# Video Quality Configuration Guide

## Overview

All video encoding in SlideShow Builder now uses centralized quality settings defined in `slideshow/config.py`. This makes it easy to adjust the quality vs file size tradeoff for your specific needs.

## Quick Start: Changing Video Quality

To change the video quality for all exports, edit **one line** in `slideshow/config.py`:

```python
FFMPEG_QUALITY_PRESET = "maximum"  # Change this value
```

Available presets:
- `"maximum"` - Visually lossless quality (~18-25 Mbps) - **Current default**
- `"high"` - Excellent quality, good compression (~12-18 Mbps) - **Recommended for most uses**
- `"medium"` - Good quality, smaller files (~8-12 Mbps) - **Good for streaming/sharing**
- `"fast"` - Acceptable quality, fast encoding (~5-8 Mbps) - **For testing/preview**

## Quality Preset Details

### Maximum Quality (Current Setting)
```python
FFMPEG_QUALITY_PRESET = "maximum"
```
- **CRF**: 18 (visually lossless)
- **Preset**: slow (best compression algorithm)
- **Profile**: high (all H.264 features enabled)
- **Use for**: USB playback, archival, when quality matters most
- **Tradeoff**: Larger files, slower encoding
- **Encoding speed**: ~7-8 seconds per slide

### High Quality (Recommended)
```python
FFMPEG_QUALITY_PRESET = "high"
```
- **CRF**: 20 (excellent quality)
- **Preset**: medium (balanced compression)
- **Profile**: high
- **Use for**: Most purposes, great balance of quality and file size
- **Tradeoff**: Very minor quality difference from maximum, 30-40% smaller files
- **Encoding speed**: ~4-5 seconds per slide

### Medium Quality
```python
FFMPEG_QUALITY_PRESET = "medium"
```
- **CRF**: 23 (good quality)
- **Preset**: medium
- **Profile**: main (standard compatibility)
- **Use for**: Streaming, sharing online, when file size matters
- **Tradeoff**: Visible quality difference on large screens, 50-60% smaller files
- **Encoding speed**: ~4-5 seconds per slide

### Fast Encoding
```python
FFMPEG_QUALITY_PRESET = "fast"
```
- **CRF**: 25 (acceptable quality)
- **Preset**: fast (quick encoding)
- **Profile**: main
- **Use for**: Testing, preview, draft exports
- **Tradeoff**: Noticeable quality reduction, smallest files
- **Encoding speed**: ~2-3 seconds per slide

## What Gets Affected

Changing `FFMPEG_QUALITY_PRESET` affects **all** video encoding operations:
- ✅ Final slideshow assembly
- ✅ Multi-slide rendering (3-video composites)
- ✅ Fade transitions
- ✅ Origami transitions
- ✅ Intro title animation
- ✅ All intermediate video processing

## Technical Details

### CRF (Constant Rate Factor)
- Lower values = better quality, larger files
- Range: 0-51 (0 = lossless, 51 = worst quality)
- **18-20**: Visually transparent to lossless
- **21-23**: High quality, standard for professional use
- **24-28**: Medium quality, good for streaming

### Preset (Encoding Speed)
- Affects compression efficiency, not quality
- Slower presets = better compression at same quality
- Options: ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
- **slow**: Best balance of encoding time and compression
- **medium**: Good balance, faster encoding
- **fast**: Quick encoding, less efficient compression

### Profile
- **high**: Maximum features, best quality (requires modern devices)
- **main**: Good compatibility, standard features
- **baseline**: Maximum compatibility (older devices)

## File Size Comparison

For a 1080p video with typical slideshow content:

| Preset | Approx. Bitrate | 1-min video | 10-min video | Quality |
|--------|----------------|-------------|--------------|---------|
| Maximum | 18-25 Mbps | ~150 MB | ~1.5 GB | Visually lossless |
| High | 12-18 Mbps | ~100 MB | ~1.0 GB | Excellent |
| Medium | 8-12 Mbps | ~70 MB | ~700 MB | Good |
| Fast | 5-8 Mbps | ~50 MB | ~500 MB | Acceptable |

## Recommendations

### For USB/Apple TV Playback
Use `"maximum"` or `"high"` - Quality is worth the file size when playing locally.

### For AirPlay Streaming
Use `"high"` or `"medium"` - Some devices have limited AirPlay buffers.

### For YouTube/Vimeo Upload
Use `"high"` - They will re-encode anyway, so maximum quality is overkill.

### For Sharing via Email/Cloud
Use `"medium"` - Smaller files upload/download faster.

### For Testing During Development
Use `"fast"` - Quick exports to verify your slideshow works.

## Advanced: Per-Operation Quality

If you need different quality settings for different operations (e.g., maximum quality for final assembly but medium for transitions), you can pass a quality preset to `get_ffmpeg_encoding_params()`:

```python
# In your code
from slideshow.config import get_ffmpeg_encoding_params

# Use a specific preset
cmd.extend(get_ffmpeg_encoding_params("high"))

# Or use the global default
cmd.extend(get_ffmpeg_encoding_params())
```

## Cache Behavior

The FFmpeg cache keys include the quality settings, so:
- ✅ Changing quality will invalidate cached transitions/effects
- ✅ Each quality preset maintains its own cache entries
- ✅ You can safely switch between presets - cache will rebuild as needed

## Questions?

**Q: Should I always use maximum quality?**
A: Not necessarily. "High" quality is visually indistinguishable for most content and renders 40% faster.

**Q: Will this affect my existing projects?**
A: Yes, all future exports will use the new quality setting. Existing exported videos are unchanged.

**Q: Can I create my own custom preset?**
A: Yes! Add a new entry to `FFMPEG_ENCODING_PRESETS` in `config.py` with your custom settings.

**Q: What if I want different quality for photos vs videos?**
A: Currently, the quality setting is global. Per-slide-type quality would require code changes.
