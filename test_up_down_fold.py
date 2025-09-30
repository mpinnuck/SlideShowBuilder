#!/usr/bin/env python3
"""
Test script for up_down_fold.py transition with the first 4 slides.
Tests both "up" and "down" directions with image slides.
"""

import os
import sys
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from slideshow.transitions.origami_fold_up_down import UpDownFold
from slideshow.config import DEFAULT_CONFIG
from PIL import Image
import moderngl

def get_test_slides(count=4):
    """Get the first 'count' image slides from the data directory."""
    slides_dir = project_root / "data" / "slides"
    
    # Get all image files (excluding videos and README)
    image_extensions = ['.jpg', '.jpeg', '.png']
    slides = []
    
    for file in sorted(slides_dir.iterdir()):
        if file.suffix.lower() in image_extensions:
            slides.append(str(file))
            if len(slides) >= count:
                break
    
    return slides

def load_and_resize_image(image_path, target_size=(1920, 1080)):
    """Load and resize an image to the target resolution."""
    with Image.open(image_path) as img:
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize maintaining aspect ratio
        img.thumbnail(target_size, Image.Resampling.LANCZOS)
        
        # Create a new image with the target size and paste the resized image
        result = Image.new('RGB', target_size, (0, 0, 0))
        
        # Center the image
        x = (target_size[0] - img.width) // 2
        y = (target_size[1] - img.height) // 2
        result.paste(img, (x, y))
        
        return result

def test_fold_transition(direction, from_img, to_img, output_path):
    """Test a single fold transition."""
    print(f"Testing {direction} fold transition...")
    
    # Create transition with higher quality settings for testing
    transition = UpDownFold(
        direction=direction,
        duration=2.0,  # 2 seconds
        resolution=(1920, 1080),
        fps=30
    )
    
    try:
        # Generate frames
        print(f"  Generating frames for {direction} fold...")
        start_time = time.time()
        
        frames = transition.generate_frames(from_img, to_img)
        
        end_time = time.time()
        print(f"  Generated {len(frames)} frames in {end_time - start_time:.2f} seconds")
        
        # Create video from frames
        print(f"  Creating video: {output_path}")
        transition.frames_to_video(frames, output_path)
        
        print(f"  ✅ Successfully created {direction} fold video: {output_path}")
        return True
        
    except Exception as e:
        print(f"  ❌ Error testing {direction} fold: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("🎬 Testing UpDownFold Transition")
    print("=" * 50)
    
    # Get test slides
    slides = get_test_slides(4)
    if len(slides) < 2:
        print("❌ Need at least 2 slides for testing")
        return
    
    print(f"Found {len(slides)} test slides:")
    for i, slide in enumerate(slides):
        print(f"  {i+1}. {Path(slide).name}")
    
    # Create output directory
    output_dir = project_root / "data" / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Load and prepare test images
    print("\n📸 Loading and preparing images...")
    test_images = []
    for slide_path in slides:
        try:
            img = load_and_resize_image(slide_path)
            test_images.append(img)
            print(f"  ✅ Loaded: {Path(slide_path).name}")
        except Exception as e:
            print(f"  ❌ Failed to load {Path(slide_path).name}: {e}")
    
    if len(test_images) < 2:
        print("❌ Need at least 2 valid images for testing")
        return
    
    # Test transitions
    print(f"\n🔄 Testing transitions with {len(test_images)} images...")
    
    success_count = 0
    total_tests = 0
    
    # Test each adjacent pair of images with both directions
    for i in range(len(test_images) - 1):
        from_img = test_images[i]
        to_img = test_images[i + 1]
        
        pair_name = f"slide{i+1}_to_slide{i+2}"
        
        print(f"\n📝 Testing transition pair: {pair_name}")
        
        # Test fold down
        output_path_down = output_dir / f"test_fold_down_{pair_name}.mp4"
        total_tests += 1
        if test_fold_transition("down", from_img, to_img, str(output_path_down)):
            success_count += 1
        
        # Test fold up  
        output_path_up = output_dir / f"test_fold_up_{pair_name}.mp4"
        total_tests += 1
        if test_fold_transition("up", from_img, to_img, str(output_path_up)):
            success_count += 1
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    print(f"Total tests: {total_tests}")
    print(f"Successful: {success_count}")
    print(f"Failed: {total_tests - success_count}")
    print(f"Success rate: {(success_count/total_tests)*100:.1f}%")
    
    if success_count == total_tests:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total_tests - success_count} test(s) failed")
    
    print(f"\n📁 Output files saved to: {output_dir}")

if __name__ == "__main__":
    main()