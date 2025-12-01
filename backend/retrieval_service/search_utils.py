"""
Search utilities combining vector search, keyword search, and fuzzy search
"""
from retrieval_service.supabase_utils import supabase
from retrieval_service.gemni_api_utils import embed_text
from typing import List, Dict, Tuple


def vector_search(user_id: str, query_embedding: List[float], search_types: List[str] = None, top_k: int = 10) -> List[Dict]:
    """
    Perform vector search using Supabase RPC functions.
    
    Args:
        user_id: User UUID
        query_embedding: Query embedding vector
        search_types: List of types to search ('email_context', 'schedule_context', 'file_context')
        top_k: Number of results per type
    
    Returns:
        List of search results with scores
    """
    if search_types is None:
        search_types = ['email_context', 'schedule_context', 'file_context']
    
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
        
        except Exception as e:
            print(f"Error in vector search for {search_type}: {e}")
    
    return results


def keyword_search(user_id: str, keywords: List[str], top_k: int = 10) -> List[Dict]:
    """
    Perform keyword search across emails, schedules, and files.
    
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
    
    return results


def fuzzy_search(user_id: str, query: str, top_k: int = 10) -> List[Dict]:
    """
    Perform fuzzy text search using ILIKE with wildcards.
    Note: Full-text search is not supported in Supabase Python client,
    so we use ILIKE for fuzzy matching instead.
    
    Args:
        user_id: User UUID
        query: Search query
        top_k: Max results per type
    
    Returns:
        List of search results with scores
    """
    results = []
    
    # Search emails with fuzzy matching using ILIKE
    try:
        response = supabase.table('emails').select('id, subject, body').eq('user_id', user_id).ilike(
            'subject', f'%{query}%'
        ).limit(top_k).execute()
        
        for item in response.data:
            results.append({
                'type': 'email',
                'id': item['id'],
                'score': 0.4,  # Fixed score for fuzzy matches
                'source': 'fuzzy'
            })
    except Exception as e:
        print(f"Error in fuzzy search for emails: {e}")
    
    # Search schedules
    try:
        response = supabase.table('schedules').select('id, summary, description').eq('user_id', user_id).ilike(
            'summary', f'%{query}%'
        ).limit(top_k).execute()
        
        for item in response.data:
            results.append({
                'type': 'schedule',
                'id': item['id'],
                'score': 0.4,
                'source': 'fuzzy'
            })
    except Exception as e:
        print(f"Error in fuzzy search for schedules: {e}")
    
    # Search files
    try:
        response = supabase.table('files').select('id, name, summary').eq('user_id', user_id).ilike(
            'name', f'%{query}%'
        ).limit(top_k).execute()
        
        for item in response.data:
            results.append({
                'type': 'file',
                'id': item['id'],
                'score': 0.4,
                'source': 'fuzzy'
            })
    except Exception as e:
        print(f"Error in fuzzy search for files: {e}")
    
    return results


def combined_search(user_id: str, query: str, keywords: List[str] = None, 
                   vector_weight: float = 0.6, keyword_weight: float = 0.3, 
                   fuzzy_weight: float = 0.1, top_k: int = 10) -> List[Dict]:
    """
    Perform combined search using vector, keyword, and fuzzy search.
    
    Args:
        user_id: User UUID
        query: Search query text
        keywords: Optional keywords to search (extracted from query if not provided)
        vector_weight: Weight for vector search results
        keyword_weight: Weight for keyword search results
        fuzzy_weight: Weight for fuzzy search results
        top_k: Number of final results to return
    
    Returns:
        List of top-k search results with references
    """
    # Generate embedding for vector search
    query_embedding = embed_text(query)
    
    # Perform vector search
    vector_results = vector_search(user_id, query_embedding, top_k=top_k)
    
    # Extract keywords if not provided
    if keywords is None:
        # Simple keyword extraction (split by space, remove common words)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        keywords = [w for w in query.lower().split() if w not in stop_words and len(w) > 2]
    
    # Perform keyword search
    keyword_results = keyword_search(user_id, keywords, top_k=top_k) if keywords else []
    
    # Perform fuzzy search
    fuzzy_results = fuzzy_search(user_id, query, top_k=top_k)
    
    # Combine results with weights
    combined_scores = {}
    
    for result in vector_results:
        key = (result['type'], result['id'])
        if key not in combined_scores:
            combined_scores[key] = {'type': result['type'], 'id': result['id'], 'score': 0.0, 'sources': []}
        combined_scores[key]['score'] += result['score'] * vector_weight
        combined_scores[key]['sources'].append('vector')
    
    for result in keyword_results:
        key = (result['type'], result['id'])
        if key not in combined_scores:
            combined_scores[key] = {'type': result['type'], 'id': result['id'], 'score': 0.0, 'sources': []}
        combined_scores[key]['score'] += result['score'] * keyword_weight
        combined_scores[key]['sources'].append('keyword')
    
    for result in fuzzy_results:
        key = (result['type'], result['id'])
        if key not in combined_scores:
            combined_scores[key] = {'type': result['type'], 'id': result['id'], 'score': 0.0, 'sources': []}
        combined_scores[key]['score'] += result['score'] * fuzzy_weight
        combined_scores[key]['sources'].append('fuzzy')
    
    # Sort by score and get top-k
    sorted_results = sorted(combined_scores.values(), key=lambda x: x['score'], reverse=True)[:top_k]
    
    return sorted_results


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
                        f"[Email] From: {email.get('from_user', 'unknown')}, "
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
        
        except Exception as e:
            print(f"Error fetching {result_type} {result_id}: {e}")
    
    context_str = "\n---\n".join(context_parts)
    return context_str, references
