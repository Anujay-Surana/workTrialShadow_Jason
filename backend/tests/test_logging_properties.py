"""
Property-based tests for the unified logging system.

**Feature: retrieval-service-refactor, Property 10: Log Format Consistency**
"""

import os
import re
import sys
from io import StringIO
from unittest.mock import patch

import pytest
from hypothesis import given, settings, strategies as st

from retrieval_service.infrastructure.logging import (
    log_debug,
    log_info,
    log_warning,
    log_error,
    _format_message
)


# Property 10: Log Format Consistency
# For any log output, the log should follow a consistent format with appropriate prefixes.
# Validates: Requirements 10.4

@given(
    message=st.text(min_size=1, max_size=200),
    level=st.sampled_from(['DEBUG', 'INFO', 'WARNING', 'ERROR'])
)
@settings(max_examples=100)
def test_log_format_consistency(message, level):
    """
    **Feature: retrieval-service-refactor, Property 10: Log Format Consistency**
    **Validates: Requirements 10.4**
    
    Property: For any log message and level, the formatted output should follow
    a consistent format: [YYYY-MM-DD HH:MM:SS] [LEVEL] message
    """
    formatted = _format_message(level, message)
    
    # Check format matches: [timestamp] [level] message
    # Pattern: [YYYY-MM-DD HH:MM:SS] [LEVEL] message
    pattern = r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[' + re.escape(level) + r'\] '
    
    assert re.match(pattern, formatted), \
        f"Log format does not match expected pattern. Got: {formatted}"
    
    # Verify the message is included in the formatted output
    assert message in formatted, \
        f"Original message not found in formatted output. Message: {message}, Formatted: {formatted}"


@given(message=st.text(min_size=1, max_size=200))
@settings(max_examples=100)
def test_debug_log_respects_verbose_output(message):
    """
    Property: Debug logs should only output when VERBOSE_OUTPUT=true
    and should follow consistent format.
    """
    # Test with VERBOSE_OUTPUT=false
    with patch.dict(os.environ, {'VERBOSE_OUTPUT': 'false'}):
        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            log_debug(message)
        
        output = captured_output.getvalue()
        assert output == '', \
            f"Debug log should not output when VERBOSE_OUTPUT=false, but got: {output}"
    
    # Test with VERBOSE_OUTPUT=true
    with patch.dict(os.environ, {'VERBOSE_OUTPUT': 'true'}):
        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            log_debug(message)
        
        output = captured_output.getvalue()
        assert output != '', \
            "Debug log should output when VERBOSE_OUTPUT=true"
        
        # Verify format consistency
        pattern = r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[DEBUG\] '
        assert re.match(pattern, output), \
            f"Debug log format does not match expected pattern. Got: {output}"


@given(message=st.text(min_size=1, max_size=200))
@settings(max_examples=100)
def test_info_log_respects_verbose_output(message):
    """
    Property: Info logs should only output when VERBOSE_OUTPUT=true
    and should follow consistent format.
    """
    # Test with VERBOSE_OUTPUT=false
    with patch.dict(os.environ, {'VERBOSE_OUTPUT': 'false'}):
        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            log_info(message)
        
        output = captured_output.getvalue()
        assert output == '', \
            f"Info log should not output when VERBOSE_OUTPUT=false, but got: {output}"
    
    # Test with VERBOSE_OUTPUT=true
    with patch.dict(os.environ, {'VERBOSE_OUTPUT': 'true'}):
        captured_output = StringIO()
        with patch('sys.stdout', captured_output):
            log_info(message)
        
        output = captured_output.getvalue()
        assert output != '', \
            "Info log should output when VERBOSE_OUTPUT=true"
        
        # Verify format consistency
        pattern = r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[INFO\] '
        assert re.match(pattern, output), \
            f"Info log format does not match expected pattern. Got: {output}"


@given(
    message=st.text(min_size=1, max_size=200),
    verbose_setting=st.sampled_from(['true', 'false', 'TRUE', 'FALSE', 'True', 'False'])
)
@settings(max_examples=100)
def test_warning_log_always_outputs(message, verbose_setting):
    """
    Property: Warning logs should always output regardless of VERBOSE_OUTPUT setting
    and should follow consistent format.
    """
    with patch.dict(os.environ, {'VERBOSE_OUTPUT': verbose_setting}):
        captured_output = StringIO()
        with patch('sys.stderr', captured_output):
            log_warning(message)
        
        output = captured_output.getvalue()
        assert output != '', \
            f"Warning log should always output regardless of VERBOSE_OUTPUT={verbose_setting}"
        
        # Verify format consistency
        pattern = r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[WARNING\] '
        assert re.match(pattern, output), \
            f"Warning log format does not match expected pattern. Got: {output}"


@given(
    message=st.text(min_size=1, max_size=200),
    verbose_setting=st.sampled_from(['true', 'false', 'TRUE', 'FALSE', 'True', 'False'])
)
@settings(max_examples=100)
def test_error_log_always_outputs(message, verbose_setting):
    """
    Property: Error logs should always output regardless of VERBOSE_OUTPUT setting
    and should follow consistent format.
    """
    with patch.dict(os.environ, {'VERBOSE_OUTPUT': verbose_setting}):
        captured_output = StringIO()
        with patch('sys.stderr', captured_output):
            log_error(message)
        
        output = captured_output.getvalue()
        assert output != '', \
            f"Error log should always output regardless of VERBOSE_OUTPUT={verbose_setting}"
        
        # Verify format consistency
        pattern = r'^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] \[ERROR\] '
        assert re.match(pattern, output), \
            f"Error log format does not match expected pattern. Got: {output}"


@given(
    message=st.text(min_size=1, max_size=200),
    level=st.sampled_from(['DEBUG', 'INFO', 'WARNING', 'ERROR'])
)
@settings(max_examples=100)
def test_log_level_prefix_consistency(message, level):
    """
    Property: All log levels should use consistent prefix format [LEVEL]
    """
    formatted = _format_message(level, message)
    
    # Verify the level appears in square brackets
    assert f'[{level}]' in formatted, \
        f"Level prefix [{level}] not found in formatted output: {formatted}"
    
    # Verify timestamp appears in square brackets before level
    timestamp_pattern = r'\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]'
    assert re.search(timestamp_pattern, formatted), \
        f"Timestamp not found in expected format in: {formatted}"
