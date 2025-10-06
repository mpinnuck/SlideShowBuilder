# SlideShow Builder

A professional Python-based macOS application for creating stunning video slideshows from photos and videos with advanced transitions, multi-image layouts, and soundtrack support.

## Features

### Core Functionality
- **Mixed Media Support**: Combine photos (JPG, PNG) and videos (MP4, MOV) in a single slideshow
- **Multi-Image Layouts**: Automatically create 3-photo composite slides at configurable intervals
- **Advanced Transitions**: 
  - Origami-style paper-folding effects with realistic lighting
  - Multiple fold patterns (left, right, up, down, center, slide, multi-directional)
  - Customizable easing functions (linear, quad, cubic, back)
  - Classic fade transitions
- **Intro Title Screen**: Optional rotating 3D title with customizable:
  - Multi-line text with configurable line spacing
  - Font selection, size, and weight
  - Text and shadow colors (RGBA)
  - Rotation axis and direction
- **Professional Soundtrack Integration**: 
  - Background music with automatic looping and fade effects
  - 1-second audio fade out at video end
- **Intelligent Caching**: FFmpeg output cache for faster re-renders
  - Automatic cache management with hit/miss statistics
  - Browse and inspect cached clips and frames
  - Configurable cache directory and cleanup options

### User Interface
- **Modern Settings Dialog**: Comprehensive tabbed interface for:
  - Transition configuration
  - Title/intro customization  
  - Advanced video and performance settings
  - Cache management tools
- **Real-time Progress Tracking**: 
  - Accurate progress indication during video processing
  - File loading progress (updates every 10 files)
  - Weighted progress for slides, transitions, and assembly
- **Responsive GUI**: Threaded processing prevents UI freezing
- **Log Panel**: 
  - Timestamped messages with copy/paste support
  - Context menu (copy all, copy selected, clear)
  - Keyboard shortcuts (Cmd+C, Cmd+A)
- **QuickTime Integration**: Automatic playback on macOS

### Technical Excellence
- **Aspect Ratio Preservation**: Maintains original ratios with letterboxing/pillarboxing
- **Configurable Timing**: Independent durations for photos, videos, and transitions
- **Smart Video Duration**: Option to use full video length or clip to configured duration
- **Native macOS App**: Builds as standalone .app with Finder launch support

## Installation

### Prerequisites

- **macOS** (tested on macOS 13+)
- **Python 3.12+**
- **FFmpeg** (for video processing)
- **ffprobe** (comes with FFmpeg)

### Setup

1. **Clone the repository:**
```bash
git clone <repository-url>
cd SlideShowBuilder
```

2. **Create and activate virtual environment:**
```bash
python -m venv .venv
source .venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Install FFmpeg:**
```bash
brew install ffmpeg
```

### Building the macOS App

The project includes a configured PyInstaller spec file for creating a native macOS application:

```bash
# Activate virtual environment
source .venv/bin/activate

# Build the app
pyinstaller -y "SlideShow Builder.spec"
```

The built application will be in `dist/SlideShow Builder.app` and can be:
- Launched from Finder by double-clicking
- Copied to `/Applications` for system-wide access
- Distributed to other Macs (ensure they have FFmpeg installed)

## Usage

### Running the Application

**Development mode:**
```bash
python slideshowbuilder.py
```

**Built app:**
- Double-click `SlideShow Builder.app` in Finder
- Or: `open "dist/SlideShow Builder.app"`

### Creating a Slideshow

1. **Basic Setup:**
   - **Project Name**: Output video filename (e.g., "MyVacation")
   - **Input Folder**: Folder containing your photos and videos
   - **Output Folder**: Where to save the generated video
   - **Photo Duration**: How long each photo displays (seconds)
   - **Video Duration**: Maximum video clip length (or -1 for full length)
   - **Transition Duration**: Time for transition effects (seconds)

2. **Advanced Settings** (click Settings button):
   
   **Transitions Tab:**
   - Choose transition type (fade, origami, etc.)
   - Configure origami effects:
     - Animation easing (linear, quad, cubic, back)
     - Realistic lighting on/off
     - Fold direction (or random)
   
   **Title/Intro Tab:**
   - Enable/disable intro title screen
   - Multi-line text with line spacing
   - Font selection and styling
   - Text and shadow colors (RGBA)
   - 3D rotation settings
   
   **Advanced Tab:**
   - Video quality (resolution, FPS)
   - Hardware acceleration (experimental)
   - FFmpeg cache settings:
     - Enable/disable caching
     - Custom cache directory
     - View cache statistics
     - Browse cached files
     - Clear cache or cleanup old entries

3. **Multi-Image Layouts:**
   - Set "Multi-Slide Frequency" (e.g., 10 = every 10th slide becomes 3-photo composite)
   - Automatically creates attractive multi-image layouts

4. **Export:**
   - Click "Export Video"
   - Progress bar shows real-time rendering status
   - Log panel displays detailed processing information
   - Click "Play Slideshow" when complete to preview

### Configuration File

Settings are automatically saved to `slideshow_config.json` and persist between sessions.

## Project Structure

```
SlideShowBuilder/
├── slideshow/                     # Core package
│   ├── __init__.py
│   ├── config.py                 # Configuration management
│   ├── controller.py             # MVC controller
│   ├── gui.py                    # Tkinter GUI with settings dialog
│   ├── slideshowmodel.py         # Core slideshow rendering logic
│   ├── slides/                   # Slide types
│   │   ├── __init__.py
│   │   ├── photo_slide.py        # Photo processing
│   │   ├── video_slide.py        # Video processing
│   │   ├── multi_slide.py        # 3-photo composite layouts
│   │   └── slide_item.py         # Base slide class
│   └── transitions/              # Transition effects
│       ├── __init__.py
│       ├── base_transition.py    # Base transition class
│       ├── fade_transition.py    # Fade effect
│       ├── origami_fold_*.py     # Various origami effects
│       ├── intro_title.py        # Title screen renderer
│       ├── ffmpeg_cache.py       # Intelligent output caching
│       └── utils.py              # Shared utilities
├── data/                         # Sample/test data
│   ├── output/                   # Generated videos
│   ├── slides/                   # Sample media files
│   └── soundtracks/              # Sample audio files
├── slideshowbuilder.py           # Main entry point
├── SlideShow Builder.spec        # PyInstaller build configuration
├── requirements.txt              # Python dependencies
├── slideshow_config.json         # User configuration (auto-saved)
├── icon.icns                     # macOS app icon
└── README.md                     # This file
```

## Supported Formats

- **Images**: JPG, JPEG, PNG
- **Videos**: MP4, MOV  
- **Audio**: MP3, WAV (for soundtrack)
- **Output**: MP4 (H.264/AAC, QuickTime compatible)

## Development

### Architecture

The application follows an MVC (Model-View-Controller) architecture:

- **Model** (`slideshowmodel.py`): Core rendering logic with FFmpeg pipeline
  - Slide loading and validation with progress reporting
  - Multi-threaded rendering with real-time progress callbacks
  - Intelligent output caching via FFmpegCache singleton
  
- **View** (`gui.py`): Tkinter-based user interface
  - Main window with configuration controls
  - Three-tab Settings dialog (Basic, Transitions, Rendering)
  - Real-time preview of multi-image layouts
  - Progress bars and status updates during export
  
- **Controller** (`controller.py`): Mediates between Model and View
  - Event handling and validation
  - Configuration persistence via JSON
  - FFmpegCache initialization at export start

### Cache System

The `FFmpegCache` singleton (in `slideshow/transitions/ffmpeg_cache.py`) provides intelligent caching of intermediate FFmpeg outputs:

- **Singleton Pattern**: Single cache instance shared across all transitions
- **Configuration**: `configure(cache_dir)` sets output path (must be called before use)
- **Lazy Initialization**: Cache directories created only when needed
- **Statistics Tracking**: Hit/miss counters, total size calculations
- **Browse Support**: Open cache directory in Finder for inspection
- **Clear Function**: One-click cache cleanup from Settings dialog

### Key Design Patterns

- **Factory Pattern**: Slide creation based on file type (photo/video/multi-image)
- **Template Method**: Base transition class with customizable render steps
- **Observer Pattern**: Progress callbacks for long-running operations
- **Singleton Pattern**: Global cache instance with controlled initialization

### Key Components

- **Slide Processing**: Each media type has its own processor with aspect ratio preservation
- **Multi-Image Layouts**: Composite rendering with PIL for 3-photo arrangements
- **Threading**: Background processing prevents GUI freezing during export
- **Progress Tracking**: Weighted progress calculation for accurate time estimation
- **FFmpeg Integration**: Professional video encoding with H.264/AAC output

### Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Add tests if applicable
5. Commit your changes: `git commit -am 'Add feature'`
6. Push to the branch: `git push origin feature-name`
7. Submit a pull request

## Technical Details

### Video Processing

- **Codec**: H.264 video, AAC audio for QuickTime compatibility
- **Aspect Ratio**: Automatic letterboxing/pillarboxing preservation
- **Transitions**: Multiple effects (fade, origami fold patterns)
- **Multi-Image Composites**: PIL-based 3-photo layouts with smooth integration
- **Soundtrack Integration**: Automatic audio looping, fade in/out effects, video-audio synchronization
- **Working Directory**: Temporary files cleaned automatically after export

### Audio Features

- **Format Support**: MP3, WAV audio files
- **Auto-looping**: Soundtrack repeats seamlessly if shorter than video duration
- **Fade Effects**: 1-second fade in/out for professional quality
- **Audio Mapping**: Proper video-audio synchronization via FFmpeg
- **Graceful Handling**: Continues without audio if soundtrack file missing

### FFmpeg Cache System

The intelligent caching system dramatically speeds up repeated exports:

- **Cache Key Generation**: SHA-256 hash of render parameters (resolution, transitions, effects)
- **Hit Detection**: Instantly reuses existing outputs when parameters match
- **Statistics**: Real-time tracking of cache hits, misses, total size
- **Directory Structure**: Organized subfolders for clips, frames, temp files
- **User Control**: Browse cache in Finder, view statistics, clear old entries
- **Persistence**: Survives between application sessions
- **Safety**: Cache configuration must be called before any rendering operation

### Performance

- **Threading**: Non-blocking GUI during video processing (prevents app freezing)
- **Progress Tracking**: Real-time updates with weighted calculations for accurate ETAs
- **Memory Management**: Efficient processing of large media libraries (1000+ files)
- **Batch Loading**: Progress indicators show file loading status every 10 items
- **Cache Benefits**: Up to 90% faster rendering on subsequent exports with identical settings

## Requirements

See `requirements.txt` for complete Python dependencies:
- opencv-python
- numpy
- tkinter (usually included with Python)

## License

[Add your license here]

## Version History

### v8.1.0 (Current)
Major enhancements and architectural improvements:

**New Features:**
- Multi-image composite layouts (3-photo arrangements)
- Origami fold transitions (center, left-right, up-down, multi-directional)
- Advanced Settings dialog with 3 tabs (Transitions, Title/Intro, Advanced)
- Intro title screen with 3D rotation and customizable styling
- FFmpeg cache system with statistics and management UI
- Progress logging for large file sets (1000+ media files)

**Technical Improvements:**
- FFmpegCache singleton pattern with configure() method
- Proper Finder launch support via Info.plist LSEnvironment
- AppleScript error handling in debugger environments
- Code cleanup (removed diagnostic prints)
- PyInstaller .spec file for reproducible builds
- Cache hit/miss tracking with performance metrics

**UI Enhancements:**
- Tabbed settings dialog for organized configuration
- Cache statistics display (hits, misses, total size)
- Browse cache directory directly from app
- Real-time multi-image layout preview
- Status updates during file loading

### v1.0.0
Initial release with core slideshow functionality:
- Mixed media support (photos and videos)
- Fade transitions
- Basic GUI with configuration options
- Progress tracking during export

## Troubleshooting

### Common Issues

**App won't launch from Finder (macOS):**
- Ensure FFmpeg is installed via Homebrew: `brew install ffmpeg`
- The .app bundle uses Info.plist LSEnvironment to locate FFmpeg
- Test in Terminal first: `python slideshowbuilder.py`

**FFmpeg not found:**
- Check FFmpeg installation: `which ffmpeg`
- macOS: Install via Homebrew (`brew install ffmpeg`)
- Ensure FFmpeg is in your PATH

**Import errors:**
- Activate virtual environment: `source .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

**Cache issues:**
- Open Settings → Advanced tab → click "Clear Cache"
- Or manually delete `ffmpeg_cache/` directory in output folder
- Check cache statistics to verify it's working

**AppleScript errors in debugger:**
- These are suppressed automatically in the code
- Only affects PyCharm/VS Code debugging, not end users
- App continues normally despite these warnings

**Video playback issues:**
- macOS: QuickTime Player should handle H.264/AAC MP4 files
- Windows: Use VLC Media Player or Windows Media Player
- Check output file isn't corrupted (file size should be > 0 bytes)

**Memory issues with large libraries:**
- Progress logging shows file loading status (every 10 files)
- Consider reducing video resolution in Settings
- Enable FFmpeg cache to speed up subsequent exports

### Support

Create an issue on GitHub with:
- Operating system and version
- Python version
- Error messages and logs
- Steps to reproduce the problem