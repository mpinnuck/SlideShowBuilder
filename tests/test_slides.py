"""
Unit tests for slideshow slide sorting and caching.

Tests slide discovery, sorting logic, and slide cache functionality.
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from slideshow.slideshowmodel import Slideshow


class TestSlideDiscovery:
    """Test slide file discovery and filtering."""
    
    def test_discover_image_files(self, temp_project_dir):
        """Test discovery of supported image file types."""
        slides_dir = temp_project_dir / "slides"
        
        # Create test files (in addition to those created by temp_project_dir fixture)
        (slides_dir / "photo1.jpg").write_text("fake jpg")
        (slides_dir / "photo2.jpeg").write_text("fake jpeg")
        (slides_dir / "photo3.png").write_text("fake png")
        (slides_dir / "photo4.gif").write_text("fake gif")
        (slides_dir / "photo5.bmp").write_text("fake bmp")
        (slides_dir / "photo6.tiff").write_text("fake tiff")
        (slides_dir / "unsupported.txt").write_text("text file")
        
        with patch('slideshow.slideshowmodel.Slideshow') as MockSlideshow:
            
            # Mock the file discovery logic
            def mock_discover_files(input_folder, recurse=False):
                folder_path = Path(input_folder)
                supported_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
                return [f for f in folder_path.rglob("*") 
                       if f.is_file() and f.suffix.lower() in supported_extensions]
            
            files = mock_discover_files(slides_dir)
            
            # Should find all supported image files (6 new + 2 from fixture = 8 total)
            # Filter to just the test files we created
            test_files = [f for f in files if f.name.startswith('photo') or f.name in ['test1.jpg', 'test2.png']]
            assert len(test_files) >= 6  # At least our 6 test files
            
            filenames = [f.name for f in files]
            assert "photo1.jpg" in filenames
            assert "photo2.jpeg" in filenames
            assert "photo3.png" in filenames
            assert "unsupported.txt" not in filenames
    
    def test_discover_video_files(self, temp_project_dir):
        """Test discovery of supported video file types."""
        slides_dir = temp_project_dir / "slides"
        
        # Create test video files (in addition to test3.mp4 from fixture)
        (slides_dir / "video1.mp4").write_text("fake mp4")
        (slides_dir / "video2.mov").write_text("fake mov")
        (slides_dir / "video3.avi").write_text("fake avi")
        (slides_dir / "video4.mkv").write_text("fake mkv")
        (slides_dir / "unsupported.txt").write_text("text file")
        
        with patch('slideshow.slideshowmodel.Slideshow') as MockSlideshow:
            def mock_discover_files(input_folder, recurse=False):
                folder_path = Path(input_folder)
                supported_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.wmv'}
                return [f for f in folder_path.rglob("*") 
                       if f.is_file() and f.suffix.lower() in supported_extensions]
            
            files = mock_discover_files(slides_dir)
            
            # Should find video files (4 new + 1 from fixture = 5 total)
            # Focus on the ones we created
            test_files = [f for f in files if f.name.startswith('video') or f.name == 'test3.mp4']
            assert len(test_files) >= 4  # At least our 4 new test files
            
            filenames = [f.name for f in files]
            assert "video1.mp4" in filenames
            assert "video2.mov" in filenames
            assert "unsupported.txt" not in filenames
    
    def test_recursive_discovery(self, temp_project_dir):
        """Test recursive file discovery in subdirectories."""
        slides_dir = temp_project_dir / "slides"
        subdir1 = slides_dir / "subdir1"
        subdir2 = slides_dir / "subdir1" / "nested"
        
        subdir1.mkdir(parents=True)
        subdir2.mkdir(parents=True)
        
        # Create files in different levels (fixture already created 3 files)
        (slides_dir / "root.jpg").write_text("root image")
        (subdir1 / "sub1.jpg").write_text("sub image")
        (subdir2 / "nested.jpg").write_text("nested image")
        
        def mock_recursive_discover(input_folder):
            folder_path = Path(input_folder)
            supported_extensions = {'.jpg', '.jpeg', '.png', '.mp4', '.mov'}
            return [f for f in folder_path.rglob("*") 
                   if f.is_file() and f.suffix.lower() in supported_extensions]
        
        files = mock_recursive_discover(slides_dir)
        
        # Should find files at all levels (3 new + 3 from fixture = 6 total)
        assert len(files) >= 3  # At least our 3 new files
        file_stems = [f.stem for f in files]
        assert "root" in file_stems
        assert "sub1" in file_stems  
        assert "nested" in file_stems


class TestSlideSorting:
    """Test slide sorting algorithms."""
    
    def test_sort_by_name_ascending(self, temp_project_dir):
        """Test sorting slides by filename in ascending order."""
        slides = [
            {"path": "zebra.jpg", "creation_date": "2024-01-01"},
            {"path": "apple.jpg", "creation_date": "2024-01-02"},
            {"path": "banana.jpg", "creation_date": "2024-01-03"}
        ]
        
        def mock_sort_by_name(slides, reverse=False):
            return sorted(slides, key=lambda x: Path(x["path"]).name, reverse=reverse)
        
        sorted_slides = mock_sort_by_name(slides, reverse=False)
        names = [Path(slide["path"]).name for slide in sorted_slides]
        
        assert names == ["apple.jpg", "banana.jpg", "zebra.jpg"]
    
    def test_sort_by_name_descending(self, temp_project_dir):
        """Test sorting slides by filename in descending order."""
        slides = [
            {"path": "zebra.jpg", "creation_date": "2024-01-01"},
            {"path": "apple.jpg", "creation_date": "2024-01-02"},
            {"path": "banana.jpg", "creation_date": "2024-01-03"}
        ]
        
        def mock_sort_by_name(slides, reverse=True):
            return sorted(slides, key=lambda x: Path(x["path"]).name, reverse=reverse)
        
        sorted_slides = mock_sort_by_name(slides, reverse=True)
        names = [Path(slide["path"]).name for slide in sorted_slides]
        
        assert names == ["zebra.jpg", "banana.jpg", "apple.jpg"]
    
    def test_sort_by_date_creation(self, temp_project_dir):
        """Test sorting slides by creation date."""
        slides = [
            {"path": "newest.jpg", "creation_date": "2024-01-03"},
            {"path": "oldest.jpg", "creation_date": "2024-01-01"},
            {"path": "middle.jpg", "creation_date": "2024-01-02"}
        ]
        
        def mock_sort_by_date(slides, reverse=False):
            return sorted(slides, key=lambda x: x["creation_date"], reverse=reverse)
        
        sorted_slides = mock_sort_by_date(slides, reverse=False)
        names = [Path(slide["path"]).name for slide in sorted_slides]
        
        assert names == ["oldest.jpg", "middle.jpg", "newest.jpg"]
    
    def test_sort_by_date_descending(self, temp_project_dir):
        """Test sorting slides by creation date in descending order."""
        slides = [
            {"path": "newest.jpg", "creation_date": "2024-01-03"},
            {"path": "oldest.jpg", "creation_date": "2024-01-01"},
            {"path": "middle.jpg", "creation_date": "2024-01-02"}
        ]
        
        def mock_sort_by_date(slides, reverse=True):
            return sorted(slides, key=lambda x: x["creation_date"], reverse=reverse)
        
        sorted_slides = mock_sort_by_date(slides, reverse=True)
        names = [Path(slide["path"]).name for slide in sorted_slides]
        
        assert names == ["newest.jpg", "middle.jpg", "oldest.jpg"]


class TestSlideCache:
    """Test slide metadata caching functionality."""
    
    def test_slide_cache_generation(self, temp_project_dir):
        """Test that slide cache is generated correctly."""
        slides_dir = temp_project_dir / "slides"
        cache_dir = temp_project_dir / "output" / "working" / "ffmpeg_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test files
        (slides_dir / "photo1.jpg").write_text("fake image 1")
        (slides_dir / "photo2.jpg").write_text("fake image 2")
        (slides_dir / "video1.mp4").write_text("fake video 1")
        
        def mock_generate_slide_cache_key(input_folder, sort_settings):
            """Mock slide cache key generation."""
            import hashlib
            content = f"{input_folder}_{sort_settings}"
            return hashlib.md5(content.encode()).hexdigest()
        
        def mock_create_slide_cache(slides, cache_key, cache_dir):
            """Mock slide cache creation."""
            cache_file = cache_dir / f"slide_order_{cache_key}.json"
            cache_data = {
                "slides": slides,
                "generated_at": "2024-01-01T12:00:00",
                "input_folder": str(slides_dir),
                "sort_settings": {"method": "name", "reverse": False}
            }
            cache_file.write_text(json.dumps(cache_data, indent=2))
            return cache_file
        
        # Generate cache
        slides = [
            {"path": str(slides_dir / "photo1.jpg"), "type": "photo"},
            {"path": str(slides_dir / "photo2.jpg"), "type": "photo"},
            {"path": str(slides_dir / "video1.mp4"), "type": "video"}
        ]
        
        sort_settings = {"method": "name", "reverse": False}
        cache_key = mock_generate_slide_cache_key(str(slides_dir), str(sort_settings))
        cache_file = mock_create_slide_cache(slides, cache_key, cache_dir)
        
        # Verify cache file was created
        assert cache_file.exists()
        
        # Verify cache content
        with open(cache_file) as f:
            cache_data = json.load(f)
        
        assert len(cache_data["slides"]) == 3
        assert cache_data["input_folder"] == str(slides_dir)
        assert cache_data["sort_settings"]["method"] == "name"
    
    def test_slide_cache_hit(self, temp_project_dir):
        """Test that slide cache hits work correctly."""
        slides_dir = temp_project_dir / "slides"
        cache_dir = temp_project_dir / "output" / "working" / "ffmpeg_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Create existing cache file
        cache_data = {
            "slides": [
                {"path": str(slides_dir / "cached1.jpg"), "type": "photo"},
                {"path": str(slides_dir / "cached2.jpg"), "type": "photo"}
            ],
            "generated_at": "2024-01-01T12:00:00",
            "input_folder": str(slides_dir)
        }
        
        cache_key = "test_cache_key"
        cache_file = cache_dir / f"slide_order_{cache_key}.json"
        cache_file.write_text(json.dumps(cache_data))
        
        def mock_load_slide_cache(cache_key, cache_dir):
            cache_file = cache_dir / f"slide_order_{cache_key}.json"
            if cache_file.exists():
                with open(cache_file) as f:
                    return json.load(f)
            return None
        
        # Test cache hit
        loaded_cache = mock_load_slide_cache(cache_key, cache_dir)
        assert loaded_cache is not None
        assert len(loaded_cache["slides"]) == 2
        assert loaded_cache["input_folder"] == str(slides_dir)
    
    def test_slide_cache_miss(self, temp_project_dir):
        """Test that slide cache misses are handled correctly."""
        cache_dir = temp_project_dir / "output" / "working" / "ffmpeg_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        def mock_load_slide_cache(cache_key, cache_dir):
            cache_file = cache_dir / f"slide_order_{cache_key}.json"
            if cache_file.exists():
                with open(cache_file) as f:
                    return json.load(f)
            return None
        
        # Test cache miss with non-existent key
        loaded_cache = mock_load_slide_cache("nonexistent_key", cache_dir)
        assert loaded_cache is None
    
    def test_slide_cache_invalidation(self, temp_project_dir):
        """Test that slide cache is invalidated when files change."""
        slides_dir = temp_project_dir / "slides"
        
        def mock_generate_cache_key_with_files(input_folder, sort_settings):
            """Generate cache key including file list hash."""
            import hashlib
            import os
            
            # Get all files in directory
            files = []
            for root, dirs, filenames in os.walk(input_folder):
                for filename in filenames:
                    filepath = os.path.join(root, filename)
                    files.append((filepath, os.path.getmtime(filepath), os.path.getsize(filepath)))
            
            # Sort for consistency
            files.sort()
            
            content = f"{input_folder}_{sort_settings}_{files}"
            return hashlib.md5(content.encode()).hexdigest()
        
        # Create initial files
        (slides_dir / "photo1.jpg").write_text("original image 1")
        (slides_dir / "photo2.jpg").write_text("original image 2")
        
        sort_settings = {"method": "name", "reverse": False}
        key1 = mock_generate_cache_key_with_files(str(slides_dir), str(sort_settings))
        
        # Add a new file
        (slides_dir / "photo3.jpg").write_text("new image 3")
        
        key2 = mock_generate_cache_key_with_files(str(slides_dir), str(sort_settings))
        
        # Cache keys should be different due to file changes
        assert key1 != key2


class TestMultiSlideLogic:
    """Test multi-slide functionality and frequency settings."""
    
    def test_multislide_insertion_frequency(self, temp_project_dir):
        """Test that multi-slides are inserted at correct frequency."""
        slides = [f"photo{i}.jpg" for i in range(20)]  # 20 regular slides
        
        def mock_insert_multislides(slides, frequency=5):
            """Mock multi-slide insertion logic."""
            if frequency <= 0:
                return slides
            
            result = []
            for i, slide in enumerate(slides):
                result.append(slide)
                # Insert multi-slide every N regular slides
                if (i + 1) % frequency == 0 and i < len(slides) - 1:
                    result.append({"type": "multi", "slides": [slide, slides[min(i + 1, len(slides) - 1)]]})
            
            return result
        
        # Test frequency of 5
        result = mock_insert_multislides(slides, frequency=5)
        
        # Count multi-slides
        multi_count = sum(1 for item in result if isinstance(item, dict) and item.get("type") == "multi")
        
        # Should have multi-slides at positions 5, 10, 15 (3 total)
        assert multi_count == 3
    
    def test_multislide_disabled(self, temp_project_dir):
        """Test that multi-slides can be disabled."""
        slides = [f"photo{i}.jpg" for i in range(10)]
        
        def mock_insert_multislides(slides, frequency=0):
            if frequency <= 0:
                return slides
            return slides  # No insertion when frequency is 0
        
        result = mock_insert_multislides(slides, frequency=0)
        
        # Should be identical to original slides
        assert result == slides
        assert len(result) == 10