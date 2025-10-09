# SlideShow Builder

A professional Python-based macOS application for creating stunning video slideshows from photos and videos with advanced transitions, multi-image layouts, and soundtrack support.

## Features

### Core Functionality
- **Mixed Media Support**: Combine photos (JPG, PNG, HEIC) and videos (MP4, MOV) in a single slideshow
  - Full HEIC/HEIF support for iPhone and iPad photos
  - Automatic AAE metadata file filtering (Apple photo edits)
  - System file filtering (.DS_Store, Thumbs.db)
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
- **Configurable Video Quality**: User-selectable encoding presets
  - **Maximum**: Visually lossless quality (CRF 18, ~18-25 Mbps) - best for archival
  - **High**: Excellent quality (CRF 20, ~12-18 Mbps) - recommended for most users
  - **Medium**: Good quality (CRF 23, ~8-12 Mbps) - balanced size/quality
  - **Fast**: Quick encoding (CRF 25, ~5-8 Mbps) - faster exports
  - Automatic cache clearing when quality changes
  - Per-project quality settings saved automatically
- **Intelligent Caching**: FFmpeg output cache for faster re-renders
  - Automatic cache management with hit/miss statistics
  - Browse and inspect cached clips and frames
  - Configurable cache directory and cleanup options
  - Smart cache invalidation on quality or input folder changes

### User Interface
- **Modern Settings Dialog**: Comprehensive tabbed interface for:
  - Transition configuration
  - Title/intro customization  
  - Advanced video and performance settings
  - Cache management tools
- **Project History Dropdown**: Quick access to recent projects
  - Maintains list of last 10 projects (Most Recently Used)
  - Click dropdown to switch between projects instantly
  - Automatically loads all project settings
  - Projects auto-saved when switching
- **Image Preview & Rotation**: Built-in tool to:
  - Preview all images in the input folder
  - Rotate individual images (90° left/right, 180°) and save to disk
  - Navigate with arrow keys or jump to specific images
  - Rotations permanently applied to source files
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

The project includes PyInstaller spec files for creating a native macOS application with two build options:

**Option 1: Multi-File Build (RECOMMENDED)**
```bash
# Activate virtual environment
source .venv/bin/activate

# Build multi-file app (onedir)
pyinstaller -y "SlideShow Builder-onedir.spec"
```

**Pros**: Instant startup (~1 second), standard macOS app bundle  
**Cons**: Larger bundle size (~200MB)

**Option 2: Single-File Build**
```bash
# Activate virtual environment
source .venv/bin/activate

# Build single-file app (onefile)
pyinstaller -y "SlideShow Builder.spec"
```

**Pros**: Smaller executable, cleaner appearance  
**Cons**: Very slow startup (~40 seconds due to extraction overhead)

The built application will be in `dist/SlideShow Builder.app` and can be:
- Launched from Finder by double-clicking
- Copied to `/Applications` for system-wide access
- Distributed to other Macs (ensure they have FFmpeg installed)

**Recommendation**: Use the **multi-file build** for best user experience. The 40-second startup delay of single-file builds makes them impractical for regular use.

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
   - **Video Quality**: Select encoding quality (maximum, high, medium, fast)
     - Higher quality = larger file size and longer export time
     - Changing quality automatically clears cache for fresh rendering

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
   - Video output settings (resolution, FPS)
   - Hardware acceleration (experimental)
   - FFmpeg cache settings:
     - Enable/disable caching
     - Custom cache directory
     - View cache statistics
     - Browse cached files
     - Clear cache or cleanup old entries
   
   **Note**: The main Video Quality setting (maximum/high/medium/fast) is in the main window for quick access, while Advanced settings contain technical video output parameters.

3. **Multi-Image Layouts:**
   - Set "Multi-Slide Frequency" (e.g., 5 = after every 5 photo slides, create 3-photo composite)
   - Requires 3 consecutive photo files to create a multi-slide
   - Videos don't interrupt the photo slide counter
   - Automatically creates attractive multi-image layouts

4. **Image Rotation** (if needed):
   - Click "Preview & Rotate Images" button
   - Navigate through all images with Previous/Next buttons or arrow keys
   - Rotate images that are sideways or upside down:
     - 90° Left: Rotate counter-clockwise
     - 90° Right: Rotate clockwise
     - 180°: Flip upside down
     - Reset: Rotate back to original orientation
   - Jump to specific image number using the "Jump to" field
   - Rotations are **immediately saved to disk** - the source image file is permanently rotated
   - Click "Save & Close" when finished
   - Note: Rotation history is tracked in config for reference purposes
   - Keyboard shortcuts:
     - Left/Right arrows: Navigate images
     - Cmd+Left: Rotate 90° left
     - Cmd+Right: Rotate 90° right

5. **Export:**
   - Click "Export Video"
   - Progress bar shows real-time rendering status
   - Log panel displays detailed processing information
   - Click "Play Slideshow" when complete to preview

### Configuration File

**Two-Level Configuration Architecture:**

SlideShow Builder uses a sophisticated two-level configuration system for flexible project management:

1. **Global App Settings** (`~/SlideshowBuilder/slideshow_settings.json`):
   - Stores application-level preferences
   - Remembers the last opened project path
   - Maintains project history (last 10 projects)
   - Persists across all projects and sessions
   - Automatically created on first launch

2. **Project-Specific Settings** (`<output_folder>/slideshow_config.json`):
   - Each project has its own configuration file
   - Stored in the project's output folder
   - Contains all slideshow settings (durations, transitions, etc.)
   - Automatically loaded when you select an existing project folder

**How It Works:**

- **New Project**: When you set a project name, the app creates a folder structure:
  ```
  media/output/ProjectName/
  ├── slideshow_config.json       # Project settings
  ├── ProjectName.mp4             # Final video (after export)
  └── working/
      └── ffmpeg_cache/           # Cached transitions
  ```

- **Existing Project**: When you select an output folder that already exists:
  - The app detects the existing `slideshow_config.json`
  - Automatically loads all project settings
  - Updates the UI to match the saved configuration
  - Updates global settings to remember this project

- **Project Name Changes**: 
  - Changing the project name automatically updates the output path
  - Uses sanitized names (removes spaces): "My Project" → "MyProject"
  - If the new folder exists, loads that project's settings
  - If new, creates a fresh project with current settings

**User Experience:**
- Settings are preserved when you return to a project
- Each project maintains its own cache for faster re-renders
- Global settings remember your last project for quick resumption
- All configuration happens automatically - no manual file editing needed

## Project Structure

```
SlideShowBuilder/
├── slideshow/                     # Core package
│   ├── __init__.py
│   ├── config.py                 # Two-level configuration system
│   ├── gui.py                    # Tkinter GUI (MVVM View-Model)
│   ├── slideshowmodel.py         # Core slideshow rendering logic (MVVM Model)
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
│       ├── ffmpeg_paths.py       # FFmpeg executable detection
│       └── utils.py              # Shared utilities
├── data/                         # Sample/test data
│   ├── output/                   # Generated videos
│   ├── slides/                   # Sample media files
│   └── soundtracks/              # Sample audio files
├── ~/SlideshowBuilder/           # User config directory
│   └── slideshow_settings.json   # Global app settings
├── slideshowbuilder.py           # Main entry point
├── SlideShow Builder.spec        # PyInstaller build configuration
├── requirements.txt              # Python dependencies
├── icon.icns                     # macOS app icon
└── README.md                     # This file

# Each project folder contains:
<output_folder>/ProjectName/
├── slideshow_config.json         # Project-specific settings
├── ProjectName.mp4               # Exported video
└── working/
    └── ffmpeg_cache/             # Project-specific cache
        ├── clips/
        ├── frames/
        └── temp/
```

## Supported Formats

- **Images**: JPG, JPEG, PNG
- **Videos**: MP4, MOV  
- **Audio**: MP3, WAV (for soundtrack)
- **Output**: MP4 (H.264/AAC, QuickTime compatible)

## Development

### Architecture

The application follows an MVC (Model-View-Controller) architecture with a two-level configuration system:

- **Model** (`slideshowmodel.py`): Core rendering logic with FFmpeg pipeline
  - Slide loading and validation with progress reporting
  - Multi-threaded rendering with real-time progress callbacks
  - Intelligent output caching via FFmpegCache singleton
  
## Architecture

The application follows the **MVVM (Model-View-ViewModel)** pattern:

- **Model** (`slideshowmodel.py`): Core business logic
  - Slide loading and sequencing
  - Multi-slide creation logic (after N photo slides)
  - Video rendering pipeline with FFmpeg
  - Cancellation support via callback
  
- **View-Model** (`gui.py`): UI and application logic
  - Tkinter-based user interface
  - Main window with configuration controls
  - Three-tab Settings dialog (Transitions, Title/Intro, Advanced)
  - Image rotation/preview dialog with slider and delete
  - Configuration persistence via two-level JSON system
  - Direct instantiation of Slideshow model for rendering
  - Progress callbacks and status updates
  - Export cancellation handling
  - FFmpegCache management

### Configuration System

The two-level configuration architecture separates app-wide settings from project-specific settings:

**Global Settings** (`~/SlideshowBuilder/slideshow_settings.json`):
- `last_project_path`: Path to most recently used project
- `project_history`: List of last 10 projects with paths and names
- Application-wide preferences
- Persists across all projects

**Project Settings** (`<output_folder>/ProjectName/slideshow_config.json`):
- All slideshow configuration (durations, transitions, effects, etc.)
- Project-specific output path and name
- Cache directory location
- Merged with defaults on load to ensure backward compatibility

**Key Functions** (`slideshow/config.py`):
- `load_app_settings()`: Load global preferences
- `save_app_settings(settings)`: Save global preferences
- `add_to_project_history(path, name)`: Add/update project in history
- `get_project_history()`: Get list of recent projects
- `load_config(output_folder)`: Load project settings from folder
- `save_config(config, output_folder)`: Save project settings
- `get_project_config_path(output_folder)`: Get path to project config

**Smart Behavior**:
- **New Project**: Creates folder structure with cache, saves config, updates global settings
- **Existing Project**: Loads existing config, updates UI, remembers project in global settings
- **Project Name Change**: Updates path, detects if folder exists, loads or creates accordingly

### Cache System

The `FFmpegCache` singleton (in `slideshow/transitions/ffmpeg_cache.py`) provides intelligent caching of intermediate FFmpeg outputs:

- **Singleton Pattern**: Single cache instance shared across all transitions
- **Configuration**: `configure(cache_dir)` sets output path (must be called before use)
- **Lazy Initialization**: Cache directories created only when needed
- **Statistics Tracking**: Hit/miss counters, total size calculations
- **Browse Support**: Open cache directory in Finder for inspection
- **Clear Function**: One-click cache cleanup from Settings dialog
- **Smart Invalidation**: Automatic cache clearing when:
  - Input folder changes (different source media)
  - Video quality setting changes (encoding parameters changed)

### Video Quality System

Centralized video encoding configuration with user-selectable quality presets (in `slideshow/config.py`):

**Quality Presets** (`FFMPEG_ENCODING_PRESETS`):
```python
{
    "maximum": {
        "crf": "18", "preset": "slow", "profile": "high", "level": "4.1",
        "description": "Visually lossless (~18-25 Mbps)"
    },
    "high": {
        "crf": "20", "preset": "medium", "profile": "high", "level": "4.1",
        "description": "Excellent quality (~12-18 Mbps) - Recommended"
    },
    "medium": {
        "crf": "23", "preset": "medium", "profile": "main", "level": "4.0",
        "description": "Good quality (~8-12 Mbps)"
    },
    "fast": {
        "crf": "25", "preset": "fast", "profile": "main", "level": "4.0",
        "description": "Quick encoding (~5-8 Mbps)"
    }
}
```

**Key Function**:
- `get_ffmpeg_encoding_params(config=None)`: Returns FFmpeg encoding arguments based on `config["video_quality"]`

**Integration**:
- All encoding operations (slides, transitions, final assembly) call this function
- Config parameter threaded through all slide/transition classes
- GUI dropdown allows instant quality switching
- Cache automatically cleared when quality changes to prevent stale renders
- Per-project quality setting saved in `slideshow_config.json`

**User Benefits**:
- **No hardcoded quality**: Single source of truth for all encoding
- **Easy experimentation**: Try different qualities without code changes
- **Predictable file sizes**: Clear bitrate expectations for each preset
- **Performance control**: Trade quality for faster exports when needed

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
- **Source File Properties**: Uses filename and size for cache keys, not intermediate clips
- **Hit Detection**: Instantly reuses existing outputs when parameters match
- **Statistics**: Real-time tracking of cache hits, misses, total size
- **Directory Structure**: Organized subfolders for clips, frames, temp files
- **User Control**: Browse cache in Finder, view statistics, clear old entries
- **Persistence**: Survives between application sessions
- **Per-Project Caching**: Each project has its own cache directory
- **Safety**: Cache configuration must be called before any rendering operation

### FFmpeg Path Detection

The app automatically finds FFmpeg on macOS without requiring PATH configuration:

**FFmpegPaths Singleton** (`slideshow/transitions/ffmpeg_paths.py`):
- Searches standard macOS locations:
  - `/usr/local/bin` (Intel Mac Homebrew)
  - `/opt/homebrew/bin` (Apple Silicon Homebrew)
  - `/usr/bin` (system installation)
- Caches executable paths for performance
- Provides `FFmpegPaths.ffmpeg()` and `FFmpegPaths.ffprobe()` classmethods
- Used throughout the codebase instead of hardcoded "ffmpeg" strings

**Benefits**:
- Works from Finder launch (no terminal PATH needed)
- Supports both Intel and Apple Silicon Macs
- Automatic detection with no configuration required
- Graceful error messages if FFmpeg not found

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
- pillow-heif (for HEIC/HEIF image support from iPhone/iPad)
- tkinter (usually included with Python)

## License

[Add your license here]

## Version History

### v8.1.0 (Current)
Major enhancements and architectural improvements:

**New Features:**
- **Project History Dropdown**: Quick switching between recent projects
  - Dropdown shows last 10 projects (Most Recently Used order)
  - Click any project name to instantly load all its settings
  - Projects automatically saved when switching
  - Smart MRU behavior: recent projects move to top
  - Invalid/deleted projects automatically filtered out
- **Image Preview & Rotation Tool**: Navigate and rotate images before export
  - Preview all images with thumbnail navigation
  - Rotate individual images (90°, 180°, 270°) and save to disk
  - Keyboard shortcuts for quick navigation and rotation
  - Rotations permanently applied to source files (no render-time overhead)
- **Two-Level Configuration System**: Global app settings + per-project configs
- **Project-Based Folder Structure**: Each project gets its own folder with cache
- **Smart Project Detection**: Automatically loads existing projects or creates new ones
- **Focus-Based Updates**: No more keystroke spam, updates only on Tab/Enter
- Multi-image composite layouts (3-photo arrangements)
- Origami fold transitions (center, left-right, up-down, multi-directional)
- Advanced Settings dialog with 3 tabs (Transitions, Title/Intro, Advanced)
- Intro title screen with 3D rotation and customizable styling
- FFmpeg cache system with statistics and management UI
- Progress logging for large file sets (1000+ media files)

**Technical Improvements:**
- **FFmpegPaths singleton**: Automatic FFmpeg detection in standard macOS locations
- **Cache optimization**: Source file properties used for keys, no duplicate caching
- **Configuration architecture**: Separation of app-wide and project-specific settings
- **Project name sanitization**: Removes spaces/hyphens for clean folder names
- FFmpegCache singleton pattern with configure() method
- Proper Finder launch support via FFmpeg path detection
- AppleScript error handling in debugger environments
- Code cleanup (removed diagnostic prints)
- PyInstaller .spec file for reproducible builds
- Cache hit/miss tracking with performance metrics

**UI Enhancements:**
- **Smart folder management**: Detects new vs existing projects
- **User feedback**: Clear logging for project name changes and config operations
- **Auto-path generation**: Project name automatically creates folder structure
- Tabbed settings dialog for organized configuration
- Cache statistics display (hits, misses, total size)
- Browse cache directory directly from app
- Real-time multi-image layout preview
- Status updates during file loading

**Configuration System:**
- Global settings: `~/SlideshowBuilder/slideshow_settings.json`
- Project settings: `<output_folder>/ProjectName/slideshow_config.json`
- Automatic project detection and loading
- Per-project cache directories
- Last project path persistence

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