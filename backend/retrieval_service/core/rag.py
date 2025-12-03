"""
RAG (Retrieval-Augmented Generation) utilities.

This module provides the core RAG retrieval functionality, including combined search
across multiple strategies (semantic, keyword, fuzzy) and prompt building for
context extraction.
"""

from typing import Dict, List, Tuple
from retrieval_service.search import (
    vector_search,
    keyword_search,
    fuzzy_search,
    get_context_from_results
)
from retrieval_service.api.gemini_client import embed_text
from retrieval_service.infrastructure.logging import log_debug, log_info, log_error
import os

DEFAULT_TOP_K = int(os.getenv("SEARCH_TOP_K", "5"))


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
            log_info(f"[RAG] Performing semantic search for: {query}")
            embedding = embed_text(query)
            semantic_results = vector_search(
                user_id=user_id,
                query_embedding=embedding,
                search_types=None,  # Search all types
                top_k=top_k
            )
            all_results.extend(semantic_results)
            log_info(f"[RAG] Semantic search found {len(semantic_results)} results")
        except Exception as e:
            log_error(f"[RAG] Error in semantic search: {e}")
    
    # 2. Keyword Search (best for exact words/names)
    if use_keyword:
        try:
            log_info(f"[RAG] Performing keyword search for: {query}")
            # Extract keywords from query (simple word splitting)
            keywords = [word for word in query.split() if len(word) > 2]
            if keywords:
                keyword_results = keyword_search(
                    user_id=user_id,
                    keywords=keywords,
                    top_k=top_k
                )
                all_results.extend(keyword_results)
                log_info(f"[RAG] Keyword search found {len(keyword_results)} results")
        except Exception as e:
            log_error(f"[RAG] Error in keyword search: {e}")
    
    # 3. Fuzzy Search (best for approximate matches)
    if use_fuzzy:
        try:
            log_info(f"[RAG] Performing fuzzy search for: {query}")
            fuzzy_results = fuzzy_search(
                user_id=user_id,
                query=query,
                top_k=top_k
            )
            all_results.extend(fuzzy_results)
            log_info(f"[RAG] Fuzzy search found {len(fuzzy_results)} results")
        except Exception as e:
            log_error(f"[RAG] Error in fuzzy search: {e}")
    
    # Deduplicate and sort by score
    unique_results = deduplicate_results(all_results)
    sorted_results = sorted(unique_results, key=lambda x: x['score'], reverse=True)
    
    # Limit to top_k total results
    final_results = sorted_results[:top_k * 2]  # Allow more results for better context
    
    log_info(f"[RAG] Total unique results: {len(final_results)}")
    
    # Get full context and references
    context, references = get_context_from_results(user_id, final_results)
    
    return context, references, final_results


def build_rag_prompt(query: str, context: str, user_info: dict, raw_results: List[Dict] = None) -> str:
    """
    Build a prompt for memory retrieval with raw result IDs.
    
    Args:
        query: User's search query
        context: Retrieved context from search
        user_info: User information from Google OAuth
        raw_results: Raw search results with IDs
    
    Returns:
        Formatted prompt for context extraction
    """
    if not context or context.strip() == "":
        return f"""Query: {query}

No data retrieved from user's personal records.

Output (third-person perspective):
No relevant information exists in user's personal data.
REFERENCE_IDS: none"""
    
    # Build a list of available sources with IDs
    sources_list = []
    if raw_results:
        for i, result in enumerate(raw_results[:10], 1):  # Limit to top 10
            result_type = result.get('type', 'unknown')
            result_id = result.get('id', 'unknown')
            score = result.get('score', 0)
            sources_list.append(f"[{result_type}_{result_id}] (score: {score:.2f})")
    
    sources_text = "\n".join(sources_list) if sources_list else "No sources available"
    
    return f"""Query: {query}

Available sources (with IDs):
{sources_text}

Retrieved information from user's data:
{context}

Extract a SHORT factual summary (max 3-4 sentences or bullet points) in THIRD-PERSON perspective. Use "they/them" as the pronoun to avoid pronoun issues.
You only provides context for other LLMs to answer, your response is for LLMs

Use phrases like:
- "User has [X] emails about..."
- "Data contains meeting scheduled for..."
- "Records show deadline of..."
- "Calendar includes event on..."

Do NOT use:
- "I found..."
- "I see..."
- "Here's what..."
- "Let me..."

Then list REFERENCE_IDS of sources used in your summary.
"""


RAG_SYSTEM_PROMPT = (
    f"You are a memory retrieval module that extracts factual context from user data.\n"
    f"CRITICAL INSTRUCTIONS:\n"
    f"1. Write in THIRD-PERSON perspective (describe what exists in the data)\n"
    f"2. Do NOT use first-person ('I found', 'I see') - use third-person ('User has', 'Data contains', 'Records show')\n"
    f"3. Keep responses SHORT - maximum 3-4 sentences or bullet points\n"
    f"4. Extract ONLY factual information, no opinions or advice\n"
    f"5. Focus on: dates, people, actions, deadlines, key facts\n"
    f"6. If no relevant data exists, state it objectively\n\n"
    f"OUTPUT FORMAT:\n"
    f"First line: Objective summary of what data exists\n"
    f"Following lines: Key facts in bullet points (if multiple)\n"
    f"Last line: REFERENCE_IDS: [comma-separated list of source IDs]\n\n"
    f"CORRECT EXAMPLES:\n"
    f"✓ 'User has 2 emails about project deadline from Sarah.'\n"
    f"✓ 'Data contains meeting scheduled for Dec 5, 2PM.'\n"
    f"✓ 'Records show budget proposal due Dec 3.'\n"
    f"✓ 'No relevant information exists in user data.'\n\n"
    f"INCORRECT EXAMPLES:\n"
    f"✗ 'I found 2 emails about project deadline.'\n"
    f"✗ 'I see you have a meeting on Dec 5.'\n"
    f"✗ 'Let me help you with that.'\n"
    f"✗ 'Here's what I discovered...'\n\n"
    f"Example output:\n"
    f"User has 2 emails about project deadline from Sarah.\n"
    f"- Meeting scheduled Dec 5, 2PM with Sarah\n"
    f"- Budget proposal due Dec 3\n"
    f"REFERENCE_IDS: email_123, email_456, event_789\n\n"
    f"If no data found:\n"
    f"No relevant information exists in user's personal data.\n"
    f"REFERENCE_IDS: none\n"
    f"Format:"
    f"[Objective summary in third-person]"
    f"REFERENCE_IDS: [comma-separated IDs like: email_123, schedule_456, file_789] (raw id without 'email_' 'file_'...)"
    f"Only include IDs directly relevant to your summary."
)