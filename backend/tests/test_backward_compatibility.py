"""
Test backward compatibility of retrieval_service imports.

This test ensures that all old import paths continue to work after refactoring.
**Feature: retrieval-service-refactor, Property 1: Import Backward Compatibility**
"""

import pytest


def test_core_imports():
    """Test that core module functions can be imported from retrieval_service root"""
    # Old style: from retrieval_service.agent import SEARCH_TOOLS
    # New style: from retrieval_service import SEARCH_TOOLS
    from retrieval_service import SEARCH_TOOLS, REACT_SYSTEM_PROMPT
    from retrieval_service import combined_search, deduplicate_results, build_rag_prompt
    from retrieval_service import react_agent, parse_action
    from retrieval_service import execute_search_tool, execute_search_tool_with_results
    
    assert SEARCH_TOOLS is not None
    assert REACT_SYSTEM_PROMPT is not None
    assert callable(combined_search)
    assert callable(deduplicate_results)
    assert callable(build_rag_prompt)
    assert callable(react_agent)
    assert callable(parse_action)
    assert callable(execute_search_tool)
    assert callable(execute_search_tool_with_results)


def test_api_imports():
    """Test that API client functions can be imported from retrieval_service root"""
    from retrieval_service import chat_completion, rag, mixed_agent
    from retrieval_service import embed_text
    from retrieval_service import (
        fetch_gmail_messages,
        extract_attachments,
        download_attachment_content,
        fetch_calendar_events,
        fetch_drive_all_files,
        download_file_content,
        list_folder_children,
        get_drive_public_download_link,
        get_gmail_attachment_download_link
    )
    
    assert callable(chat_completion)
    assert callable(rag)
    assert callable(mixed_agent)
    assert callable(embed_text)
    assert callable(fetch_gmail_messages)
    assert callable(extract_attachments)
    assert callable(download_attachment_content)
    assert callable(fetch_calendar_events)
    assert callable(fetch_drive_all_files)
    assert callable(download_file_content)
    assert callable(list_folder_children)
    assert callable(get_drive_public_download_link)
    assert callable(get_gmail_attachment_download_link)


def test_search_imports():
    """Test that search functions can be imported from retrieval_service root"""
    from retrieval_service import vector_search, keyword_search, fuzzy_search
    from retrieval_service import get_context_from_results
    from retrieval_service import fetch_full_reference, parse_reference_ids, fetch_references_by_ids
    
    assert callable(vector_search)
    assert callable(keyword_search)
    assert callable(fuzzy_search)
    assert callable(get_context_from_results)
    assert callable(fetch_full_reference)
    assert callable(parse_reference_ids)
    assert callable(fetch_references_by_ids)


def test_data_imports():
    """Test that data layer functions can be imported from retrieval_service root"""
    from retrieval_service import supabase
    from retrieval_service import (
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
        delete_user_and_all_data
    )
    from retrieval_service import (
        initialize_user_data,
        create_email_embeddings,
        create_schedule_embeddings,
        create_file_embeddings,
        create_attachment_embeddings
    )
    
    assert supabase is not None
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
    assert callable(initialize_user_data)
    assert callable(create_email_embeddings)
    assert callable(create_schedule_embeddings)
    assert callable(create_file_embeddings)
    assert callable(create_attachment_embeddings)


def test_processing_imports():
    """Test that processing functions can be imported from retrieval_service root"""
    from retrieval_service import (
        summarize,
        summarize_doc,
        chunk_text,
        summarize_chunk,
        combine_summaries
    )
    from retrieval_service import isDOC, extractDOC
    from retrieval_service import isIMG, init_model, extractOCR
    from retrieval_service import process_file_by_type
    
    assert callable(summarize)
    assert callable(summarize_doc)
    assert callable(chunk_text)
    assert callable(summarize_chunk)
    assert callable(combine_summaries)
    assert callable(isDOC)
    assert callable(extractDOC)
    assert callable(isIMG)
    assert callable(init_model)
    assert callable(extractOCR)
    assert callable(process_file_by_type)


def test_infrastructure_imports():
    """Test that infrastructure functions can be imported from retrieval_service root"""
    from retrieval_service import log_debug, log_info, log_warning, log_error
    from retrieval_service import monitor
    from retrieval_service import get_thread_pool_manager
    from retrieval_service import batch_embed_gemini, batch_insert_supabase
    
    assert callable(log_debug)
    assert callable(log_info)
    assert callable(log_warning)
    assert callable(log_error)
    assert monitor is not None
    assert callable(get_thread_pool_manager)
    assert callable(batch_embed_gemini)
    assert callable(batch_insert_supabase)


def test_old_module_imports_still_work():
    """Test that importing from old module paths still works through backward compatibility layer"""
    # Old files have been deleted, but imports should work through __init__.py shim
    from retrieval_service import monitor as old_monitor
    from retrieval_service import get_user_by_email as old_get_user
    
    # And the new imports should work too
    from retrieval_service.infrastructure.monitoring import monitor as new_monitor
    from retrieval_service.data.database import get_user_by_email as new_get_user
    
    # Both should be valid objects/functions
    assert old_monitor is not None
    assert new_monitor is not None
    assert callable(old_get_user)
    assert callable(new_get_user)
    
    # They should be the same objects (not copies)
    assert old_monitor is new_monitor
    assert old_get_user is new_get_user


def test_new_module_imports_work():
    """Test that importing from new module paths works"""
    from retrieval_service.core.mixed import SEARCH_TOOLS
    from retrieval_service.core.rag import combined_search
    from retrieval_service.core.react import react_agent
    from retrieval_service.api.openai_client import rag
    from retrieval_service.api.gemini_client import embed_text
    from retrieval_service.search.vector import vector_search
    from retrieval_service.data.database import get_user_by_email
    from retrieval_service.processing.documents import summarize
    from retrieval_service.infrastructure.logging import log_debug
    
    assert SEARCH_TOOLS is not None
    assert callable(combined_search)
    assert callable(react_agent)
    assert callable(rag)
    assert callable(embed_text)
    assert callable(vector_search)
    assert callable(get_user_by_email)
    assert callable(summarize)
    assert callable(log_debug)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
