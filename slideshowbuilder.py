'''
    SlideshowBBuilder for building slideshows from photos and videos.

SlideShowBuilder/
├── slideshowbuilder.py             ← Main entry point
├── slideshow_config.json           ← Project config
├── requirements.txt                ← Dependencies
└── slideshow/
    ├── __init__.py
    ├── config.py
    ├── controller.py
    ├── gui.py
    ├── slideshow.py
    ├── slides/
    │   ├── __init__.py
    │   ├── slide_item.py
    │   ├── photo_slide.py
    │   └── video_slide.py
    └── transitions/
        ├── __init__.py
        └── fade_transition.py
    
source .venv/bin/activate


'''

# Version information
VERSION = "1.0.0"

from slideshow.gui import GUI
from slideshow.controller import SlideshowController

if __name__ == "__main__":
    controller = SlideshowController()
    app = GUI(controller, VERSION)
    app.mainloop()
