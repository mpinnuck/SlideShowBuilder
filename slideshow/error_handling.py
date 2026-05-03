# slideshow/error_handling.py
"""
Centralized error handling utilities for consistent error management across the application.
"""
import logging
from typing import Optional, Any, Callable
from pathlib import Path


class ErrorHandler:
    """Centralized error handling with consistent logging and fallback strategies."""
    
    @staticmethod
    def log_warning(logger_func: Callable, operation: str, error: Exception, context: str = "") -> None:
        """Log a warning with consistent formatting."""
        context_str = f" ({context})" if context else ""
        logger_func(f"[WARNING] {operation} failed{context_str}: {error}")
    
    @staticmethod
    def log_error(logger_func: Callable, operation: str, error: Exception, context: str = "") -> None:
        """Log an error with consistent formatting."""
        context_str = f" ({context})" if context else ""
        logger_func(f"[ERROR] {operation} failed{context_str}: {error}")
    
    @staticmethod
    def handle_file_operation(operation: str, file_path: Path, logger_func: Callable, 
                            fallback_value: Any = None) -> Any:
        """Standard handler for file operations with logging."""
        try:
            return operation(file_path)
        except OSError as e:
            ErrorHandler.log_warning(logger_func, f"File operation on {file_path}", e)
            return fallback_value
        except Exception as e:
            ErrorHandler.log_error(logger_func, f"Unexpected error with file {file_path}", e)
            return fallback_value
    
    @staticmethod
    def safe_metadata_extraction(extractor_func: Callable, file_path: Path, 
                               logger_func: Callable, fallback_value: Any = None) -> Any:
        """Standard handler for metadata extraction operations."""
        try:
            return extractor_func(file_path)
        except (OSError, ValueError) as e:
            # Expected errors - log as warning
            ErrorHandler.log_warning(logger_func, f"Metadata extraction from {file_path.name}", e)
            return fallback_value
        except Exception as e:
            # Unexpected errors - log as error
            ErrorHandler.log_error(logger_func, f"Unexpected error extracting metadata from {file_path.name}", e)
            return fallback_value
    
    @staticmethod  
    def safe_subprocess_call(command_name: str, cmd_args: list, logger_func: Callable,
                           timeout: int = 30, fallback_value: Any = None) -> Any:
        """Standard handler for subprocess calls with proper error handling."""
        import subprocess
        try:
            result = subprocess.run(cmd_args, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                ErrorHandler.log_warning(logger_func, f"{command_name} command", 
                                       Exception(f"Exit code {result.returncode}: {result.stderr}"))
                return fallback_value
            return result
        except subprocess.TimeoutExpired as e:
            ErrorHandler.log_warning(logger_func, f"{command_name} command timeout", e)
            return fallback_value
        except (OSError, FileNotFoundError) as e:
            ErrorHandler.log_warning(logger_func, f"{command_name} command execution", e)
            return fallback_value
        except Exception as e:
            ErrorHandler.log_error(logger_func, f"Unexpected error in {command_name} command", e)
            return fallback_value


# Convenience functions for common error patterns
def safe_file_stat(file_path: Path, logger_func: Callable) -> Optional[float]:
    """Safely get file timestamp with proper error handling."""
    try:
        stat = file_path.stat()
        return getattr(stat, 'st_birthtime', stat.st_mtime)
    except OSError as e:
        ErrorHandler.log_warning(logger_func, f"Getting file stats for {file_path.name}", e)
        return 0.0
    except Exception as e:
        ErrorHandler.log_error(logger_func, f"Unexpected error getting stats for {file_path.name}", e)
        return 0.0


def safe_json_parse(json_string: str, logger_func: Callable, context: str = "") -> Optional[dict]:
    """Safely parse JSON with proper error handling."""
    import json
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        ErrorHandler.log_warning(logger_func, f"JSON parsing{' ' + context if context else ''}", e)
        return None
    except Exception as e:
        ErrorHandler.log_error(logger_func, f"Unexpected error parsing JSON{' ' + context if context else ''}", e)
        return None