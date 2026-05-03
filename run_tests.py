#!/usr/bin/env python3
"""
Test runner script for SlideShow Builder.

This script provides convenient commands for running tests with different options.
"""

import sys
import subprocess
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle output."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=False)
        print(f"\n✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"\n❌ pytest not found. Install with: pip install -r requirements.txt")
        return False


def main():
    """Main test runner function."""
    if len(sys.argv) < 2:
        print("""
SlideShow Builder Test Runner

Usage:
    python run_tests.py <command> [options]

Commands:
    all         - Run all tests
    unit        - Run only unit tests (fast)  
    security    - Run only security tests
    config      - Run only config tests
    cache       - Run only cache tests
    coverage    - Run tests with coverage report
    watch       - Run tests in watch mode (requires pytest-watch)
    verbose     - Run tests with verbose output
    
Examples:
    python run_tests.py all
    python run_tests.py unit
    python run_tests.py security
    python run_tests.py coverage
    python run_tests.py verbose
        """)
        return 1

    command = sys.argv[1].lower()
    extra_args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    # Base pytest command
    base_cmd = ["python", "-m", "pytest"]
    
    # Command routing
    if command == "all":
        cmd = base_cmd + ["tests/", "-v"] + extra_args
        success = run_command(cmd, "All tests")
        
    elif command == "unit":
        cmd = base_cmd + ["tests/", "-m", "unit", "-v"] + extra_args
        success = run_command(cmd, "Unit tests")
        
    elif command == "security":
        cmd = base_cmd + ["tests/", "-m", "security", "-v"] + extra_args
        success = run_command(cmd, "Security tests")
        
    elif command == "config":
        cmd = base_cmd + ["tests/test_config.py", "-v"] + extra_args
        success = run_command(cmd, "Config tests")
        
    elif command == "cache":
        cmd = base_cmd + ["tests/test_cache.py", "-v"] + extra_args
        success = run_command(cmd, "Cache tests")
        
    elif command == "coverage":
        cmd = base_cmd + ["tests/", "--cov=slideshow", "--cov-report=html", "--cov-report=term-missing", "-v"] + extra_args
        success = run_command(cmd, "Tests with coverage")
        if success:
            print(f"\n📊 Coverage report generated in htmlcov/index.html")
            
    elif command == "verbose":
        cmd = base_cmd + ["tests/", "-vvv", "--tb=long"] + extra_args
        success = run_command(cmd, "Verbose tests")
        
    elif command == "watch":
        try:
            cmd = ["ptw", "tests/", "--", "-v"] + extra_args
            success = run_command(cmd, "Watch mode tests")
        except FileNotFoundError:
            print("❌ pytest-watch not installed. Install with: pip install pytest-watch")
            return 1
            
    else:
        print(f"❌ Unknown command: {command}")
        return 1
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())