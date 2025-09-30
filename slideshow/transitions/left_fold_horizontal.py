# slideshow/transitions/left_fold_horizontal.py
from slideshow.transitions.left_right_fold import LeftRightFold

class LeftFoldHorizontal(LeftRightFold):
    """Left-to-right origami-style fold transition."""
    def __init__(self, **kwargs):
        super().__init__(direction="left", **kwargs)
