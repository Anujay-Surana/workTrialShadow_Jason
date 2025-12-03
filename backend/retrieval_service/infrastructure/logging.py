"""
Unified logging system for the Memory Retrieval Service.

This module provides a consistent logging interface that respects the
VERBOSE_OUTPUT environment variable for controlling debug and info logs,
while always outputting warnings and errors.
"""

import os
import sys
from datetime import datetime
from typing import Any


def _get_verbose_output() -> bool:
    """
    Check if verbose output is enabled via environment variable.
    
    Returns:
        True if VERBOSE_OUTPUT is set to 'true' (case-insensitive), False otherwise
    """
    return os.getenv('VERBOSE_OUTPUT', 'false').lower() == 'true'


def _format_message(level: str, message: str) -> str:
    """
    Format a log message with timestamp and level prefix.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        message: The message to log
        
    Returns:
        Formatted log message string
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return f"[{timestamp}] [{level}] {message}"


def log_debug(message: str, *args: Any) -> None:
    """
    Log a debug message. Only outputs if VERBOSE_OUTPUT=true.
    
    Args:
        message: Debug message to log
        *args: Additional arguments to format into the message
    """
    if _get_verbose_output():
        formatted_msg = message if not args else message % args
        print(_format_message("DEBUG", formatted_msg), file=sys.stdout)


def log_info(message: str, *args: Any) -> None:
    """
    Log an informational message. Only outputs if VERBOSE_OUTPUT=true.
    
    Args:
        message: Info message to log
        *args: Additional arguments to format into the message
    """
    if _get_verbose_output():
        formatted_msg = message if not args else message % args
        print(_format_message("INFO", formatted_msg), file=sys.stdout)


def log_warning(message: str, *args: Any) -> None:
    """
    Log a warning message. Always outputs regardless of VERBOSE_OUTPUT.
    
    Args:
        message: Warning message to log
        *args: Additional arguments to format into the message
    """
    formatted_msg = message if not args else message % args
    print(_format_message("WARNING", formatted_msg), file=sys.stderr)


def log_error(message: str, *args: Any) -> None:
    """
    Log an error message. Always outputs regardless of VERBOSE_OUTPUT.
    
    Args:
        message: Error message to log
        *args: Additional arguments to format into the message
    """
    formatted_msg = message if not args else message % args
    print(_format_message("ERROR", formatted_msg), file=sys.stderr)
