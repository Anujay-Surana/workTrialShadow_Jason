"""
Property-based tests for LLM inference API consistency.

**Feature: retrieval-service-refactor, Property 9: LLM Inference API Consistency**
**Validates: Requirements 9.3**

Property: For any LLM inference operation (chat completion, reasoning), the operation should use OpenAI API.
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


def check_file_for_gemini_llm_inference(filepath):
    """
    Check if a file contains Gemini LLM inference calls.
    
    Returns:
        tuple: (has_gemini_llm, violations)
    """
    violations = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Check for Gemini LLM inference patterns (excluding embeddings)
        if 'genai.generate_content' in content or 'genai.GenerativeModel' in content:
            # Parse the AST to find actual LLM inference calls
            tree = ast.parse(content, filename=filepath)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_name = None
                    
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                    
                    # Check for Gemini content generation (not embedding)
                    if func_name in ['generate_content', 'generate_text', 'GenerativeModel']:
                        violations.append({
                            'type': 'call',
                            'line': node.lineno,
                            'detail': f"Gemini LLM inference call: {func_name}"
                        })
        
        return len(violations) > 0, violations
        
    except Exception as e:
        # If we can't parse the file, skip it
        return False, []


def check_file_uses_openai_for_llm_inference(filepath):
    """
    Check if a file that performs LLM inference uses OpenAI API.
    
    Returns:
        tuple: (performs_llm_inference, uses_openai)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Exclude __init__.py files (they just re-export)
        if '__init__' in filepath:
            return False, True
        
        # Check if file performs LLM inference operations
        # Look for chat completion patterns
        performs_llm_inference = any([
            'chat.completions.create' in content,
            'chat_completion' in content,
            'messages=' in content and ('role' in content and 'content' in content),
        ])
        
        # Exclude embedding-only files
        if 'embed' in filepath.lower() and 'chat' not in content.lower():
            return False, True
        
        if not performs_llm_inference:
            return False, True  # Doesn't perform LLM inference, so it's fine
        
        # Check if it uses OpenAI
        uses_openai = any([
            'from openai import' in content,
            'OpenAI(' in content,
            'AsyncOpenAI(' in content,
            'client.chat.completions.create' in content,
            'async_client.chat.completions.create' in content,
        ])
        
        return performs_llm_inference, uses_openai
        
    except Exception:
        return False, True


@settings(max_examples=1)
@given(st.just(None))
def test_no_gemini_llm_inference_calls(dummy):
    """
    Property: For any Python file in the system, it should not use Gemini for LLM inference.
    
    This test scans all Python files to ensure no Gemini LLM inference operations exist.
    """
    python_files = get_python_files()
    
    violations_by_file = {}
    
    for filepath in python_files:
        has_violation, violations = check_file_for_gemini_llm_inference(filepath)
        
        if has_violation:
            relative_path = os.path.relpath(filepath, Path(__file__).parent.parent)
            violations_by_file[relative_path] = violations
    
    # Assert no violations found
    if violations_by_file:
        error_msg = "Found Gemini LLM inference operations in the following files:\n"
        for filepath, violations in violations_by_file.items():
            error_msg += f"\n{filepath}:\n"
            for v in violations:
                error_msg += f"  Line {v['line']}: {v['detail']}\n"
        
        pytest.fail(error_msg)


@settings(max_examples=1)
@given(st.just(None))
def test_llm_inference_operations_use_openai(dummy):
    """
    Property: For any file that performs LLM inference operations, it should use OpenAI API.
    
    This test ensures all LLM inference operations route through OpenAI client.
    """
    python_files = get_python_files()
    
    violations = []
    
    for filepath in python_files:
        performs_llm_inference, uses_openai = check_file_uses_openai_for_llm_inference(filepath)
        
        if performs_llm_inference and not uses_openai:
            relative_path = os.path.relpath(filepath, Path(__file__).parent.parent)
            violations.append(relative_path)
    
    # Assert all LLM inference operations use OpenAI
    if violations:
        error_msg = "Found LLM inference operations not using OpenAI API in:\n"
        for filepath in violations:
            error_msg += f"  - {filepath}\n"
        
        pytest.fail(error_msg)


def test_openai_client_exists():
    """
    Verify that the OpenAI client module exists and exports LLM functions.
    """
    try:
        from retrieval_service.api.openai_client import chat_completion, rag_direct, react_with_tools_direct
        
        # Check that the functions exist
        assert callable(chat_completion), "chat_completion should be a callable function"
        assert callable(rag_direct), "rag_direct should be a callable function"
        assert callable(react_with_tools_direct), "react_with_tools_direct should be a callable function"
        
    except ImportError as e:
        pytest.fail(f"Failed to import OpenAI client: {e}")


def test_api_module_exports_openai_functions():
    """
    Verify that the API module exports OpenAI LLM functions.
    """
    try:
        from retrieval_service.api import chat_completion, rag_direct, react_with_tools_direct
        
        assert callable(chat_completion), "chat_completion should be exported from api module"
        assert callable(rag_direct), "rag_direct should be exported from api module"
        assert callable(react_with_tools_direct), "react_with_tools_direct should be exported from api module"
        
    except ImportError as e:
        pytest.fail(f"Failed to import OpenAI functions from api module: {e}")
