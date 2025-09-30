# slideshow/transitions/right_fold_horizontal.py
from slideshow.transitions.left_right_fold import LeftRightFold

class RightFoldHorizontal(LeftRightFold):
    """Right-to-left origami-style fold transition."""
    def __init__(self, **kwargs):
        super().__init__(direction="right", **kwargs)
