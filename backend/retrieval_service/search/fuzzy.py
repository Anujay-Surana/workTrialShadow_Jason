"""
Fuzzy search utilities for approximate string matching.

This module provides fuzzy search across emails, schedules, files,
and attachments using rapidfuzz for similarity scoring.
"""

from retrieval_service.data.database import supabase
from retrieval_service.infrastructure.logging import log_debug, log_error
from typing import List, Dict
from rapidfuzz import fuzz


def fuzzy_search(
    user_id: str,
    query: str,
    top_k: int = 10
) -> List[Dict]:
    """
    FULL fuzzy search across emails, schedules, files, attachments.
    Covers ALL relevant text fields.
    
    Args:
        user_id: User UUID
        query: Search query string
        top_k: Maximum number of results to return
        
    Returns:
        List of search results sorted by fuzzy match score
    """
    results = []

    def append_results(response, r_type, fields, id_field="id"):
        for item in response.data:
            merged_text = " ".join([(item.get(f) or "") for f in fields])
            score = fuzz.partial_ratio(
                query.lower(), merged_text.lower()
            ) / 100.0
            results.append({
                "type": r_type,
                "id": item[id_field],
                "score": float(score),
                "source": "fuzzy"
            })

    # EMAILS
    try:
        resp = supabase.table("emails").select(
            "id, subject, body, from_user, to_user, cc, bcc"
        ).eq("user_id", user_id).or_(
            "subject.ilike.%{}%,body.ilike.%{}%,from_user.ilike.%{}%,to_user.ilike.%{}%,cc.ilike.%{}%,bcc.ilike.%{}%".format(
                query, query, query, query, query, query
            )
        ).limit(top_k).execute()

        append_results(resp, "email",
                       ["subject", "body", "from_user", "to_user", "cc", "bcc"])
    except Exception as e:
        log_error(f"Error in fuzzy email search: {e}")

    # SCHEDULES
    try:
        resp = supabase.table("schedules").select(
            "id, summary, description, location"
        ).eq("user_id", user_id).or_(
            "summary.ilike.%{}%,description.ilike.%{}%,location.ilike.%{}%".format(
                query, query, query
            )
        ).limit(top_k).execute()

        append_results(resp, "schedule",
                       ["summary", "description", "location"])
    except Exception as e:
        log_error(f"Error in fuzzy schedule search: {e}")

    # FILES
    try:
        resp = supabase.table("files").select(
            "id, name, path, summary, owner_email, owner_name"
        ).eq("user_id", user_id).or_(
            "name.ilike.%{}%,path.ilike.%{}%,summary.ilike.%{}%,owner_email.ilike.%{}%,owner_name.ilike.%{}%".format(
                query, query, query, query, query
            )
        ).limit(top_k).execute()

        append_results(resp, "file",
                       ["name", "path", "summary", "owner_email", "owner_name"])
    except Exception as e:
        log_error(f"Error in fuzzy file search: {e}")

    # ATTACHMENTS
    try:
        resp = supabase.table("attachments").select(
            "id, email_id, filename, summary"
        ).eq("user_id", user_id).or_(
            "filename.ilike.%{}%,summary.ilike.%{}%".format(query, query)
        ).limit(top_k).execute()

        append_results(resp, "attachment",
                       ["filename", "summary"], id_field="id")
    except Exception as e:
        log_error(f"Error in fuzzy attachment search: {e}")

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    return results[:top_k]
