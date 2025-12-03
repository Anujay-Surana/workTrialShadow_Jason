"""
Property-based tests for database module imports.

**Feature: retrieval-service-refactor, Property 1: Import Backward Compatibility**
**Validates: Requirements 2.4**
"""

import pytest
from hypothesis import given, strategies as st, settings


class TestDatabaseImports:
    """Test that database module imports work correctly after migration."""
    
    def test_data_module_imports(self):
        """Test that all expected functions can be imported from data module."""
        # Test importing the main module
        from retrieval_service import data
        
        # Test that supabase client is available
        assert hasattr(data, 'supabase')
        
        # Test User Management functions
        assert hasattr(data, 'get_user_by_email')
        assert hasattr(data, 'create_user')
        assert hasattr(data, 'update_user_status')
        
        # Test Email Management functions
        assert hasattr(data, 'insert_emails')
        assert hasattr(data, 'get_emails_by_thread')
        
        # Test Schedule Management functions
        assert hasattr(data, 'insert_schedules')
        
        # Test File Management functions
        assert hasattr(data, 'insert_files')
        assert hasattr(data, 'update_file_summary')
        
        # Test Attachment Management functions
        assert hasattr(data, 'insert_attachments')
        assert hasattr(data, 'update_attachment_summary')
        assert hasattr(data, 'get_attachments_by_email')
        
        # Test Embedding Management functions
        assert hasattr(data, 'insert_embedding')
        assert hasattr(data, 'batch_insert_embeddings')
        
        # Test User Deletion
        assert hasattr(data, 'delete_user_and_all_data')
    
    def test_imports_from_data(self):
        """Test that functions can be imported directly from data module."""
        from retrieval_service.data import (
            supabase,
            get_user_by_email,
            create_user,
            update_user_status,
            insert_emails,
            get_emails_by_thread,
            insert_schedules,
            insert_files,
            update_file_summary,
            insert_attachments,
            update_attachment_summary,
            get_attachments_by_email,
            insert_embedding,
            batch_insert_embeddings,
            delete_user_and_all_data,
        )
        
        # Verify all imports are callable (functions) or objects (supabase client)
        assert callable(get_user_by_email)
        assert callable(create_user)
        assert callable(update_user_status)
        assert callable(insert_emails)
        assert callable(get_emails_by_thread)
        assert callable(insert_schedules)
        assert callable(insert_files)
        assert callable(update_file_summary)
        assert callable(insert_attachments)
        assert callable(update_attachment_summary)
        assert callable(get_attachments_by_email)
        assert callable(insert_embedding)
        assert callable(batch_insert_embeddings)
        assert callable(delete_user_and_all_data)
        assert supabase is not None
    
    def test_database_module_import(self):
        """Test that database.py module can be imported directly."""
        from retrieval_service.data import database
        
        # Verify the module has the expected attributes
        assert hasattr(database, 'supabase')
        assert hasattr(database, 'get_user_by_email')
        assert hasattr(database, 'create_user')
    
    @given(st.sampled_from([
        'get_user_by_email',
        'create_user',
        'update_user_status',
        'insert_emails',
        'get_emails_by_thread',
        'insert_schedules',
        'insert_files',
        'update_file_summary',
        'insert_attachments',
        'update_attachment_summary',
        'get_attachments_by_email',
        'insert_embedding',
        'batch_insert_embeddings',
        'delete_user_and_all_data',
    ]))
    @settings(max_examples=100)
    def test_all_functions_importable(self, function_name):
        """
        Property test: For any database function name, it should be importable from data module.
        
        **Feature: retrieval-service-refactor, Property 1: Import Backward Compatibility**
        **Validates: Requirements 2.4**
        """
        from retrieval_service import data
        
        # Verify the function exists and is callable
        assert hasattr(data, function_name), f"Function {function_name} not found in data module"
        func = getattr(data, function_name)
        assert callable(func), f"{function_name} is not callable"
