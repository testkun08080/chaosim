"""Abstract base for all simulators."""

from abc import ABC, abstractmethod
from pathlib import Path


class BaseSimulator(ABC):
    """Base class for simulation backends (Blender, Houdini, UE5, etc.)"""

    @abstractmethod
    def setup_scene(self, params: dict) -> None:
        """Configure the simulation scene with given parameters."""
        ...

    @abstractmethod
    def run_simulation(self) -> None:
        """Execute the simulation."""
        ...

    @abstractmethod
    def render(self, output_path: Path, preset: str = "high") -> Path:
        """Render simulation to video file."""
        ...
