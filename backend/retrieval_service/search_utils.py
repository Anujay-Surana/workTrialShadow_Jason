"""
Search utilities combining vector search, keyword search, and fuzzy search
"""
from retrieval_service.supabase_utils import supabase
from retrieval_service.gemni_api_utils import embed_text
from typing import List, Dict, Tuple
import os
from dotenv import load_dotenv
from rapidfuzz import fuzz 

load_dotenv()

# Get top-k from environment variable, default to 5
DEFAULT_TOP_K = int(os.getenv("SEARCH_TOP_K", "5"))


def vector_search(user_id: str, query_embedding: List[float], search_types: List[str] = None, top_k: int = 10) -> List[Dict]:
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
        search_types = ['email_context', 'schedule_context', 'file_context', 'attachment_context']
    
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


def keyword_search(user_id: str, keywords: List[str], top_k: int = 10) -> List[Dict]:
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
            # Search in subject and body using proper PostgREST OR syntax
            # Use filter() instead of or_() to avoid syntax issues
            response = supabase.table('emails').select('id, subject, body').eq('user_id', user_id).filter(
                'subject', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()
            
            # Also search in body
            response2 = supabase.table('emails').select('id, subject, body').eq('user_id', user_id).filter(
                'body', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()
            
            # Combine results
            combined_data = response.data + response2.data
            # Remove duplicates based on id
            seen_ids = set()
            unique_data = []
            for item in combined_data:
                if item['id'] not in seen_ids:
                    seen_ids.add(item['id'])
                    unique_data.append(item)
            
            response.data = unique_data[:top_k]
            
            for item in response.data:
                # Simple scoring based on keyword matches
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
            # Search in summary
            response = supabase.table('schedules').select('id, summary, description').eq('user_id', user_id).filter(
                'summary', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()
            
            # Also search in description
            response2 = supabase.table('schedules').select('id, summary, description').eq('user_id', user_id).filter(
                'description', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()
            
            # Combine and deduplicate
            combined_data = response.data + response2.data
            seen_ids = set()
            unique_data = []
            for item in combined_data:
                if item['id'] not in seen_ids:
                    seen_ids.add(item['id'])
                    unique_data.append(item)
            
            response.data = unique_data[:top_k]
            
            for item in response.data:
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
            # Search in name
            response = supabase.table('files').select('id, name, summary').eq('user_id', user_id).filter(
                'name', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()
            
            # Also search in summary
            response2 = supabase.table('files').select('id, name, summary').eq('user_id', user_id).filter(
                'summary', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()
            
            # Combine and deduplicate
            combined_data = response.data + response2.data
            seen_ids = set()
            unique_data = []
            for item in combined_data:
                if item['id'] not in seen_ids:
                    seen_ids.add(item['id'])
                    unique_data.append(item)
            
            response.data = unique_data[:top_k]
            
            for item in response.data:
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
            # Search in filename
            response = supabase.table('attachments').select('id, filename, summary').eq('user_id', user_id).filter(
                'filename', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()
            
            # Also search in summary
            response2 = supabase.table('attachments').select('id, filename, summary').eq('user_id', user_id).filter(
                'summary', 'ilike', f'%{keyword}%'
            ).limit(top_k).execute()
            
            # Combine and deduplicate
            combined_data = response.data + response2.data
            seen_ids = set()
            unique_data = []
            for item in combined_data:
                if item['id'] not in seen_ids:
                    seen_ids.add(item['id'])
                    unique_data.append(item)
            
            response.data = unique_data[:top_k]
            
            for item in response.data:
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


def fuzzy_search(user_id: str, query: str, top_k: int = 10) -> List[Dict]:
    """
    FULL fuzzy search across emails, schedules, files, attachments.
    Covers ALL relevant text fields.
    """
    results = []

    # Helper: Compute a similarity score from available fields
    def append_results(response, r_type, fields, id_field="id"):
        for item in response.data:
            merged_text = " ".join([(item.get(f) or "") for f in fields])
            score = fuzz.partial_ratio(query.lower(), merged_text.lower()) / 100.0
            results.append({
                "type": r_type,
                "id": item[id_field],
                "score": float(score),
                "source": "fuzzy"
            })

    # ======================================================
    # EMAILS
    # ======================================================
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

    # ======================================================
    # SCHEDULES
    # ======================================================
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

    # ======================================================
    # FILES
    # ======================================================
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

    # ======================================================
    # ATTACHMENTS
    # ======================================================
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

    # ======================================================
    # GLOBAL SORTING
    # ======================================================
    results = sorted(results, key=lambda x: x["score"], reverse=True)

    # Return top_k globally
    return results[:top_k]


def combined_search(
    user_id: str,
    query: str,
    keywords: List[str] = None,
    vector_weight: float = 0.6,
    keyword_weight: float = 0.4,
    fuzzy_weight: float = 0.6,
    top_k: int = None
) -> List[Dict]:

    if top_k is None:
        top_k = DEFAULT_TOP_K

    # Generate embedding for vector search
    query_embedding = embed_text(query)

    # Perform vector search
    vector_results = vector_search(user_id, query_embedding, top_k=top_k)

    # Extract keywords if not provided
    if keywords is None:
        stop_words = {
            # articles / determiners
            "a", "an", "the", "this", "that", "these", "those",

            # conjunctions
            "and", "or", "but", "so", "yet",

            # prepositions
            "in", "on", "at", "to", "for", "of", "with", "from", "into",
            "during", "including", "until", "against", "among", "throughout",
            "despite", "towards", "upon", "about", "above", "below", "under",
            "over", "between", "without", "within", "along", "across",

            # pronouns
            "i", "you", "he", "she", "it", "we", "they",
            "me", "him", "her", "them", "us",
            "my", "your", "his", "her", "its", "our", "their",
            "mine", "yours", "ours", "theirs",

            # auxiliary verbs
            "am", "is", "are", "was", "were",
            "be", "been", "being",
            "do", "does", "did",
            "have", "has", "had",

            # modal verbs
            "can", "could", "should", "would", "will", "shall",
            "may", "might", "must",

            # filler verbs that carry no meaning in search
            "find", "show", "give", "tell", "get", "look",
            "help", "let", "need", "want", "see",

            # WH fillers (not the meaningful ones like "where" or "who")
            "what", "how",

            # question/polite fillers
            "please", "thanks", "thank", "hi", "hello",
            "hey", "ok", "okay", "sure",

            # padding words
            "just", "really", "very", "quite", "maybe", "perhaps",
            "like", "kind", "sort", "thing", "stuff",
            "also", "still", "almost",

            # frequency/time fillers
            "today", "now", "then", "later",

            # others
            "myself", "yourself", "ourselves", "themselves",
            "any", "some", "all", "both", "each", "every",
            "few", "more", "most", "other", "same"
            
            # verbs like "is", "are", "was", "were" are already included above
            "is", "are", "was", "were", "find", "show", "give", "tell"
        }

        keywords = [
            w.replace("?","").replace(".","").replace(",","") for w in query.lower().split()
            if w not in stop_words and len(w) > 2
        ]

    # Perform keyword search
    keyword_results = keyword_search(user_id, keywords, top_k=top_k) if keywords else []
    print("keyword results:", keyword_results)

    # Perform fuzzy search
    fuzzy_results = fuzzy_search(user_id, query, top_k=top_k)

    # --- WEAK VECTOR BOOST ---
    weak_vectors = all(v['score'] < 0.5 for v in vector_results) if vector_results else True

    if weak_vectors:
        print("Vector search weak (<0.5): boosting keyword + fuzzy weights")
        vector_weight = 0.3
        keyword_weight = 0.4
        fuzzy_weight = 0.3

    # --- COMBINE SCORES ---
    combined_scores = {}

    def add_score(result, weight):
        key = (result['type'], result['id'])
        if key not in combined_scores:
            combined_scores[key] = {
                'type': result['type'],
                'id': result['id'],
                'score': 0.0,
                'sources': []
            }
        combined_scores[key]['score'] += result['score'] * weight
        combined_scores[key]['sources'].append(result['source'])

    for r in vector_results:
        add_score(r, vector_weight)
    for r in keyword_results:
        add_score(r, keyword_weight)
    for r in fuzzy_results:
        add_score(r, fuzzy_weight)

    # --- SORT ---
    sorted_results = sorted(
        combined_scores.values(),
        key=lambda x: x['score'],
        reverse=True
    )

    # -------------------------------
    #   ENSURE 1 KEYWORD + 1 FUZZY
    # -------------------------------

    keyword_included = any('keyword' in r['sources'] for r in sorted_results)
    fuzzy_included = any('fuzzy' in r['sources'] for r in sorted_results)

    # Insert keyword result if missing
    if not keyword_included and keyword_results:
        best_keyword = keyword_results[0]
        key = (best_keyword['type'], best_keyword['id'])
        forced_entry = combined_scores[key]
        print("Forcing best keyword result into list")
        sorted_results.append(forced_entry)

    # Insert fuzzy result if missing
    if not fuzzy_included and fuzzy_results:
        best_fuzzy = fuzzy_results[0]
        key = (best_fuzzy['type'], best_fuzzy['id'])
        forced_entry = combined_scores[key]
        print("Forcing best fuzzy result into list")
        sorted_results.append(forced_entry)

    # Deduplicate again after forced insertions
    seen = set()
    unique_sorted = []
    for r in sorted_results:
        key = (r['type'], r['id'])
        if key not in seen:
            seen.add(key)
            unique_sorted.append(r)

    # Final trim
    final_sorted = unique_sorted[:top_k]

    return final_sorted


def get_context_from_results(user_id: str, search_results: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Fetch full content from search results and format as context.
    
    Args:
        user_id: User UUID
        search_results: List of search results from combined_search
    
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
                response = supabase.table('emails').select('*').eq('user_id', user_id).eq('id', result_id).execute()
                if response.data:
                    email = response.data[0]
                    context_parts.append(
                        f"[Email] From: {email.get('from_user', 'unknown')}, To: {email.get('to_user', 'unknown')}\n, CC: {email.get('cc', '')}, BCC: {email.get('bcc', '')}\n"
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
                response = supabase.table('schedules').select('*').eq('user_id', user_id).eq('id', result_id).execute()
                if response.data:
                    schedule = response.data[0]
                    context_parts.append(
                        f"[Calendar Event] {schedule.get('summary', 'No title')}\n"
                        f"Description: {schedule.get('description', 'No description')}\n"
                        f"Location: {schedule.get('location', 'No location')}\n"
                        f"Time: {schedule.get('start_time', 'unknown')} to {schedule.get('end_time', 'unknown')}\n"
                    )
                    references.append({
                        'type': 'schedule',
                        'id': result_id,
                        'title': schedule.get('summary', 'No title'),
                        'start_time': schedule.get('start_time', 'unknown'),
                        'location': schedule.get('location', 'No location')
                    })
            
            elif result_type == 'file':
                response = supabase.table('files').select('*').eq('user_id', user_id).eq('id', result_id).execute()
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
                response = supabase.table('attachments').select('*').eq('user_id', user_id).eq('id', result_id).execute()
                if response.data:
                    attachment = response.data[0]
                    email_id = attachment.get('email_id', 'unknown')
                    
                    # Get email information for context
                    email_info = None
                    try:
                        email_response = supabase.table('emails').select('*').eq('user_id', user_id).eq('id', email_id).execute()
                        if email_response.data:
                            email_info = email_response.data[0]
                    except Exception as e:
                        print(f"Error fetching email info for attachment {result_id}: {e}")
                    
                    # Build context with email information
                    context_text = f"[Email Attachment] {attachment.get('filename', 'unknown')}\n"
                    context_text += f"ID: {attachment.get('id', 'unknown')}\n"
                    context_text += f"Type: {attachment.get('mime_type', 'unknown')}\n"
                    context_text += f"Size: {attachment.get('size', 'unknown')} bytes\n"
                    
                    if email_info:
                        context_text += f"From email sent by: {email_info.get('from_user', 'unknown')}\n"
                        context_text += f"To: {email_info.get('to_user', 'unknown')}\n"
                        if email_info.get('cc'):
                            context_text += f"CC: {email_info.get('cc')}\n"
                        if email_info.get('bcc'):
                            context_text += f"BCC: {email_info.get('bcc')}\n"
                        context_text += f"Email date: {email_info.get('date', 'unknown')}\n"
                        context_text += f"Email subject: {email_info.get('subject', 'No subject')}\n"
                    
                    context_text += f"Summary: {attachment.get('summary', 'No summary available')}\n"
                    context_parts.append(context_text)
                    
                    # Build reference with email information
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
