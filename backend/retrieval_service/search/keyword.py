"""
Keyword search utilities for exact keyword matching.

This module provides keyword-based search across emails, schedules,
files, and attachments using database text matching.
"""

from retrieval_service.data.database import supabase
from retrieval_service.infrastructure.logging import log_debug, log_error
from typing import List, Dict


def keyword_search(
    user_id: str,
    keywords: List[str],
    top_k: int = 10
) -> List[Dict]:
    """
    Perform keyword search across emails, schedules, files, and attachments.

    Args:
        user_id: User UUID
        keywords: List of keywords to search
        top_k: Max results per type

    Returns:
        List of search results with scores
    """
    results = []

    # Search emails
    try:
        for keyword in keywords:
            response = supabase.table('emails').select(
                'id, subject, body'
            ).eq('user_id', user_id).filter(
                'subject', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()

            # Also search in body
            response2 = supabase.table('emails').select(
                'id, subject, body'
            ).eq('user_id', user_id).filter(
                'body', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()

            combined_data = response.data + response2.data
            seen_ids = set()
            unique_data = []
            for item in combined_data:
                if item['id'] not in seen_ids:
                    seen_ids.add(item['id'])
                    unique_data.append(item)

            for item in unique_data[:top_k]:
                score = 0.0
                if keyword.lower() in (item.get('subject', '') or '').lower():
                    score += 0.5
                if keyword.lower() in (item.get('body', '') or '').lower():
                    score += 0.3

                results.append({
                    'type': 'email',
                    'id': item['id'],
                    'score': score,
                    'source': 'keyword'
                })
    except Exception as e:
        log_error(f"Error in keyword search for emails: {e}")

    # Search schedules
    try:
        for keyword in keywords:
            response = supabase.table('schedules').select(
                'id, summary, description'
            ).eq('user_id', user_id).filter(
                'summary', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()

            response2 = supabase.table('schedules').select(
                'id, summary, description'
            ).eq('user_id', user_id).filter(
                'description', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()

            combined_data = response.data + response2.data
            seen_ids = set()
            unique_data = []
            for item in combined_data:
                if item['id'] not in seen_ids:
                    seen_ids.add(item['id'])
                    unique_data.append(item)

            for item in unique_data[:top_k]:
                score = 0.0
                if keyword.lower() in (item.get('summary', '') or '').lower():
                    score += 0.5
                if keyword.lower() in (item.get('description', '') or '').lower():
                    score += 0.3

                results.append({
                    'type': 'schedule',
                    'id': item['id'],
                    'score': score,
                    'source': 'keyword'
                })
    except Exception as e:
        log_error(f"Error in keyword search for schedules: {e}")

    # Search files
    try:
        for keyword in keywords:
            response = supabase.table('files').select(
                'id, name, summary'
            ).eq('user_id', user_id).filter(
                'name', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()

            response2 = supabase.table('files').select(
                'id, name, summary'
            ).eq('user_id', user_id).filter(
                'summary', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()

            combined_data = response.data + response2.data
            seen_ids = set()
            unique_data = []
            for item in combined_data:
                if item['id'] not in seen_ids:
                    seen_ids.add(item['id'])
                    unique_data.append(item)

            for item in unique_data[:top_k]:
                score = 0.0
                if keyword.lower() in (item.get('name', '') or '').lower():
                    score += 0.5
                if keyword.lower() in (item.get('summary', '') or '').lower():
                    score += 0.3

                results.append({
                    'type': 'file',
                    'id': item['id'],
                    'score': score,
                    'source': 'keyword'
                })
    except Exception as e:
        log_error(f"Error in keyword search for files: {e}")

    # Search attachments
    try:
        for keyword in keywords:
            response = supabase.table('attachments').select(
                'id, filename, summary'
            ).eq('user_id', user_id).filter(
                'filename', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()

            response2 = supabase.table('attachments').select(
                'id, filename, summary'
            ).eq('user_id', user_id).filter(
                'summary', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()

            combined_data = response.data + response2.data
            seen_ids = set()
            unique_data = []
            for item in combined_data:
                if item['id'] not in seen_ids:
                    seen_ids.add(item['id'])
                    unique_data.append(item)

            for item in unique_data[:top_k]:
                score = 0.0
                if keyword.lower() in (item.get('filename', '') or '').lower():
                    score += 0.5
                if keyword.lower() in (item.get('summary', '') or '').lower():
                    score += 0.3

                results.append({
                    'type': 'attachment',
                    'id': item['id'],
                    'score': score,
                    'source': 'keyword'
                })
    except Exception as e:
        log_error(f"Error in keyword search for attachments: {e}")

    return results
