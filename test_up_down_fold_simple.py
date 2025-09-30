#!/usr/bin/env python3
"""
Simple test script for up_down_fold.py transition.
Tests with the first 4 slides using a quick demo.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_basic_functionality():
    """Test basic import and instantiation."""
    try:
        from slideshow.transitions.origami_fold_up_down import UpDownFold
        
        # Test both directions
        fold_down = UpDownFold(direction="down")
        fold_up = UpDownFold(direction="up")
        
        print("✅ Successfully imported and created UpDownFold instances")
        print(f"  - Fold Down: {fold_down.__class__.__name__} (direction: {fold_down.direction})")
        print(f"  - Fold Up: {fold_up.__class__.__name__} (direction: {fold_up.direction})")
        
        # Test requirements
        requirements = fold_down.get_requirements()
        print(f"  - Requirements: {requirements}")
        
        return True
        
    except Exception as e:
        print(f"❌ Import/instantiation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_with_sample_images():
    """Test with actual image files."""
    from slideshow.transitions.origami_fold_up_down import UpDownFold
    from PIL import Image
    
    # Get first 4 image slides
    slides_dir = project_root / "data" / "slides"
    image_files = []
    
    for file in sorted(slides_dir.iterdir()):
        if file.suffix.lower() in ['.jpg', '.jpeg', '.png']:
            image_files.append(file)
            if len(image_files) >= 4:
                break
    
    if len(image_files) < 2:
        print("❌ Need at least 2 image files for testing")
        return False
    
    print(f"\n📸 Found {len(image_files)} test images:")
    for i, img_file in enumerate(image_files):
        print(f"  {i+1}. {img_file.name}")
    
    try:
        # Load first two images for testing
        print(f"\n🔄 Loading images...")
        img1 = Image.open(image_files[0]).convert('RGB')
        img2 = Image.open(image_files[1]).convert('RGB')
        
        # Resize to reasonable size for testing
        test_size = (640, 360)  # Smaller for faster testing
        img1 = img1.resize(test_size)
        img2 = img2.resize(test_size)
        
        print(f"  - Image 1: {img1.size} {img1.mode}")
        print(f"  - Image 2: {img2.size} {img2.mode}")
        
        # Test fold down transition
        print(f"\n🔽 Testing fold DOWN transition...")
        fold_down = UpDownFold(direction="down", duration=1.0, fps=15)  # Fast test
        
        try:
            frames_down = fold_down.generate_frames(img1, img2)
            print(f"  ✅ Generated {len(frames_down)} frames for fold down")
        except Exception as e:
            print(f"  ❌ Fold down failed: {e}")
            return False
        
        # Test fold up transition
        print(f"\n🔼 Testing fold UP transition...")
        fold_up = UpDownFold(direction="up", duration=1.0, fps=15)  # Fast test
        
        try:
            frames_up = fold_up.generate_frames(img2, img1)  # Reverse order
            print(f"  ✅ Generated {len(frames_up)} frames for fold up")
        except Exception as e:
            print(f"  ❌ Fold up failed: {e}")
            return False
        
        print(f"\n🎉 All basic tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Image testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🧪 UpDownFold Transition - Quick Test")
    print("=" * 40)
    
    # Test 1: Basic functionality
    print("Test 1: Basic Import & Instantiation")
    if not test_basic_functionality():
        return
    
    # Test 2: With sample images
    print("\nTest 2: Sample Image Processing")
    if not test_with_sample_images():
        return
    
    print("\n" + "=" * 40)
    print("🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
    print("The up_down_fold.py transition is working correctly.")

if __name__ == "__main__":
    main()