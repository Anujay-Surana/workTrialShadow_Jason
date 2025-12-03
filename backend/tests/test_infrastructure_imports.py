"""
Property-based tests for infrastructure module imports.

**Feature: retrieval-service-refactor, Property 2: Module Import Success**
"""

import importlib
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st


# Property 2: Module Import Success
# For any module in the refactored structure, importing the module should succeed without errors.
# Validates: Requirements 3.1


def test_infrastructure_logging_module_import():
    """
    **Feature: retrieval-service-refactor, Property 2: Module Import Success**
    **Validates: Requirements 3.1**
    
    Test that the infrastructure.logging module can be imported successfully.
    """
    try:
        from retrieval_service.infrastructure import logging
        assert hasattr(logging, 'log_debug')
        assert hasattr(logging, 'log_info')
        assert hasattr(logging, 'log_warning')
        assert hasattr(logging, 'log_error')
    except ImportError as e:
        pytest.fail(f"Failed to import infrastructure.logging module: {e}")


def test_infrastructure_monitoring_module_import():
    """
    **Feature: retrieval-service-refactor, Property 2: Module Import Success**
    **Validates: Requirements 3.1**
    
    Test that the infrastructure.monitoring module can be imported successfully.
    """
    try:
        from retrieval_service.infrastructure import monitoring
        assert hasattr(monitoring, 'RateLimitMonitor')
        assert hasattr(monitoring, 'monitor')
    except ImportError as e:
        pytest.fail(f"Failed to import infrastructure.monitoring module: {e}")


def test_infrastructure_threading_module_import():
    """
    **Feature: retrieval-service-refactor, Property 2: Module Import Success**
    **Validates: Requirements 3.1**
    
    Test that the infrastructure.threading module can be imported successfully.
    """
    try:
        from retrieval_service.infrastructure import threading
        assert hasattr(threading, 'GlobalThreadPoolManager')
        assert hasattr(threading, 'get_thread_pool_manager')
    except ImportError as e:
        pytest.fail(f"Failed to import infrastructure.threading module: {e}")


def test_infrastructure_batch_module_import():
    """
    **Feature: retrieval-service-refactor, Property 2: Module Import Success**
    **Validates: Requirements 3.1**
    
    Test that the infrastructure.batch module can be imported successfully.
    """
    try:
        from retrieval_service.infrastructure import batch
        assert hasattr(batch, 'batch_embed_gemini')
        assert hasattr(batch, 'batch_insert_supabase')
    except ImportError as e:
        pytest.fail(f"Failed to import infrastructure.batch module: {e}")


def test_infrastructure_package_exports():
    """
    **Feature: retrieval-service-refactor, Property 2: Module Import Success**
    **Validates: Requirements 3.1**
    
    Test that the infrastructure package exports all expected functions and objects.
    """
    try:
        from retrieval_service import infrastructure
        
        # Check logging exports
        assert hasattr(infrastructure, 'log_debug')
        assert hasattr(infrastructure, 'log_info')
        assert hasattr(infrastructure, 'log_warning')
        assert hasattr(infrastructure, 'log_error')
        
        # Check monitoring exports
        assert hasattr(infrastructure, 'monitor')
        
        # Check threading exports
        assert hasattr(infrastructure, 'get_thread_pool_manager')
        
        # Check batch exports
        assert hasattr(infrastructure, 'batch_embed_gemini')
        assert hasattr(infrastructure, 'batch_insert_supabase')
        
    except ImportError as e:
        pytest.fail(f"Failed to import infrastructure package: {e}")
    except AttributeError as e:
        pytest.fail(f"Infrastructure package missing expected export: {e}")


@given(
    module_name=st.sampled_from([
        'retrieval_service.infrastructure.logging',
        'retrieval_service.infrastructure.monitoring',
        'retrieval_service.infrastructure.threading',
        'retrieval_service.infrastructure.batch',
    ])
)
@settings(max_examples=100)
def test_module_import_idempotency(module_name):
    """
    **Feature: retrieval-service-refactor, Property 2: Module Import Success**
    **Validates: Requirements 3.1**
    
    Property: For any infrastructure module, importing it multiple times
    should succeed and return the same module object (idempotency).
    """
    try:
        # First import
        module1 = importlib.import_module(module_name)
        
        # Second import
        module2 = importlib.import_module(module_name)
        
        # Should be the same object
        assert module1 is module2, \
            f"Module {module_name} returned different objects on repeated imports"
        
    except ImportError as e:
        pytest.fail(f"Failed to import module {module_name}: {e}")


def test_monitor_singleton_consistency():
    """
    **Feature: retrieval-service-refactor, Property 2: Module Import Success**
    **Validates: Requirements 3.1**
    
    Test that the monitor singleton is consistent across imports.
    """
    try:
        from retrieval_service.infrastructure.monitoring import monitor as monitor1
        from retrieval_service.infrastructure import monitor as monitor2
        
        # Should be the same object
        assert monitor1 is monitor2, \
            "Monitor singleton is not consistent across different import paths"
        
    except ImportError as e:
        pytest.fail(f"Failed to import monitor: {e}")


def test_thread_pool_manager_singleton_consistency():
    """
    **Feature: retrieval-service-refactor, Property 2: Module Import Success**
    **Validates: Requirements 3.1**
    
    Test that the thread pool manager singleton is consistent across imports.
    """
    try:
        from retrieval_service.infrastructure.threading import get_thread_pool_manager
        from retrieval_service.infrastructure import get_thread_pool_manager as get_manager2
        
        # Get instances
        manager1 = get_thread_pool_manager()
        manager2 = get_manager2()
        
        # Should be the same object
        assert manager1 is manager2, \
            "Thread pool manager singleton is not consistent across different import paths"
        
    except ImportError as e:
        pytest.fail(f"Failed to import thread pool manager: {e}")


@given(
    function_name=st.sampled_from([
        'log_debug', 'log_info', 'log_warning', 'log_error',
        'batch_embed_gemini', 'batch_insert_supabase',
        'get_thread_pool_manager'
    ])
)
@settings(max_examples=100)
def test_exported_functions_are_callable(function_name):
    """
    **Feature: retrieval-service-refactor, Property 2: Module Import Success**
    **Validates: Requirements 3.1**
    
    Property: For any exported function from infrastructure package,
    the function should be callable.
    """
    try:
        from retrieval_service import infrastructure
        
        func = getattr(infrastructure, function_name)
        assert callable(func), \
            f"Exported function {function_name} is not callable"
        
    except ImportError as e:
        pytest.fail(f"Failed to import infrastructure package: {e}")
    except AttributeError as e:
        pytest.fail(f"Function {function_name} not found in infrastructure package: {e}")
