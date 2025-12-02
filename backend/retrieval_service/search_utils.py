"""
Search utilities combining vector search, keyword search, and fuzzy search
"""

from retrieval_service.supabase_utils import supabase
from retrieval_service.gemni_api_utils import embed_text
from typing import List, Dict, Tuple, Any
import os
from dotenv import load_dotenv
from rapidfuzz import fuzz
import traceback


load_dotenv()

DEFAULT_TOP_K = int(os.getenv("SEARCH_TOP_K", "5"))


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
            print(f"Error in vector search for {search_type}: {e}")

    return results


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
        print(f"Error in keyword search for emails: {e}")

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
        print(f"Error in keyword search for schedules: {e}")

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
        print(f"Error in keyword search for files: {e}")

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
        print(f"Error in keyword search for attachments: {e}")

    return results


def fuzzy_search(
    user_id: str,
    query: str,
    top_k: int = 10
) -> List[Dict]:
    """
    FULL fuzzy search across emails, schedules, files, attachments.
    Covers ALL relevant text fields.
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
        print("Error in fuzzy email search:", e)

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
        print("Error in fuzzy schedule search:", e)

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
        print("Error in fuzzy file search:", e)

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
        print("Error in fuzzy attachment search:", e)

    results = sorted(results, key=lambda x: x["score"], reverse=True)

    return results[:top_k]


def get_context_from_results(
    user_id: str,
    search_results: List[Dict]
) -> Tuple[str, List[Dict]]:
    """
    Fetch full content from search results and format as context.
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
                if response.data:
                    email = response.data[0]
                    context_parts.append(
                        f"[Email] From: {email.get('from_user', 'unknown')}, "
                        f"To: {email.get('to_user', 'unknown')}\n"
                        f"CC: {email.get('cc', '')}, BCC: {email.get('bcc', '')}\n"
                        f"Email ID: {email.get('id', 'unknown')}\n"
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
                if response.data:
                    schedule = response.data[0]
                    context_parts.append(
                        f"[Calendar Event] {schedule.get('summary', 'No title')}\n"
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
                if response.data:
                    file = response.data[0]
                    context_parts.append(
                        f"[File] {file.get('name', 'unknown')}\n"
                        f"ID: {file.get('id', 'unknown')}\n"
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
                if response.data:
                    attachment = response.data[0]
                    email_id = attachment.get('email_id', 'unknown')

                    email_info = None
                    try:
                        email_response = supabase.table('emails').select('*')\
                            .eq('user_id', user_id).eq('id', email_id).execute()
                        if email_response.data:
                            email_info = email_response.data[0]
                    except Exception as e:
                        print(f"Error fetching email info for attachment {result_id}: {e}")

                    context_text = (
                        f"[Email Attachment] {attachment.get('filename', 'unknown')}\n"
                        f"ID: {attachment.get('id', 'unknown')}\n"
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
            print(f"Error fetching {result_type} {result_id}: {e}")

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

    NOTE:
        - All search functions must already be imported from your code above.
        - embedding API (embed_text) is also imported.
    """

    try:
        # ----------------------------------------------------
        # 1) Parse arguments
        # ----------------------------------------------------
        query: str = arguments.get("query", "")
        keywords: List[str] = arguments.get("keywords", [])
        search_types: List[str] = arguments.get("search_types", None)
        top_k: int = int(arguments.get("top_k", 10))

        # ----------------------------------------------------
        # 2) Route by tool name
        # ----------------------------------------------------
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

        # ----------------------------------------------------
        # 3) Expand context & references
        # ----------------------------------------------------
        context, references = get_context_from_results(user_id, raw_results)

        # ----------------------------------------------------
        # 4) Return to LLM
        # ----------------------------------------------------
        return {
            "ok": True,
            "results": raw_results,
            "context": context,
            "references": references,
            "raw_results": raw_results  # optional: give model raw items
        }

    except Exception as e:
        traceback.print_exc()
        return {
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
