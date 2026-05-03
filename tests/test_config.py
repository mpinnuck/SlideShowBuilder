"""
Unit tests for slideshow.config module.

Tests configuration loading, saving, validation, and security features.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from slideshow.config import Config
from tests.conftest import TestHelpers


class TestConfigSingleton:
    """Test Config singleton behavior."""
    
    def test_singleton_instance(self, clean_config):
        """Test that Config maintains singleton pattern."""
        instance1 = Config.instance()
        instance2 = Config.instance()
        assert instance1 is instance2
    
    def test_direct_instantiation_fails(self, clean_config):
        """Test that direct instantiation is prevented."""
        # Create an instance first so _instance is not None
        Config.instance()
        
        # Now direct instantiation should fail
        with pytest.raises(RuntimeError, match="Use Config.instance()"):
            Config()


class TestInputValidation:
    """Test input validation functions."""
    
    def test_validate_fps_valid(self, clean_config):
        """Test FPS validation with valid values."""
        config = Config.instance()
        assert config._validate_fps(30) == 30
        assert config._validate_fps("24") == 24
        assert config._validate_fps(60.0) == 60
        assert config._validate_fps(1) == 1
        assert config._validate_fps(120) == 120
    
    def test_validate_fps_invalid(self, clean_config):
        """Test FPS validation with invalid values."""
        config = Config.instance()
        
        with pytest.raises(ValueError, match="must be positive"):
            config._validate_fps(0)
        
        with pytest.raises(ValueError, match="must be positive"):
            config._validate_fps(-1)
        
        with pytest.raises(ValueError, match="too high"):
            config._validate_fps(500)
        
        with pytest.raises(ValueError, match="must be a number"):
            config._validate_fps("invalid")
    
    def test_validate_duration_valid(self, clean_config):
        """Test duration validation with valid values."""
        config = Config.instance()
        assert config._validate_duration(3.0, "test") == 3.0
        assert config._validate_duration("5.5", "test") == 5.5
        assert config._validate_duration(1, "test") == 1.0
        assert config._validate_duration(3600, "test") == 3600.0
    
    def test_validate_duration_invalid(self, clean_config):
        """Test duration validation with invalid values."""
        config = Config.instance()
        
        with pytest.raises(ValueError, match="must be positive"):
            config._validate_duration(0, "test")
        
        with pytest.raises(ValueError, match="must be positive"):
            config._validate_duration(-1.0, "test")
        
        with pytest.raises(ValueError, match="too long"):
            config._validate_duration(5000, "test")
        
        with pytest.raises(ValueError, match="must be a number"):
            config._validate_duration("invalid", "test")
    
    def test_validate_resolution_valid(self, clean_config):
        """Test resolution validation with valid values."""
        config = Config.instance()
        assert config._validate_resolution([1920, 1080]) == [1920, 1080]
        assert config._validate_resolution((1280, 720)) == [1280, 720]
        assert config._validate_resolution([64, 64]) == [64, 64]
        assert config._validate_resolution([7680, 4320]) == [7680, 4320]
    
    def test_validate_resolution_invalid(self, clean_config):
        """Test resolution validation with invalid values."""
        config = Config.instance()
        
        with pytest.raises(ValueError, match="must be \\[width, height\\]"):
            config._validate_resolution([1920])
        
        with pytest.raises(ValueError, match="must be \\[width, height\\]"):
            config._validate_resolution([1920, 1080, 30])
        
        with pytest.raises(ValueError, match="too small"):
            config._validate_resolution([32, 32])
        
        with pytest.raises(ValueError, match="too large"):
            config._validate_resolution([10000, 10000])
        
        with pytest.raises(ValueError, match="must be even numbers"):
            config._validate_resolution([1921, 1080])
        
        with pytest.raises(ValueError, match="must be integers"):
            config._validate_resolution(["1920", "invalid"])


@pytest.mark.security 
class TestPathTraversalSecurity:
    """Test path traversal security fixes."""
    
    def test_get_project_config_path_safe(self, clean_config, temp_project_dir):
        """Test that _get_project_config_path handles normal paths safely."""
        config = Config.instance()
        output_folder = str(temp_project_dir / "output")
        
        config_path = config._get_project_config_path(output_folder)
        
        # Should be in the parent of output folder
        expected = temp_project_dir / "slideshow_config.json"
        # Compare resolved paths to handle symlinks (macOS /var -> /private/var)
        assert config_path.resolve() == expected.resolve()
        
        # Verify path is resolved and safe
        assert TestHelpers.assert_path_is_safe(config_path, temp_project_dir.parent)
    
    def test_get_project_config_path_blocks_traversal(self, clean_config, temp_project_dir):
        """Test that path traversal attempts are blocked."""
        config = Config.instance()
        
        # These should all be handled safely with .resolve()
        dangerous_paths = [
            "../../../etc",
            str(temp_project_dir / "../../../etc"),
            str(temp_project_dir / "output" / "../../../etc"),
        ]
        
        for dangerous_path in dangerous_paths:
            # Should not raise an exception - .resolve() normalizes the path
            config_path = config._get_project_config_path(dangerous_path)
            
            # The resolved path should not escape to system directories like /etc
            resolved_str = str(config_path.resolve())
            assert not resolved_str.startswith("/etc")
            assert not resolved_str.startswith("/usr")
            assert not resolved_str.startswith("/var")
    
    def test_load_with_invalid_path_fails_gracefully(self, clean_config, temp_project_dir):
        """Test that load() handles path validation errors gracefully."""
        config = Config.instance()
        
        # Mock _get_project_config_path to raise ValueError
        with patch.object(config, '_get_project_config_path') as mock_get_path:
            mock_get_path.side_effect = ValueError("Invalid path")
            
            # Should return default config without crashing
            result = config.load("invalid_path")
            assert result == Config.DEFAULT_CONFIG
            assert config.get("fps") == Config.DEFAULT_CONFIG["fps"]
    
    def test_save_with_invalid_path_fails_gracefully(self, clean_config, temp_project_dir):
        """Test that save() handles path validation errors gracefully.""" 
        config = Config.instance()
        config.set(Config.DEFAULT_CONFIG)
        
        # Mock _get_project_config_path to raise ValueError
        with patch.object(config, '_get_project_config_path') as mock_get_path:
            mock_get_path.side_effect = ValueError("Invalid path")
            
            # Should not crash, just print error and return
            config.save("invalid_path")  # Should not raise exception


class TestConfigValidationIntegration:
    """Test configuration validation integration with set/update/load methods."""
    
    def test_set_with_valid_config(self, clean_config, sample_config):
        """Test that set() works with valid configuration."""
        config = Config.instance()
        config.set(sample_config)
        
        assert config.get("fps") == 30
        assert config.get("resolution") == [1920, 1080]
        assert config.get("photo_duration") == 3.0
    
    def test_set_with_invalid_config_falls_back(self, clean_config, invalid_configs):
        """Test that set() falls back gracefully with invalid configuration."""
        config = Config.instance()
        
        # Test with completely invalid config
        invalid_config = invalid_configs["negative_fps"]
        config.set(invalid_config)
        
        # Should fall back to defaults for invalid parameters
        assert config.get("fps") == Config.DEFAULT_CONFIG["fps"]
    
    def test_update_with_mixed_valid_invalid(self, clean_config, sample_config):
        """Test that update() applies only valid parameters when mixed."""
        config = Config.instance()
        config.set(sample_config)
        
        # Mix of valid and invalid updates
        updates = {
            "fps": 60,  # Valid
            "photo_duration": -1,  # Invalid
            "resolution": [1280, 720]  # Valid
        }
        
        config.update(updates)
        
        # Valid parameters should be applied
        assert config.get("fps") == 60
        assert config.get("resolution") == [1280, 720]
        # Invalid parameter should be ignored, keeping original value
        assert config.get("photo_duration") == 3.0
    
    def test_load_validates_disk_config(self, clean_config, temp_project_dir):
        """Test that load() validates configuration loaded from disk."""
        config = Config.instance()
        
        # Create a config file with invalid data
        config_file = temp_project_dir / "slideshow_config.json"
        invalid_config_data = {
            "fps": -10,  # Invalid
            "resolution": [1920, 1081],  # Invalid (odd number)
            "photo_duration": 3.0  # Valid
        }
        
        config_file.write_text(json.dumps(invalid_config_data))
        
        # Load should validate and keep only valid parameters
        result = config.load(str(temp_project_dir / "output"))
        
        # Valid parameter should be preserved
        assert result["photo_duration"] == 3.0
        # Invalid parameters should be rejected, defaults kept
        # Note: load() now validates each parameter individually during loading
        assert result["fps"] == Config.DEFAULT_CONFIG["fps"]  # Should remain default (30)
        assert result["resolution"] == Config.DEFAULT_CONFIG["resolution"]  # Should remain default [1920, 1080]


class TestConfigPersistence:
    """Test configuration loading and saving."""
    
    def test_save_and_load_roundtrip(self, clean_config, temp_project_dir, sample_config):
        """Test that save and load work correctly together."""
        config = Config.instance()
        config.set(sample_config)
        
        output_folder = str(temp_project_dir / "output")
        
        # Save config
        config.save(output_folder)
        
        # Verify file was created
        config_file = temp_project_dir / "slideshow_config.json"
        assert config_file.exists()
        
        # Load in a fresh instance
        config.clear()
        loaded_config = config.load(output_folder)
        
        # Should match original
        assert loaded_config["project_name"] == sample_config["project_name"]
        assert loaded_config["fps"] == sample_config["fps"]
        assert loaded_config["resolution"] == sample_config["resolution"]
    
    def test_load_nonexistent_uses_defaults(self, clean_config, temp_project_dir):
        """Test that loading from non-existent path uses defaults."""
        config = Config.instance()
        
        nonexistent_output = str(temp_project_dir / "nonexistent" / "output")
        result = config.load(nonexistent_output)
        
        assert result == Config.DEFAULT_CONFIG
    
    def test_load_corrupted_json_uses_defaults(self, clean_config, temp_project_dir):
        """Test that loading corrupted JSON falls back to defaults."""
        config = Config.instance()
        
        # Create corrupted config file
        config_file = temp_project_dir / "slideshow_config.json"
        config_file.write_text("{ invalid json }")
        
        output_folder = str(temp_project_dir / "output")
        result = config.load(output_folder)
        
        # Should fall back to defaults
        assert result == Config.DEFAULT_CONFIG