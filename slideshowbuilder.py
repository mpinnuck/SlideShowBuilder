'''
Build commands:
source .venv/bin/activate
pyinstaller -y "SlideShow Builder.spec"

'''


import os
import sys
import subprocess
from slideshow.gui import GUI
from slideshow.controller import SlideshowController

VERSION = "8.4.0"

if __name__ == "__main__":
    # Bring app to foreground on macOS (fail silently if error)
    if sys.platform == "darwin":
        try:
            subprocess.run(
                ['osascript', '-e', 
                 f'tell application "System Events" to set frontmost of the first process whose unix id is {os.getpid()} to true'],
                capture_output=True,
                timeout=1
            )
        except Exception:
            pass  # Not critical, continue anyway
    
    controller = SlideshowController()
    app = GUI(controller, VERSION)
    app.mainloop()

