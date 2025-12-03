"""
Data access layer for the Memory Retrieval Service.

This module provides database operations and data initialization functionality.
"""

from .database import (
    # Supabase client
    supabase,
    
    # User Management
    get_user_by_email,
    create_user,
    update_user_status,
    
    # Email Management
    insert_emails,
    get_emails_by_thread,
    
    # Schedule Management
    insert_schedules,
    
    # File Management
    insert_files,
    update_file_summary,
    
    # Attachment Management
    insert_attachments,
    update_attachment_summary,
    get_attachments_by_email,
    
    # Embedding Management
    insert_embedding,
    batch_insert_embeddings,
    
    # User Deletion
    delete_user_and_all_data,
)

from .initialization import (
    initialize_user_data,
    create_email_embeddings,
    create_schedule_embeddings,
    create_file_embeddings,
    create_attachment_embeddings,
)

__all__ = [
    "supabase",
    "get_user_by_email",
    "create_user",
    "update_user_status",
    "insert_emails",
    "get_emails_by_thread",
    "insert_schedules",
    "insert_files",
    "update_file_summary",
    "insert_attachments",
    "update_attachment_summary",
    "get_attachments_by_email",
    "insert_embedding",
    "batch_insert_embeddings",
    "delete_user_and_all_data",
    "initialize_user_data",
    "create_email_embeddings",
    "create_schedule_embeddings",
    "create_file_embeddings",
    "create_attachment_embeddings",
]
