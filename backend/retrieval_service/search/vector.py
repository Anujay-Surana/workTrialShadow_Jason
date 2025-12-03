"""
Vector search utilities for semantic similarity using embeddings.

This module provides vector similarity search across emails, schedules,
files, and attachments using Supabase RPC functions.
"""

from retrieval_service.data.database import supabase
from retrieval_service.infrastructure.logging import log_debug, log_error
from typing import List, Dict


def vector_search(
    user_id: str,
    query_embedding: List[float],
    search_types: List[str] = None,
    top_k: int = 10
) -> List[Dict]:
    """
    Perform vector search using Supabase RPC functions.

    Args:
        user_id: User UUID
        query_embedding: Query embedding vector
        search_types: List of types to search ('email_context', 'schedule_context', 'file_context', 'attachment_context')
        top_k: Number of results per type

    Returns:
        List of search results with scores
    """
    if search_types is None:
        search_types = [
            'email_context',
            'schedule_context',
            'file_context',
            'attachment_context'
        ]

    results = []

    for search_type in search_types:
        try:
            if 'email' in search_type:
                response = supabase.rpc(
                    'match_email_embeddings',
                    {
                        '_user_id': user_id,
                        '_query_embedding': query_embedding,
                        '_type': search_type,
                        '_match_threshold': 0.2,
                        '_match_count': top_k
                    }
                ).execute()

                for item in response.data:
                    results.append({
                        'type': 'email',
                        'id': item['email_id'],
                        'embedding_type': item['type'],
                        'score': item['similarity'],
                        'source': 'vector'
                    })

            elif 'schedule' in search_type:
                response = supabase.rpc(
                    'match_schedule_embeddings',
                    {
                        '_user_id': user_id,
                        '_query_embedding': query_embedding,
                        '_type': search_type,
                        '_match_threshold': 0.2,
                        '_match_count': top_k
                    }
                ).execute()

                for item in response.data:
                    results.append({
                        'type': 'schedule',
                        'id': item['schedule_id'],
                        'embedding_type': item['type'],
                        'score': item['similarity'],
                        'source': 'vector'
                    })

            elif 'file' in search_type:
                response = supabase.rpc(
                    'match_file_embeddings',
                    {
                        '_user_id': user_id,
                        '_query_embedding': query_embedding,
                        '_type': search_type,
                        '_match_threshold': 0.2,
                        '_match_count': top_k
                    }
                ).execute()

                for item in response.data:
                    results.append({
                        'type': 'file',
                        'id': item['file_id'],
                        'embedding_type': item['type'],
                        'score': item['similarity'],
                        'source': 'vector'
                    })

            elif 'attachment' in search_type:
                response = supabase.rpc(
                    'match_attachment_embeddings',
                    {
                        '_user_id': user_id,
                        '_query_embedding': query_embedding,
                        '_type': search_type,
                        '_match_threshold': 0.2,
                        '_match_count': top_k
                    }
                ).execute()

                for item in response.data:
                    results.append({
                        'type': 'attachment',
                        'id': item['attachment_id'],
                        'embedding_type': item['type'],
                        'score': item['similarity'],
                        'source': 'vector'
                    })

        except Exception as e:
            log_error(f"Error in vector search for {search_type}: {e}")

    return results
