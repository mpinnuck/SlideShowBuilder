'''
    SlideshowBBuilder for building slideshows from photos and videos.

    Setup Instructions:   
source .venv/bin/activate
pip install -r requirements.txt

'''

# Version information
VERSION = "5.2.0"

from slideshow.gui import GUI
from slideshow.controller import SlideshowController

if __name__ == "__main__":
    controller = SlideshowController()
    app = GUI(controller, VERSION)
    app.mainloop()
