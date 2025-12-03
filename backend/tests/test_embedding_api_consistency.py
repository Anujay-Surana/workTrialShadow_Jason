"""
Property-based tests for embedding API consistency.

**Feature: retrieval-service-refactor, Property 7: Embedding API Consistency**
**Validates: Requirements 9.1, 9.4**

Property: For any embedding operation in the system, the operation should use Gemini API and not OpenAI API.
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


def check_file_for_openai_embedding(filepath):
    """
    Check if a file contains OpenAI embedding calls.
    
    Returns:
        tuple: (has_openai_embedding, violations)
    """
    violations = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Parse the AST
        tree = ast.parse(content, filename=filepath)
        
        # Check for OpenAI embedding imports
        for node in ast.walk(tree):
            # Check for imports of OpenAI embedding functions
            if isinstance(node, ast.ImportFrom):
                if node.module and 'openai' in node.module.lower():
                    for alias in node.names:
                        if 'embed' in alias.name.lower():
                            violations.append({
                                'type': 'import',
                                'line': node.lineno,
                                'detail': f"Import of OpenAI embedding: {alias.name}"
                            })
            
            # Check for function calls that might be OpenAI embeddings
            if isinstance(node, ast.Call):
                func_name = None
                
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                
                # Check for suspicious function names
                if func_name:
                    # OpenAI embedding patterns
                    if func_name in ['batch_embed_openai', 'embed_openai']:
                        violations.append({
                            'type': 'call',
                            'line': node.lineno,
                            'detail': f"Call to OpenAI embedding function: {func_name}"
                        })
                    
                    # Check for openai_client.embeddings.create pattern
                    if func_name == 'create' and isinstance(node.func, ast.Attribute):
                        if isinstance(node.func.value, ast.Attribute):
                            if node.func.value.attr == 'embeddings':
                                violations.append({
                                    'type': 'call',
                                    'line': node.lineno,
                                    'detail': "Call to OpenAI embeddings.create()"
                                })
        
        return len(violations) > 0, violations
        
    except Exception as e:
        # If we can't parse the file, skip it
        return False, []


def check_file_uses_gemini_for_embeddings(filepath):
    """
    Check if a file that performs embeddings uses Gemini API.
    
    Returns:
        tuple: (performs_embedding, uses_gemini)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if file actually CALLS embedding operations (not just mentions them)
        # Look for actual function calls like embed_text(...) or genai.embed_content(...)
        performs_embedding = any([
            'embed_text(' in content,
            'embed_content(' in content,
            'genai.embed' in content,
            'embeddings.create(' in content
        ])
        
        if not performs_embedding:
            return False, True  # Doesn't perform embedding, so it's fine
        
        # Check if it uses Gemini
        uses_gemini = any([
            'gemini_client' in content,
            'gemni_api_utils' in content,  # Old import path
            'genai.embed' in content,
            'from retrieval_service.api import embed_text' in content,
            'from retrieval_service.api.gemini_client import embed_text' in content
        ])
        
        return performs_embedding, uses_gemini
        
    except Exception:
        return False, True


@settings(max_examples=1)
@given(st.just(None))
def test_no_openai_embedding_calls(dummy):
    """
    Property: For any Python file in the system, it should not contain OpenAI embedding calls.
    
    This test scans all Python files to ensure no OpenAI embedding operations exist.
    """
    python_files = get_python_files()
    
    violations_by_file = {}
    
    for filepath in python_files:
        has_violation, violations = check_file_for_openai_embedding(filepath)
        
        if has_violation:
            relative_path = os.path.relpath(filepath, Path(__file__).parent.parent)
            violations_by_file[relative_path] = violations
    
    # Assert no violations found
    if violations_by_file:
        error_msg = "Found OpenAI embedding operations in the following files:\n"
        for filepath, violations in violations_by_file.items():
            error_msg += f"\n{filepath}:\n"
            for v in violations:
                error_msg += f"  Line {v['line']}: {v['detail']}\n"
        
        pytest.fail(error_msg)


@settings(max_examples=1)
@given(st.just(None))
def test_embedding_operations_use_gemini(dummy):
    """
    Property: For any file that performs embedding operations, it should use Gemini API.
    
    This test ensures all embedding operations route through Gemini client.
    """
    python_files = get_python_files()
    
    violations = []
    
    for filepath in python_files:
        performs_embedding, uses_gemini = check_file_uses_gemini_for_embeddings(filepath)
        
        if performs_embedding and not uses_gemini:
            relative_path = os.path.relpath(filepath, Path(__file__).parent.parent)
            violations.append(relative_path)
    
    # Assert all embedding operations use Gemini
    if violations:
        error_msg = "Found embedding operations not using Gemini API in:\n"
        for filepath in violations:
            error_msg += f"  - {filepath}\n"
        
        pytest.fail(error_msg)


def test_gemini_client_exists():
    """
    Verify that the Gemini client module exists and exports embed_text.
    """
    try:
        from retrieval_service.api.gemini_client import embed_text
        assert callable(embed_text), "embed_text should be a callable function"
    except ImportError as e:
        pytest.fail(f"Failed to import Gemini client: {e}")


def test_api_module_exports_embed_text():
    """
    Verify that the API module exports embed_text from Gemini client.
    """
    try:
        from retrieval_service.api import embed_text
        assert callable(embed_text), "embed_text should be exported from api module"
    except ImportError as e:
        pytest.fail(f"Failed to import embed_text from api module: {e}")
