from typing import Dict, List, Tuple
from retrieval_service.search_utils import (
    vector_search,
    keyword_search,
    fuzzy_search,
    get_context_from_results,
    DEFAULT_TOP_K
)
from retrieval_service.gemni_api_utils import embed_text


def deduplicate_results(results: List[Dict]) -> List[Dict]:
    """
    Deduplicate search results based on type and id.
    Keeps the result with the highest score for each unique (type, id) pair.
    """
    seen = {}
    for result in results:
        key = (result['type'], result['id'])
        if key not in seen or result['score'] > seen[key]['score']:
            seen[key] = result
    
    return list(seen.values())


def combined_search(
    user_id: str,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    use_semantic: bool = True,
    use_keyword: bool = True,
    use_fuzzy: bool = True
) -> Tuple[str, List[Dict], List[Dict]]:
    """
    Perform a combined search using multiple search strategies.
    This is the core RAG retrieval function that doesn't rely on agent reasoning.
    
    Args:
        user_id: User UUID
        query: Natural language search query
        top_k: Number of results to return per search method
        use_semantic: Whether to use semantic/vector search
        use_keyword: Whether to use keyword search
        use_fuzzy: Whether to use fuzzy search
    
    Returns:
        Tuple of (context_string, references, raw_results)
    """
    all_results = []
    
    # 1. Semantic/Vector Search (best for meaning-based queries)
    if use_semantic:
        try:
            print(f"[RAG] Performing semantic search for: {query}")
            embedding = embed_text(query)
            semantic_results = vector_search(
                user_id=user_id,
                query_embedding=embedding,
                search_types=None,  # Search all types
                top_k=top_k
            )
            all_results.extend(semantic_results)
            print(f"[RAG] Semantic search found {len(semantic_results)} results")
        except Exception as e:
            print(f"[RAG] Error in semantic search: {e}")
    
    # 2. Keyword Search (best for exact words/names)
    if use_keyword:
        try:
            print(f"[RAG] Performing keyword search for: {query}")
            # Extract keywords from query (simple word splitting)
            keywords = [word for word in query.split() if len(word) > 2]
            if keywords:
                keyword_results = keyword_search(
                    user_id=user_id,
                    keywords=keywords,
                    top_k=top_k
                )
                all_results.extend(keyword_results)
                print(f"[RAG] Keyword search found {len(keyword_results)} results")
        except Exception as e:
            print(f"[RAG] Error in keyword search: {e}")
    
    # 3. Fuzzy Search (best for approximate matches)
    if use_fuzzy:
        try:
            print(f"[RAG] Performing fuzzy search for: {query}")
            fuzzy_results = fuzzy_search(
                user_id=user_id,
                query=query,
                top_k=top_k
            )
            all_results.extend(fuzzy_results)
            print(f"[RAG] Fuzzy search found {len(fuzzy_results)} results")
        except Exception as e:
            print(f"[RAG] Error in fuzzy search: {e}")
    
    # Deduplicate and sort by score
    unique_results = deduplicate_results(all_results)
    sorted_results = sorted(unique_results, key=lambda x: x['score'], reverse=True)
    
    # Limit to top_k total results
    final_results = sorted_results[:top_k * 2]  # Allow more results for better context
    
    print(f"[RAG] Total unique results: {len(final_results)}")
    
    # Get full context and references
    context, references = get_context_from_results(user_id, final_results)
    
    return context, references, final_results


def build_rag_prompt(user_message: str, context: str, user_info: dict) -> str:
    """
    Build a prompt for RAG mode that includes the retrieved context.
    
    Args:
        user_message: User's question/message
        context: Retrieved context from search
        user_info: User information from Google OAuth
    
    Returns:
        Formatted prompt with context
    """
    if not context or context.strip() == "":
        return f"""You are a helpful assistant with access to the user's personal data.

The user asked: {user_message}

Unfortunately, I couldn't find any relevant information in your personal data to answer this question. This could mean:
1. The information doesn't exist in your emails, calendar, or files
2. The question doesn't require personal data (general knowledge question)

Please answer the user's question to the best of your ability. If it's a general knowledge question, answer it directly. If it requires personal data that wasn't found, let them know politely.

User info (for reference): {user_info.get('email', 'unknown')}"""
    
    return f"""You are a helpful assistant analyzing the user's personal data.

The user asked: {user_message}

Here is the relevant information I found from your emails, calendar events, and files:

{context}

Please answer the user's question based on this information. Be specific and cite which sources you're using (e.g., "According to the email from...", "Based on your calendar event...", etc.).

If the context doesn't fully answer the question, acknowledge what you know and what you don't know.

User info (for reference): {user_info.get('email', 'unknown')}"""
