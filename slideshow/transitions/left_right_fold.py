# slideshow/transitions/left_right_fold.py
from slideshow.transitions.origami_frame_transition import OrigamiFrameTransition

class LeftRightFold(OrigamiFrameTransition):
    """
    Base class for left/right horizontal origami-style folds.
    Provides common attributes and dependency requirements.
    """

    def __init__(self, direction="left", **kwargs):
        super().__init__(**kwargs)
        self.direction = direction  # "left" or "right"

    def get_requirements(self):
        """
        Return list of required dependencies so controller can verify
        them before attempting to run this transition.
        """
        return ["moderngl", "pillow", "numpy", "ffmpeg"]

    def __repr__(self):
        return f"<LeftRightFold direction={self.direction} duration={self.duration}s fps={self.fps}>"
    