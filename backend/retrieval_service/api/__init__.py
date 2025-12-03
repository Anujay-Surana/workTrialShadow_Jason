"""
External API integration module.

This module provides client interfaces for external APIs including:
- OpenAI API (for text generation and summarization)
- Gemini API (for embeddings)
- Google API (for Gmail, Calendar, and Drive access)
"""

from retrieval_service.api.gemini_client import embed_text
from retrieval_service.api.openai_client import chat_completion, rag_direct, react_with_tools_direct
from retrieval_service.api.google_client import (
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

__all__ = [
    'embed_text',
    'chat_completion',
    'rag_direct',
    'react_with_tools_direct',
    'fetch_gmail_messages',
    'extract_attachments',
    'download_attachment_content',
    'fetch_calendar_events',
    'fetch_drive_all_files',
    'download_file_content',
    'list_folder_children',
    'get_drive_public_download_link',
    'get_gmail_attachment_download_link'
]
