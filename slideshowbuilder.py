'''
Build commands:
source .venv/bin/activate
pyinstaller -y "SlideShow Builder.spec"

'''


import os
import sys
import subprocess
from slideshow.gui import GUI

# Register HEIF/HEIC format support with PIL
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # pillow-heif not installed, HEIC files won't be supported

VERSION = "9.6.3"

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
    
    app = GUI(VERSION)
    app.mainloop()

