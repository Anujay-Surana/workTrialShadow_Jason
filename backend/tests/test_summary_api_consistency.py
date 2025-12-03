"""
Property-based tests for summary API consistency.

**Feature: retrieval-service-refactor, Property 8: Summary API Consistency**
**Validates: Requirements 9.2**

Property: For any text summarization operation, the operation should use OpenAI API.
"""

import pytest
import ast
import os
from pathlib import Path
from hypothesis import given, strategies as st, settings


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


def check_file_for_gemini_summarization(filepath):
    """
    Check if a file contains Gemini summarization calls.
    
    Returns:
        tuple: (has_gemini_summary, violations)
    """
    violations = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check for Gemini summarization patterns
        if 'genai.generate_content' in content or 'gemini' in content.lower():
            # Parse the AST to find actual summarization calls
            tree = ast.parse(content, filename=filepath)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = None
                    
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    
                    # Check for Gemini content generation
                    if func_name in ['generate_content', 'generate_text']:
                        # Check if this is a summarization context
                        violations.append({
                            'type': 'call',
                            'line': node.lineno,
                            'detail': f"Potential Gemini summarization call: {func_name}"
                        })
        
        return len(violations) > 0, violations
        
    except Exception as e:
        # If we can't parse the file, skip it
        return False, []


def check_file_uses_openai_for_summarization(filepath):
    """
    Check if a file that performs summarization uses OpenAI API.
    
    Returns:
        tuple: (performs_summarization, uses_openai)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Exclude files that just store/retrieve summaries (database operations)
        if 'supabase' in filepath or 'database' in filepath or '__init__' in filepath:
            # These files handle summary storage/exports, not generation
            return False, True
        
        # Check if file actually generates summaries (not just calls or stores them)
        # Look for actual LLM calls for summarization
        generates_summary = any([
            'client.chat.completions.create' in content and 'summarize' in content.lower(),
            'async_client.chat.completions.create' in content and 'summarize' in content.lower(),
            'genai.generate_content' in content and 'summarize' in content.lower(),
        ])
        
        if not generates_summary:
            return False, True  # Doesn't generate summaries, so it's fine
        
        # Check if it uses OpenAI
        uses_openai = any([
            'from openai import' in content,
            'OpenAI(' in content,
            'client.chat.completions.create' in content,
            'async_client.chat.completions.create' in content,
        ])
        
        return generates_summary, uses_openai
        
    except Exception:
        return False, True


@settings(max_examples=1)
@given(st.just(None))
def test_no_gemini_summarization_calls(dummy):
    """
    Property: For any Python file in the system, it should not use Gemini for summarization.
    
    This test scans all Python files to ensure no Gemini summarization operations exist.
    """
    python_files = get_python_files()
    
    violations_by_file = {}
    
    for filepath in python_files:
        has_violation, violations = check_file_for_gemini_summarization(filepath)
        
        if has_violation:
            relative_path = os.path.relpath(filepath, Path(__file__).parent.parent)
            violations_by_file[relative_path] = violations
    
    # Assert no violations found
    if violations_by_file:
        error_msg = "Found Gemini summarization operations in the following files:\n"
        for filepath, violations in violations_by_file.items():
            error_msg += f"\n{filepath}:\n"
            for v in violations:
                error_msg += f"  Line {v['line']}: {v['detail']}\n"
        
        pytest.fail(error_msg)


@settings(max_examples=1)
@given(st.just(None))
def test_summarization_operations_use_openai(dummy):
    """
    Property: For any file that performs summarization operations, it should use OpenAI API.
    
    This test ensures all summarization operations route through OpenAI client.
    """
    python_files = get_python_files()
    
    violations = []
    
    for filepath in python_files:
        performs_summarization, uses_openai = check_file_uses_openai_for_summarization(filepath)
        
        if performs_summarization and not uses_openai:
            relative_path = os.path.relpath(filepath, Path(__file__).parent.parent)
            violations.append(relative_path)
    
    # Assert all summarization operations use OpenAI
    if violations:
        error_msg = "Found summarization operations not using OpenAI API in:\n"
        for filepath in violations:
            error_msg += f"  - {filepath}\n"
        
        pytest.fail(error_msg)


def test_document_utils_uses_openai():
    """
    Verify that document processing module uses OpenAI for summarization.
    """
    try:
        from retrieval_service.processing import summarize, summarize_doc
        
        # Check that the functions exist
        assert callable(summarize), "summarize should be a callable function"
        assert callable(summarize_doc), "summarize_doc should be a callable function"
        
        # Verify the module imports OpenAI
        import retrieval_service.processing.documents as doc_utils
        import inspect
        
        source = inspect.getsource(doc_utils)
        assert 'from openai import' in source or 'import openai' in source, \
            "processing.documents should import OpenAI"
        
    except ImportError as e:
        pytest.fail(f"Failed to import processing.documents: {e}")
