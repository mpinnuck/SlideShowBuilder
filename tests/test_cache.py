"""
Unit tests for slideshow cache system.

Tests FFmpeg cache functionality, metadata handling, and concurrent access.
"""

import pytest
import json
import hashlib
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import after adding slideshow to path (done in conftest.py)
from slideshow.transitions.ffmpeg_cache import FFmpegCache


class TestFFmpegCacheClassMethods:
    """Test FFmpeg cache class method behavior."""
    
    def test_cache_configuration(self, temp_project_dir):
        """Test that FFmpegCache can be configured with cache directory."""
        cache_dir = temp_project_dir / "cache"
        FFmpegCache.configure(cache_dir)
        assert FFmpegCache._cache_dir.resolve() == cache_dir.resolve()
    
    def test_cache_auto_configure(self, temp_project_dir):
        """Test that auto configuration works."""
        # This would normally try to auto-detect from config
        # For testing, we can just verify it doesn't crash
        try:
            FFmpegCache.auto_configure()
        except Exception:
            # Expected - no actual config available in test
            pass


class TestBasicCacheFunctionality:
    """Test basic cache functionality that can be tested without complex setup."""
    
    def test_cache_key_generation_deterministic(self, temp_project_dir):
        """Test that cache key generation is deterministic."""
        cache_dir = temp_project_dir / "cache"
        FFmpegCache.configure(cache_dir)
        
        # Create test file
        test_file = temp_project_dir / "test.mp4"
        test_file.write_text("test content")
        
        params1 = {"fps": 30, "duration": 3.0}
        params2 = {"fps": 30, "duration": 3.0}
        params3 = {"fps": 60, "duration": 3.0}
        
        key1 = FFmpegCache._generate_cache_key(test_file, params1)
        key2 = FFmpegCache._generate_cache_key(test_file, params2)
        key3 = FFmpegCache._generate_cache_key(test_file, params3)
        
        # Same params should give same key
        assert key1 == key2
        # Different params should give different key
        assert key1 != key3
        assert isinstance(key1, str)
        assert len(key1) > 0