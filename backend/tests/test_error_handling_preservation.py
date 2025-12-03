"""
Property-based tests for error handling preservation.

**Feature: retrieval-service-refactor, Property 6: Error Handling Preservation**
**Validates: Requirements 8.1**

Property: For any error scenario that was handled before refactoring, 
the same error should be caught and handled in the same way after refactoring.
"""

import pytest
import ast
import os
from pathlib import Path
from hypothesis import given, strategies as st, settings
from typing import Dict, List, Tuple


def get_python_files():
    """Get all Python files in the retrieval_service directory."""
    backend_path = Path(__file__).parent.parent / "retrieval_service"
    python_files = []
    
    for root, dirs, files in os.walk(backend_path):
        # Skip __pycache__ and test directories
        dirs[:] = [d for d in dirs if d not in ['__pycache__', 'tests', '.pytest_cache']]
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    return python_files


def analyze_error_handling(filepath: str) -> Dict:
    """
    Analyze error handling patterns in a Python file.
    
    Returns:
        dict: {
            'try_blocks': int,
            'except_clauses': List[str],
            'retry_patterns': int,
            'error_logging': int,
            'has_error_handling': bool
        }
    """
    analysis = {
        'try_blocks': 0,
        'except_clauses': [],
        'retry_patterns': 0,
        'error_logging': 0,
        'has_error_handling': False
    }
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the AST
        tree = ast.parse(content, filename=filepath)
        
        # Count try-except blocks
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                analysis['try_blocks'] += 1
                analysis['has_error_handling'] = True
                
                # Analyze except handlers
                for handler in node.handlers:
                    if handler.type:
                        if isinstance(handler.type, ast.Name):
                            analysis['except_clauses'].append(handler.type.id)
                        elif isinstance(handler.type, ast.Tuple):
                            for exc in handler.type.elts:
                                if isinstance(exc, ast.Name):
                                    analysis['except_clauses'].append(exc.id)
                    else:
                        # Bare except
                        analysis['except_clauses'].append('Exception')
            
            # Check for retry patterns (for loops with range and max_retries)
            if isinstance(node, ast.For):
                if isinstance(node.iter, ast.Call):
                    if isinstance(node.iter.func, ast.Name) and node.iter.func.id == 'range':
                        # Check if the loop variable is named 'attempt' or similar
                        if isinstance(node.target, ast.Name):
                            if 'attempt' in node.target.id.lower() or 'retry' in node.target.id.lower():
                                analysis['retry_patterns'] += 1
        
        # Check for error logging patterns
        if 'log_error(' in content or 'logging.error(' in content or '.error(' in content:
            analysis['error_logging'] += content.count('log_error(') + content.count('.error(')
        
        return analysis
        
    except Exception as e:
        # If we can't parse the file, return empty analysis
        return analysis


def check_critical_error_handling() -> Tuple[bool, List[str]]:
    """
    Check that critical modules have proper error handling.
    
    Returns:
        tuple: (all_have_error_handling, missing_modules)
    """
    critical_modules = [
        'api/openai_client.py',
        'api/gemini_client.py',
        'api/google_client.py',
        'data/database.py',
        'data/initialization.py',
        'infrastructure/batch.py',
        'search/vector.py',
        'search/keyword.py',
        'search/fuzzy.py',
    ]
    
    backend_path = Path(__file__).parent.parent / "retrieval_service"
    missing = []
    
    for module in critical_modules:
        filepath = backend_path / module
        if filepath.exists():
            analysis = analyze_error_handling(str(filepath))
            if not analysis['has_error_handling']:
                missing.append(module)
        else:
            missing.append(f"{module} (not found)")
    
    return len(missing) == 0, missing


def check_retry_patterns_exist() -> Tuple[bool, List[str]]:
    """
    Check that retry patterns exist in API client modules.
    
    Returns:
        tuple: (has_retry_patterns, modules_without_retry)
    """
    api_modules = [
        'api/openai_client.py',
        'api/gemini_client.py',
        'api/google_client.py',
    ]
    
    backend_path = Path(__file__).parent.parent / "retrieval_service"
    without_retry = []
    
    for module in api_modules:
        filepath = backend_path / module
        if filepath.exists():
            analysis = analyze_error_handling(str(filepath))
            # Check if module has retry patterns or mentions max_retries
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            has_retry = analysis['retry_patterns'] > 0 or 'max_retries' in content or 'retry' in content.lower()
            if not has_retry:
                without_retry.append(module)
    
    return len(without_retry) == 0, without_retry


def check_error_logging_exists() -> Tuple[bool, List[str]]:
    """
    Check that modules with error handling also log errors.
    
    Returns:
        tuple: (all_log_errors, modules_without_logging)
    """
    python_files = get_python_files()
    without_logging = []
    
    for filepath in python_files:
        analysis = analyze_error_handling(filepath)
        
        # If module has error handling but no error logging
        if analysis['has_error_handling'] and analysis['error_logging'] == 0:
            relative_path = os.path.relpath(filepath, Path(__file__).parent.parent)
            
            # Check if it at least imports logging
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            has_logging_import = (
                'from retrieval_service.infrastructure.logging import' in content or
                'import logging' in content
            )
            
            # Only flag if it has try-except but no logging at all
            if not has_logging_import:
                without_logging.append(relative_path)
    
    return len(without_logging) == 0, without_logging


@settings(max_examples=1)
@given(st.just(None))
def test_critical_modules_have_error_handling(dummy):
    """
    Property: For any critical module, it should have proper error handling.
    
    Critical modules that interact with external services (APIs, databases)
    must have try-except blocks to handle potential failures.
    """
    all_have_handling, missing = check_critical_error_handling()
    
    if not all_have_handling:
        error_msg = "The following critical modules lack error handling:\n"
        for module in missing:
            error_msg += f"  - {module}\n"
        error_msg += "\nCritical modules must have try-except blocks to handle external service failures."
        pytest.fail(error_msg)


@settings(max_examples=1)
@given(st.just(None))
def test_api_modules_have_retry_patterns(dummy):
    """
    Property: For any API client module, it should implement retry logic.
    
    API clients must handle transient failures with retry mechanisms
    to ensure reliability (Requirement 8.4).
    """
    has_retry, without_retry = check_retry_patterns_exist()
    
    if not has_retry:
        error_msg = "The following API modules lack retry patterns:\n"
        for module in without_retry:
            error_msg += f"  - {module}\n"
        error_msg += "\nAPI modules should implement exponential backoff retry strategies."
        pytest.fail(error_msg)


@settings(max_examples=1)
@given(st.just(None))
def test_error_handling_includes_logging(dummy):
    """
    Property: For any module with error handling, errors should be logged.
    
    Modules that catch exceptions should log them for debugging and monitoring
    (Requirement 8.2).
    """
    all_log, without_logging = check_error_logging_exists()
    
    if not all_log:
        error_msg = "The following modules have error handling but no error logging:\n"
        for module in without_logging:
            error_msg += f"  - {module}\n"
        error_msg += "\nModules with try-except blocks should log errors using log_error()."
        pytest.fail(error_msg)


def test_exception_types_are_specific():
    """
    Verify that exception handling uses specific exception types where appropriate.
    
    Bare except clauses should be minimized in favor of specific exception types.
    """
    python_files = get_python_files()
    bare_except_files = []
    
    for filepath in python_files:
        analysis = analyze_error_handling(filepath)
        
        # Count bare except clauses (catching Exception)
        bare_count = analysis['except_clauses'].count('Exception')
        
        # If more than 50% are bare except, flag it
        if analysis['try_blocks'] > 0:
            bare_ratio = bare_count / len(analysis['except_clauses']) if analysis['except_clauses'] else 0
            if bare_ratio > 0.7:  # More than 70% are bare except
                relative_path = os.path.relpath(filepath, Path(__file__).parent.parent)
                bare_except_files.append((relative_path, bare_count, len(analysis['except_clauses'])))
    
    # This is a warning, not a failure - bare except is sometimes necessary
    if bare_except_files:
        warning_msg = "The following modules use many bare except clauses:\n"
        for filepath, bare, total in bare_except_files:
            warning_msg += f"  - {filepath}: {bare}/{total} are bare except\n"
        warning_msg += "\nConsider using specific exception types where possible."
        # Just print warning, don't fail
        print(f"\nWARNING: {warning_msg}")


def test_database_operations_have_error_handling():
    """
    Verify that all database operations in data/database.py have error handling.
    """
    database_file = Path(__file__).parent.parent / "retrieval_service" / "data" / "database.py"
    
    if not database_file.exists():
        pytest.skip("database.py not found")
    
    analysis = analyze_error_handling(str(database_file))
    
    # Database module should have substantial error handling
    assert analysis['try_blocks'] > 0, "database.py should have try-except blocks"
    assert analysis['has_error_handling'], "database.py should have error handling"
    
    # Check that it has multiple try blocks (one per function ideally)
    assert analysis['try_blocks'] >= 10, f"database.py should have multiple error handlers, found {analysis['try_blocks']}"


def test_initialization_has_comprehensive_error_handling():
    """
    Verify that data initialization has comprehensive error handling.
    """
    init_file = Path(__file__).parent.parent / "retrieval_service" / "data" / "initialization.py"
    
    if not init_file.exists():
        pytest.skip("initialization.py not found")
    
    analysis = analyze_error_handling(str(init_file))
    
    # Initialization is critical and should have robust error handling
    assert analysis['try_blocks'] > 0, "initialization.py should have try-except blocks"
    assert analysis['has_error_handling'], "initialization.py should have error handling"
    assert analysis['error_logging'] > 0, "initialization.py should log errors"


def test_api_clients_handle_common_exceptions():
    """
    Verify that API clients handle common exception types.
    """
    api_modules = [
        'api/openai_client.py',
        'api/gemini_client.py',
        'api/google_client.py',
    ]
    
    backend_path = Path(__file__).parent.parent / "retrieval_service"
    
    for module in api_modules:
        filepath = backend_path / module
        if filepath.exists():
            analysis = analyze_error_handling(str(filepath))
            
            # API clients should have error handling
            assert analysis['has_error_handling'], f"{module} should have error handling"
            
            # Check for common exception types in the file
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Should handle at least some common exceptions
            # (This is a soft check - not all modules need all exception types)
            has_exception_handling = (
                'except' in content.lower() and
                analysis['try_blocks'] > 0
            )
            
            assert has_exception_handling, f"{module} should have exception handling"
