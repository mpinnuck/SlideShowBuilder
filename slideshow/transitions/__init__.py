"""
Slideshow transition effects module

This module provides various transition effects for slideshow videos,
including simple fades and complex 3D origami-style transitions.
"""

from .base_transition import BaseTransition
from .fade_transition import FadeTransition
from .origami_transition import OrigamiTransition

# Registry of available transitions
AVAILABLE_TRANSITIONS = {
    'fade': FadeTransition,
    'origami': OrigamiTransition,
}

def get_transition(name: str, **kwargs):
    """
    Get a transition instance by name
    
    Args:
        name: Transition name ('fade', 'origami')
        **kwargs: Parameters to pass to transition constructor
        
    Returns:
        Transition instance
        
    Raises:
        ValueError: If transition name is not recognized
    """
    if name not in AVAILABLE_TRANSITIONS:
        available = ', '.join(AVAILABLE_TRANSITIONS.keys())
        raise ValueError(f"Unknown transition '{name}'. Available: {available}")
    
    transition_class = AVAILABLE_TRANSITIONS[name]
    return transition_class(**kwargs)

def list_available_transitions():
    """
    Get list of available transition names
    
    Returns:
        List of transition names that can be used
    """
    available = []
    for name, transition_class in AVAILABLE_TRANSITIONS.items():
        # Test if transition dependencies are available
        try:
            instance = transition_class()
            if instance.is_available():
                available.append({
                    'name': name,
                    'display_name': instance.name,
                    'description': instance.description
                })
        except Exception:
            # Skip transitions that can't be instantiated
            pass
    
    return available

__all__ = [
    'BaseTransition',
    'FadeTransition', 
    'OrigamiTransition',
    'AVAILABLE_TRANSITIONS',
    'get_transition',
    'list_available_transitions'
]