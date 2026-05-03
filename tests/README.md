# SlideShow Builder Test Suite

This directory contains comprehensive unit tests for the SlideShow Builder application.

## Quick Start

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
python run_tests.py all

# Run specific test categories
python run_tests.py security
python run_tests.py config
python run_tests.py cache
```

## Test Categories

### Security Tests (`-m security`)
- **Path Traversal Protection**: Tests that config.py prevents directory traversal attacks
- **Input Validation**: Tests that FFmpeg parameters are properly validated
- **Path Normalization**: Tests that all user-supplied paths are normalized with `.resolve()`

### Unit Tests (`-m unit`)
- **Config System**: Configuration loading, saving, validation, singleton behavior
- **Cache System**: FFmpeg cache functionality, metadata handling, concurrent access
- **Slide System**: File discovery, sorting algorithms, slide cache

### Integration Tests (`-m integration`)
- **End-to-End Workflows**: Full slideshow generation pipeline
- **Cross-Component**: Tests involving multiple modules working together

## Test Files

| File | Description | Key Areas |
|------|-------------|-----------|
| `test_config.py` | Configuration system tests | Input validation, path security, persistence |
| `test_cache.py` | Cache system tests | FFmpeg cache, metadata, concurrency |
| `test_slides.py` | Slide system tests | Discovery, sorting, slide cache |
| `conftest.py` | Test fixtures and utilities | Common test setup, helpers |

## Running Tests

### Using the test runner script:

```bash
# All tests with basic output
python run_tests.py all

# Only security-related tests
python run_tests.py security

# Tests with coverage report
python run_tests.py coverage

# Verbose output for debugging
python run_tests.py verbose
```

### Using pytest directly:

```bash
# Basic test run
pytest tests/

# With coverage
pytest tests/ --cov=slideshow --cov-report=html

# Specific test file
pytest tests/test_config.py -v

# Specific test method
pytest tests/test_config.py::TestPathTraversalSecurity::test_get_project_config_path_blocks_traversal -v

# Run with specific markers
pytest tests/ -m "security or unit" -v
```

## Test Markers

Tests are categorized with pytest markers:

- `@pytest.mark.unit` - Unit tests for individual components
- `@pytest.mark.security` - Security-related tests 
- `@pytest.mark.integration` - Integration tests requiring multiple components
- `@pytest.mark.slow` - Tests that take more than 1 second
- `@pytest.mark.gui` - Tests requiring GUI components (may be skipped in CI)

## Coverage Goals

| Component | Target Coverage | Current Status |
|-----------|----------------|----------------|
| `slideshow/config.py` | 90%+ | ✅ High priority areas covered |
| `slideshow/transitions/ffmpeg_cache.py` | 85%+ | ✅ Core functionality covered |
| `slideshow/slideshowmodel.py` | 80%+ | ⚠️ Partial coverage |
| Security-sensitive code | 100% | ✅ Path validation covered |

## Test Fixtures

Key fixtures available in `conftest.py`:

- `temp_test_dir` - Session-scoped temporary directory
- `temp_project_dir` - Function-scoped project directory with sample files
- `clean_config` - Ensures Config singleton is clean for each test
- `sample_config` - Valid configuration dictionary for testing
- `invalid_configs` - Various invalid configurations for validation testing

## Development Workflow

When adding new features:

1. **Write tests first** (TDD approach recommended)
2. **Add appropriate markers** (`@pytest.mark.unit`, etc.)
3. **Test both happy path and edge cases**
4. **Include security tests** for any user input handling
5. **Run tests frequently** during development

```bash
# Quick feedback loop during development
python run_tests.py config  # Test just the area you're working on
```

## CI/CD Integration

For continuous integration, use:

```bash
# Fast feedback for PR checks
pytest tests/ -m "not slow" --tb=short

# Full test suite for main branch
pytest tests/ --cov=slideshow --cov-report=xml --junitxml=test-results.xml
```

## Troubleshooting

### Common Issues

**ImportError: No module named 'slideshow'**
- The `conftest.py` file adds the slideshow module to sys.path
- Ensure you're running tests from the project root directory

**Tests fail with "Config singleton already exists"**  
- Use the `clean_config` fixture to ensure clean state
- Check that your test is properly clearing the singleton

**Path-related test failures on Windows**
- Tests use `pathlib.Path` for cross-platform compatibility
- Temporary directories are automatically cleaned up

### Debugging Failed Tests

```bash
# Run with maximum verbosity
python run_tests.py verbose

# Run specific failing test with detailed output  
pytest tests/test_config.py::TestPathTraversalSecurity::test_specific_method -vvv --tb=long

# Drop into debugger on failure
pytest tests/test_config.py --pdb -x
```