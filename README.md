# Slideshow Builder

A Python-based application for creating video slideshows from photos and videos with transitions and soundtrack support.

## Features

- **Mixed Media Support**: Combine photos (JPG, PNG) and videos (MP4, MOV) in a single slideshow
- **Professional Soundtrack Integration**: Add background music with automatic looping and fade effects
- **Smooth Transitions**: Configurable fade transitions between slides
- **Aspect Ratio Preservation**: Maintains original aspect ratios with letterboxing/pillarboxing
- **Real-time Progress Tracking**: Accurate progress indication during video processing
- **QuickTime Integration**: Automatic playback on macOS with QuickTime Player
- **Responsive GUI**: Threaded processing prevents UI freezing during export
- **Configurable Timing**: Customizable durations for photos, videos, and transitions

## Installation

### Prerequisites

- Python 3.12+
- FFmpeg (for video processing)
- Virtual environment recommended

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd SlideShowBuilder
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate     # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install FFmpeg:
   - **macOS**: `brew install ffmpeg`
   - **Ubuntu/Debian**: `sudo apt install ffmpeg`
   - **Windows**: Download from https://ffmpeg.org/

## Usage

### GUI Application

Run the main application:
```bash
python slideshowbuilder.py
```

### Configuration

1. **Project Name**: Set the output video filename
2. **Input Folder**: Select folder containing photos and videos
3. **Output Folder**: Choose where to save the generated video
4. **Durations**: Configure timing for photos, videos, and transitions
5. **Soundtrack**: (Optional) Add background music

### Supported Formats

- **Images**: JPG, JPEG, PNG
- **Videos**: MP4, MOV
- **Audio**: MP3, WAV (for soundtrack)

## Project Structure

```
SlideShowBuilder/
├── slideshow/                  # Core package
│   ├── __init__.py
│   ├── config.py              # Configuration management
│   ├── controller.py          # MVC controller
│   ├── gui.py                 # Tkinter GUI
│   ├── slideshowmodel.py      # Core slideshow logic
│   ├── slides/                # Slide types
│   │   ├── __init__.py
│   │   ├── photo_slide.py     # Photo processing
│   │   ├── slide_item.py      # Base slide class
│   │   └── video_slide.py     # Video processing
│   └── transitions/           # Transition effects
│       ├── __init__.py
│       └── fade_transition.py # Fade effect
├── data/                      # Sample data
│   ├── output/               # Generated videos
│   ├── slides/               # Sample media files
│   └── soundtracks/          # Sample audio files
├── slideshowbuilder.py       # Main entry point
├── requirements.txt          # Python dependencies
├── slideshow_config.json     # Configuration file
└── README.md                 # This file
```

## Development

### Architecture

The application follows a Model-View-Controller (MVC) pattern:

- **Model** (`slideshowmodel.py`): Core slideshow rendering logic
- **View** (`gui.py`): Tkinter-based user interface
- **Controller** (`controller.py`): Coordinates between model and view

### Key Components

- **Slide Processing**: Each media type has its own processor with aspect ratio preservation
- **Threading**: Background processing prevents GUI freezing
- **Progress Tracking**: Weighted progress calculation for accurate time estimation
- **FFmpeg Integration**: Professional video encoding with H264/AAC output

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

- **Codec**: H264 video, AAC audio for QuickTime compatibility
- **Aspect Ratio**: Automatic letterboxing/pillarboxing preservation
- **Transitions**: Crossfade blending between consecutive media
- **Soundtrack Integration**: Automatic audio looping, fade in/out effects, video-audio synchronization
- **Working Directory**: Temporary files cleaned automatically

### Audio Features

- **Format Support**: MP3, WAV audio files
- **Auto-looping**: Soundtrack repeats if shorter than video duration
- **Fade Effects**: 1-second fade in/out for professional quality
- **Audio Mapping**: Proper video-audio synchronization via FFmpeg
- **Graceful Handling**: Continues without audio if soundtrack file missing

### Performance

- **Threading**: Non-blocking GUI during video processing
- **Progress Tracking**: Real-time updates with weighted calculations
- **Memory Management**: Efficient processing of large media files

## Requirements

See `requirements.txt` for complete Python dependencies:
- opencv-python
- numpy
- tkinter (usually included with Python)

## License

[Add your license here]

## Version History

- **v1.0.0**: Initial release with basic slideshow functionality
- Features: Mixed media support, transitions, GUI, progress tracking

## Troubleshooting

### Common Issues

1. **FFmpeg not found**: Ensure FFmpeg is installed and in your PATH
2. **Import errors**: Activate virtual environment and install dependencies
3. **Video playback issues**: Check QuickTime Player is installed (macOS)
4. **Memory issues**: Reduce media file sizes or video resolution

### Support

Create an issue on GitHub with:
- Operating system and version
- Python version
- Error messages and logs
- Steps to reproduce the problem