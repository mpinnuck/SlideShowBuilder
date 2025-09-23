from abc import ABC, abstractmethod
from pathlib import Path

class SlideItem(ABC):
    def __init__(self, path: Path, duration: float):
        self.path = path
        self.duration = duration

    @abstractmethod
    def render(self, output_path: Path, resolution: tuple[int, int], fps: int):
        pass
