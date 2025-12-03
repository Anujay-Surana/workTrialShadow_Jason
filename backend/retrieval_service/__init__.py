"""
Retrieval Service - Backward Compatibility Layer

This module provides backward-compatible imports for the refactored retrieval service.
All old import paths continue to work while the codebase uses the new modular structure.

New structure:
- core/: Core business logic (agent, RAG, ReAct)
- api/: External API clients (OpenAI, Gemini, Google)
- search/: Search and retrieval functions
- data/: Database operations and initialization
- processing/: Document processing and OCR
- infrastructure/: Logging, monitoring, threading, batch operations
"""

# ======================================================
# Core Module Exports (agent.py, rag_utils.py, react_agent_utils.py)
# ======================================================

# From core/agent.py
from .core.mixed import SEARCH_TOOLS, MIXED_MODE_SYSTEM_PROMPT

# From core/rag.py
from .core.rag import (
    combined_search,
    deduplicate_results,
    build_rag_prompt,
    RAG_SYSTEM_PROMPT
)

# From core/react.py
from .core.react import (
    react_agent,
    parse_action,
    execute_search_tool,
    execute_search_tool_with_results,
    REACT_SYSTEM_PROMPT
)

# ======================================================
# API Module Exports (openai_api_utils.py, gemni_api_utils.py, google_api_utils.py)
# ======================================================

# From api/openai_client.py
from .api.openai_client import (
    chat_completion,
    rag,
    mixed_agent
)

# From api/gemini_client.py
from .api.gemini_client import embed_text

# From api/google_client.py
from .api.google_client import (
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

# ======================================================
# Search Module Exports (search_utils.py, reference_utils.py)
# ======================================================

# From search/vector.py, search/keyword.py, search/fuzzy.py
from .search.vector import vector_search
from .search.keyword import keyword_search
from .search.fuzzy import fuzzy_search

# From search/__init__.py
from .search import (
    get_context_from_results,
    execute_search_tool as search_execute_search_tool
)

# From search/reference.py
from .search.reference import (
    fetch_full_reference,
    parse_reference_ids,
    fetch_references_by_ids
)

# ======================================================
# Data Module Exports (supabase_utils.py, google_api_utils.py initialization)
# ======================================================

# From data/database.py
from .data.database import (
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
    delete_user_and_all_data
)

# From data/initialization.py
from .data.initialization import (
    initialize_user_data,
    create_email_embeddings,
    create_schedule_embeddings,
    create_file_embeddings,
    create_attachment_embeddings
)

# ======================================================
# Processing Module Exports (document_utils.py, doc_utils.py, ocr_utils.py)
# ======================================================

# From processing/documents.py
from .processing.documents import (
    summarize,
    summarize_doc,
    chunk_text,
    summarize_chunk,
    combine_summaries
)

# From processing/parsers.py
from .processing.parsers import (
    isDOC,
    extractDOC
)

# From processing/ocr.py
from .processing.ocr import (
    isIMG,
    init_model,
    extractOCR
)

# From processing/__init__.py
from .processing import process_file_by_type

# ======================================================
# Infrastructure Module Exports (rate_limit_monitor.py, thread_pool_manager.py, batch_utils.py)
# ======================================================

# From infrastructure/logging.py
from .infrastructure.logging import (
    log_debug,
    log_info,
    log_warning,
    log_error
)

# From infrastructure/monitoring.py
from .infrastructure.monitoring import monitor

# From infrastructure/threading.py
from .infrastructure.threading import get_thread_pool_manager

# From infrastructure/batch.py
from .infrastructure.batch import (
    batch_embed_gemini,
    batch_insert_supabase
)

# ======================================================
# Backward Compatibility Aliases
# ======================================================

# These aliases ensure that old import patterns continue to work
# Example: from retrieval_service.openai_api_utils import rag
# Now works as: from retrieval_service import rag

__all__ = [
    # Core
    'SEARCH_TOOLS',
    'REACT_SYSTEM_PROMPT',
    'RAG_SYSTEM_PROMPT',
    'MIXED_MODE_SYSTEM_PROMPT',
    'combined_search',
    'deduplicate_results',
    'build_rag_prompt',
    'react_agent',
    'parse_action',
    'execute_search_tool',
    'execute_search_tool_with_results',
    
    # API
    'chat_completion',
    'rag',
    'mixed_agent',
    'embed_text',
    'fetch_gmail_messages',
    'extract_attachments',
    'download_attachment_content',
    'fetch_calendar_events',
    'fetch_drive_all_files',
    'download_file_content',
    'list_folder_children',
    'get_drive_public_download_link',
    'get_gmail_attachment_download_link',
    
    # Search
    'vector_search',
    'keyword_search',
    'fuzzy_search',
    'get_context_from_results',
    'search_execute_search_tool',
    'fetch_full_reference',
    'parse_reference_ids',
    'fetch_references_by_ids',
    
    # Data
    'supabase',
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
    'initialize_user_data',
    'create_email_embeddings',
    'create_schedule_embeddings',
    'create_file_embeddings',
    'create_attachment_embeddings',
    
    # Processing
    'summarize',
    'summarize_doc',
    'chunk_text',
    'summarize_chunk',
    'combine_summaries',
    'isDOC',
    'extractDOC',
    'isIMG',
    'init_model',
    'extractOCR',
    'process_file_by_type',
    
    # Infrastructure
    'log_debug',
    'log_info',
    'log_warning',
    'log_error',
    'monitor',
    'get_thread_pool_manager',
    'batch_embed_gemini',
    'batch_insert_supabase',
]
