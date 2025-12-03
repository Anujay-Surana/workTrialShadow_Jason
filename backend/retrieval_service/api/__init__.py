"""
External API integration module.

This module provides client interfaces for external APIs including:
- OpenAI API (for text generation and summarization)
- Gemini API (for embeddings)
- Google API (for Gmail, Calendar, and Drive access)

Note: Import submodules directly to avoid circular dependencies:
    from retrieval_service.api import openai_client
    from retrieval_service.api import gemini_client
    from retrieval_service.api import google_client
"""

# Don't import at module level to avoid circular dependencies
# Users should import submodules directly:
#   from retrieval_service.api import openai_client
#   from retrieval_service.api.gemini_client import embed_text

__all__ = [
    'openai_client',
    'gemini_client',
    'google_client'
]
