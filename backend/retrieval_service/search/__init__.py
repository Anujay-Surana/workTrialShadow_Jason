"""
Search module providing unified interface for all search operations.

This module exports vector, keyword, and fuzzy search functions,
along with utilities for context extraction and search tool execution.
"""

import traceback
from typing import List, Dict, Tuple, Any
from retrieval_service.data.database import supabase
from retrieval_service.api.gemini_client import embed_text
from retrieval_service.infrastructure.logging import log_debug, log_error

# Import search functions
from .vector import vector_search
from .keyword import keyword_search
from .fuzzy import fuzzy_search
from .reference import (
    fetch_full_reference,
    parse_reference_ids,
    fetch_references_by_ids
)

# Export all search functions
__all__ = [
    'vector_search',
    'keyword_search',
    'fuzzy_search',
    'fetch_full_reference',
    'parse_reference_ids',
    'fetch_references_by_ids',
    'get_context_from_results',
    'execute_search_tool'
]


def get_context_from_results(
    user_id: str,
    search_results: List[Dict]
) -> Tuple[str, List[Dict]]:
    """
    Fetch full content from search results and format as context.
    
    Args:
        user_id: User UUID for filtering results
        search_results: List of search result dictionaries
        
    Returns:
        Tuple of (formatted_context_string, list_of_references)
    """
    context_parts = []
    references = []

    for result in search_results:
        result_type = result['type']
        result_id = result['id']

        try:
            if result_type == 'email':
                response = supabase.table('emails').select('*')\
                    .eq('user_id', user_id).eq('id', result_id).execute()
                if response.data and len(response.data) > 0:
                    email = response.data[0]
                    context_parts.append(
                        f"[Email ID: email_{result_id}]\n"
                        f"From: {email.get('from_user', 'unknown')}, "
                        f"To: {email.get('to_user', 'unknown')}\n"
                        f"CC: {email.get('cc', '')}, BCC: {email.get('bcc', '')}\n"
                        f"Subject: {email.get('subject', 'No subject')}, "
                        f"Date: {email.get('date', 'unknown')}\n"
                        f"Content: {email.get('body', '')}\n"
                    )
                    references.append({
                        'type': 'email',
                        'id': result_id,
                        'title': email.get('subject', 'No subject'),
                        'from': email.get('from_user', 'unknown'),
                        'date': email.get('date', 'unknown')
                    })

            elif result_type == 'schedule':
                response = supabase.table('schedules').select('*')\
                    .eq('user_id', user_id).eq('id', result_id).execute()
                if response.data and len(response.data) > 0:
                    schedule = response.data[0]
                    context_parts.append(
                        f"[Schedule ID: schedule_{result_id}]\n"
                        f"Event: {schedule.get('summary', 'No title')}\n"
                        f"Description: {schedule.get('description', 'No description')}\n"
                        f"Location: {schedule.get('location', 'No location')}\n"
                        f"Time: {schedule.get('start_time', 'unknown')} "
                        f"to {schedule.get('end_time', 'unknown')}\n"
                    )
                    references.append({
                        'type': 'schedule',
                        'id': result_id,
                        'title': schedule.get('summary', 'No title'),
                        'start_time': schedule.get('start_time', 'unknown'),
                        'location': schedule.get('location', 'No location')
                    })

            elif result_type == 'file':
                response = supabase.table('files').select('*')\
                    .eq('user_id', user_id).eq('id', result_id).execute()
                if response.data and len(response.data) > 0:
                    file = response.data[0]
                    context_parts.append(
                        f"[File ID: file_{result_id}]\n"
                        f"Name: {file.get('name', 'unknown')}\n"
                        f'Size: {file.get("size", "unknown")} bytes\n'
                        f"Metadata: {file.get('metadata', 'No metadata')}\n"
                        f"Path: {file.get('path', 'unknown')}\n"
                        f"Type: {file.get('mime_type', 'unknown')}\n"
                        f"Summary: {file.get('summary', 'No summary available')}\n"
                    )
                    references.append({
                        'type': 'file',
                        'id': result_id,
                        'title': file.get('name', 'unknown'),
                        'path': file.get('path', 'unknown'),
                        'mime_type': file.get('mime_type', 'unknown')
                    })

            elif result_type == 'attachment':
                response = supabase.table('attachments').select('*')\
                    .eq('user_id', user_id).eq('id', result_id).execute()
                if response.data and len(response.data) > 0:
                    attachment = response.data[0]
                    email_id = attachment.get('email_id', 'unknown')

                    email_info = None
                    try:
                        email_response = supabase.table('emails').select('*')\
                            .eq('user_id', user_id).eq('id', email_id).execute()
                        if email_response.data:
                            email_info = email_response.data[0]
                    except Exception as e:
                        log_error(f"Error fetching email info for attachment {result_id}: {e}")

                    context_text = (
                        f"[Attachment ID: attachment_{result_id}]\n"
                        f"Filename: {attachment.get('filename', 'unknown')}\n"
                        f"Type: {attachment.get('mime_type', 'unknown')}\n"
                        f"Size: {attachment.get('size', 'unknown')} bytes\n"
                    )

                    if email_info:
                        context_text += (
                            f"From email sent by: {email_info.get('from_user', 'unknown')}\n"
                            f"To: {email_info.get('to_user', 'unknown')}\n"
                        )
                        if email_info.get('cc'):
                            context_text += f"CC: {email_info.get('cc')}\n"
                        if email_info.get('bcc'):
                            context_text += f"BCC: {email_info.get('bcc')}\n"
                        context_text += (
                            f"Email date: {email_info.get('date', 'unknown')}\n"
                            f"Email subject: {email_info.get('subject', 'No subject')}\n"
                        )

                    context_text += (
                        f"Summary: {attachment.get('summary', 'No summary available')}\n"
                    )
                    context_parts.append(context_text)

                    ref = {
                        'type': 'attachment',
                        'id': result_id,
                        'title': attachment.get('filename', 'unknown'),
                        'mime_type': attachment.get('mime_type', 'unknown'),
                        'email_id': email_id
                    }

                    if email_info:
                        ref['from'] = email_info.get('from_user', 'unknown')
                        ref['to'] = email_info.get('to_user', 'unknown')
                        ref['cc'] = email_info.get('cc', '')
                        ref['bcc'] = email_info.get('bcc', '')
                        ref['date'] = email_info.get('date', 'unknown')
                        ref['subject'] = email_info.get('subject', 'No subject')

                    references.append(ref)

        except Exception as e:
            log_error(f"Error fetching {result_type} {result_id}: {e}")

    context_str = "\n---\n".join(context_parts)
    return context_str, references


async def execute_search_tool(function_name: str, arguments: Dict[str, Any], user_id: str) -> Dict:
    """
    Execute a search tool invoked by the LLM during ReAct.
    Returns a dict suitable for LLM tool messages:
        {
            "ok": true/false,
            "results": [...],
            "context": "...",
            "references": [...],
            "raw_results": ...
        }

    Args:
        function_name: Name of the search function to execute
        arguments: Dictionary of arguments for the search function
        user_id: User UUID for filtering results
        
    Returns:
        Dictionary with search results and context
    """

    try:
        # Parse arguments
        query: str = arguments.get("query", "")
        keywords: List[str] = arguments.get("keywords", [])
        search_types: List[str] = arguments.get("search_types", None)
        top_k: int = int(arguments.get("top_k", 10))

        # Route by tool name
        if function_name == "vector_search":
            if not query:
                return {"ok": False, "error": "vector_search requires query (string)"}

            embedding = embed_text(query)
            raw_results = vector_search(
                user_id=user_id,
                query_embedding=embedding,
                search_types=search_types,
                top_k=top_k,
            )

        elif function_name == "keyword_search":
            if not keywords and not query:
                return {"ok": False, "error": "keyword_search requires keywords or query"}

            kw = keywords or [query]
            raw_results = keyword_search(
                user_id=user_id,
                keywords=kw,
                top_k=top_k,
            )

        elif function_name == "fuzzy_search":
            if not query:
                return {"ok": False, "error": "fuzzy_search requires query"}

            raw_results = fuzzy_search(
                user_id=user_id,
                query=query,
                top_k=top_k,
            )

        else:
            return {
                "ok": False,
                "error": f"Unknown tool: {function_name}"
            }

        # Expand context & references
        context, references = get_context_from_results(user_id, raw_results)

        # Return to LLM
        return {
            "ok": True,
            "results": raw_results,
            "context": context,
            "references": references,
            "raw_results": raw_results
        }

    except Exception as e:
        traceback.print_exc()
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
