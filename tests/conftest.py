"""
Test fixtures and utilities for SlideShow Builder tests.

This module provides common fixtures, utilities, and test data
that can be used across multiple test files.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Generator
import pytest

# Add the slideshow module to Python path for testing
sys.path.insert(0, str(Path(__file__).parent.parent))

from slideshow.config import Config


@pytest.fixture(scope="session")
def temp_test_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files that persists for the session."""
    test_dir = Path(tempfile.mkdtemp(prefix="slideshow_test_"))
    try:
        yield test_dir
    finally:
        # Clean up temporary directory
        if test_dir.exists():
            shutil.rmtree(test_dir)


@pytest.fixture(scope="function") 
def temp_project_dir(temp_test_dir, request) -> Generator[Path, None, None]:
    """Create a temporary project directory structure for each test."""
    # Use request.node.name to get the current test name
    test_name = request.node.name.replace("[", "_").replace("]", "_")
    project_dir = temp_test_dir / f"project_{test_name}"
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # Create basic project structure
    slides_dir = project_dir / "slides"
    output_dir = project_dir / "output"
    slides_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    
    # Create some test slide files
    (slides_dir / "test1.jpg").write_text("fake image data")
    (slides_dir / "test2.png").write_text("fake image data")
    (slides_dir / "test3.mp4").write_text("fake video data")
    
    yield project_dir


@pytest.fixture(scope="function")
def clean_config():
    """Ensure Config singleton is clean for each test."""
    # Clear any existing instance
    Config._instance = None
    yield
    # Clean up after test
    if Config._instance:
        Config._instance.clear()
        Config._instance = None


@pytest.fixture
def sample_config() -> dict:
    """Provide a sample valid configuration for testing."""
    return {
        "project_name": "TestProject",
        "fps": 30,
        "resolution": [1920, 1080],
        "photo_duration": 3.0,
        "video_duration": 5.0,
        "transition_duration": 1.0,
        "intro_title": {
            "enabled": True,
            "duration": 5.0,
            "font_size": 120
        }
    }


@pytest.fixture
def invalid_configs() -> dict:
    """Provide various invalid configurations for testing validation."""
    return {
        "negative_fps": {"fps": -10},
        "zero_fps": {"fps": 0},
        "huge_fps": {"fps": 500},
        "string_fps": {"fps": "invalid"},
        "negative_duration": {"photo_duration": -1.0},
        "zero_duration": {"video_duration": 0},
        "huge_duration": {"transition_duration": 5000},
        "odd_resolution": {"resolution": [1921, 1080]},
        "tiny_resolution": {"resolution": [32, 32]},
        "huge_resolution": {"resolution": [10000, 10000]},
        "invalid_resolution_format": {"resolution": [1920]},
        "negative_font_size": {"intro_title": {"font_size": -10}},
        "huge_font_size": {"intro_title": {"font_size": 2000}}
    }


class TestHelpers:
    """Helper utilities for tests."""
    
    @staticmethod
    def create_fake_media_file(path: Path, content: str = "fake data") -> Path:
        """Create a fake media file for testing."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path
    
    @staticmethod
    def assert_path_is_safe(path: Path, base_path: Path) -> bool:
        """Assert that a path doesn't escape from base_path (no path traversal)."""
        try:
            resolved = path.resolve()
            base_resolved = base_path.resolve()
            return str(resolved).startswith(str(base_resolved))
        except Exception:
            return False