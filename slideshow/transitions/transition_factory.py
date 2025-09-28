# slideshow/transitions/transition_factory.py
import random
from slideshow.config import DEFAULT_CONFIG

class TransitionFactory:
    """
    Factory class to create transition instances based on name.
    Supports extension with additional transitions and meta-transitions.
    """

    @staticmethod
    def create(name: str,
               duration: float = DEFAULT_CONFIG["transition_duration"],
               resolution=tuple(DEFAULT_CONFIG["resolution"]),
               fps: int = DEFAULT_CONFIG["fps"]):
        """
        Create and return a transition instance based on its name.

        Args:
            name: Transition type ("fade", "origami", "random", etc.)
            duration: Transition duration in seconds
            resolution: Output resolution (width, height)
            fps: Target framerate

        Returns:
            A transition instance ready to use.
        """
        base = name.lower()

        if base == "fade":
            from slideshow.transitions.fade_transition import FadeTransition
            return FadeTransition(duration=duration)

        if base == "origami":
            from slideshow.transitions.origami_transition import OrigamiTransition
            return OrigamiTransition(duration=duration, resolution=resolution, fps=fps)

        if base in ("random", "rand", "rnd"):
            choice = random.choice(["fade", "origami"])
            return TransitionFactory.create(choice, duration=duration, resolution=resolution, fps=fps)

        raise ValueError(f"Unknown transition type: {name}")
    