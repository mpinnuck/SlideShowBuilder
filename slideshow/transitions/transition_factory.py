# slideshow/transitions/transition_factory.py
import random
from slideshow.config import Config, DEFAULT_CONFIG

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
        from slideshow.transitions.fade_transition import FadeTransition
        from slideshow.transitions.origami_transition import OrigamiTransition

        # Extract origami-specific settings from config
        config = Config.instance().get_all()
        origami_kwargs = {
            'easing': config.get('origami_easing', 'quad'),
            'lighting': config.get('origami_lighting', True),
            'fold': config.get('origami_fold', ''),  # Empty string means deterministic
            'project_name': config.get('project_name', 'default')
        }

        TRANSITIONS = {
            "fade": lambda: FadeTransition(duration=duration),
            "origami": lambda: OrigamiTransition(
                duration=duration, 
                resolution=resolution, 
                fps=fps,
                **origami_kwargs
            ),
        }

        base = name.lower()

        if base in ("random", "rand", "rnd"):
            base = random.choice(list(TRANSITIONS.keys()))

        if base in TRANSITIONS:
            return TRANSITIONS[base]()

        raise ValueError(f"Unknown transition type: {name}")