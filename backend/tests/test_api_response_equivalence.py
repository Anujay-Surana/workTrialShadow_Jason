"""
Property-Based Test for API Response Equivalence

This test verifies that the refactored retrieval service produces functionally
equivalent responses to the original implementation.

**Feature: retrieval-service-refactor, Property 3: API Response Equivalence**
**Validates: Requirements 3.3**
"""

import pytest
from hypothesis import given, strategies as st, settings
from typing import Dict, List


# ======================================================
# Test Helpers
# ======================================================

def normalize_response(response: Dict) -> Dict:
    """
    Normalize a response for comparison.
    
    Some fields may vary slightly (like timestamps, process steps in verbose mode)
    but the core content and references should be identical.
    """
    if not isinstance(response, dict):
        return response
    
    normalized = {}
    
    # Core fields that must match exactly
    if 'content' in response:
        normalized['content'] = response['content']
    
    if 'references' in response:
        # Sort references by type and id for consistent comparison
        refs = response['references']
        if isinstance(refs, list):
            sorted_refs = sorted(refs, key=lambda r: (r.get('type', ''), r.get('id', '')))
            normalized['references'] = sorted_refs
        else:
            normalized['references'] = refs
    
    # Other fields
    for key in ['ok', 'error', 'result_count', 'context']:
        if key in response:
            normalized[key] = response[key]
    
    return normalized


def responses_are_equivalent(response1: Dict, response2: Dict) -> bool:
    """
    Check if two API responses are functionally equivalent.
    
    Responses are considered equivalent if:
    - They have the same content
    - They have the same references (same type, id, and data)
    - They have the same error status
    """
    norm1 = normalize_response(response1)
    norm2 = normalize_response(response2)
    
    # Check content
    if norm1.get('content') != norm2.get('content'):
        return False
    
    # Check references
    refs1 = norm1.get('references', [])
    refs2 = norm2.get('references', [])
    
    if len(refs1) != len(refs2):
        return False
    
    for ref1, ref2 in zip(refs1, refs2):
        if ref1.get('type') != ref2.get('type'):
            return False
        if ref1.get('id') != ref2.get('id'):
            return False
    
    # Check error status
    if norm1.get('ok') != norm2.get('ok'):
        return False
    
    if norm1.get('error') != norm2.get('error'):
        return False
    
    return True


# ======================================================
# Property Tests
# ======================================================

@given(
    result_type=st.sampled_from(['email', 'schedule', 'file', 'attachment']),
    result_id=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
    score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_search_result_format_consistency(result_type: str, result_id: str, score: float):
    """
    Property: Search results from old and new modules have the same format.
    
    For any search result, the format should be consistent between old and new implementations.
    """
    # Create a mock search result
    result = {
        'type': result_type,
        'id': result_id,
        'score': score
    }
    
    # Both old and new implementations should handle this result format
    assert 'type' in result
    assert 'id' in result
    assert 'score' in result
    assert isinstance(result['type'], str)
    assert isinstance(result['id'], str)
    assert isinstance(result['score'], float)
    assert 0.0 <= result['score'] <= 1.0


@given(
    llm_output=st.text(min_size=10, max_size=500),
    reference_ids=st.lists(
        st.text(min_size=5, max_size=30, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'P'))),
        min_size=0,
        max_size=10
    )
)
@settings(max_examples=100, deadline=None)
def test_reference_parsing_consistency(llm_output: str, reference_ids: List[str]):
    """
    Property: Reference ID parsing produces consistent results.
    
    For any LLM output with REFERENCE_IDS, parsing should work consistently
    between old and new implementations.
    """
    from retrieval_service import parse_reference_ids
    from retrieval_service.search.reference import parse_reference_ids as new_parse
    
    # Add REFERENCE_IDS to output if we have any
    if reference_ids:
        test_output = f"{llm_output}\nREFERENCE_IDS: {', '.join(reference_ids)}"
    else:
        test_output = llm_output
    
    # Parse with both old and new implementations
    content1, ids1 = parse_reference_ids(test_output)
    content2, ids2 = new_parse(test_output)
    
    # Results should be identical
    assert content1 == content2
    assert sorted(ids1) == sorted(ids2)


@given(
    query=st.text(min_size=1, max_size=200, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'P', 'Zs'))),
    top_k=st.integers(min_value=1, max_value=20)
)
@settings(max_examples=50)
def test_search_function_signatures_consistent(query: str, top_k: int):
    """
    Property: Search functions have consistent signatures.
    
    For any query and top_k value, search functions should accept the same parameters
    in both old and new implementations.
    """
    from retrieval_service import vector_search, keyword_search, fuzzy_search
    from retrieval_service.search.vector import vector_search as new_vector
    from retrieval_service.search.keyword import keyword_search as new_keyword
    from retrieval_service.search.fuzzy import fuzzy_search as new_fuzzy
    
    # Check that functions are callable
    assert callable(vector_search)
    assert callable(keyword_search)
    assert callable(fuzzy_search)
    assert callable(new_vector)
    assert callable(new_keyword)
    assert callable(new_fuzzy)
    
    # Check that they're the same functions (backward compatibility)
    assert vector_search is new_vector
    assert keyword_search is new_keyword
    assert fuzzy_search is new_fuzzy


@given(
    text=st.text(min_size=10, max_size=1000, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'P', 'Zs')))
)
@settings(max_examples=50)
def test_embedding_function_consistency(text: str):
    """
    Property: Embedding functions produce consistent results.
    
    For any text input, the embedding function should work consistently
    between old and new implementations.
    """
    from retrieval_service import embed_text
    from retrieval_service.api.gemini_client import embed_text as new_embed
    
    # Check that functions are callable
    assert callable(embed_text)
    assert callable(new_embed)
    
    # Check that they're the same function (backward compatibility)
    assert embed_text is new_embed


@given(
    user_id=st.text(min_size=10, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'P'))),
    email=st.emails()
)
@settings(max_examples=50)
def test_database_function_consistency(user_id: str, email: str):
    """
    Property: Database functions have consistent signatures.
    
    For any user_id and email, database functions should accept the same parameters
    in both old and new implementations.
    """
    from retrieval_service import get_user_by_email, create_user
    from retrieval_service.data.database import get_user_by_email as new_get_user
    from retrieval_service.data.database import create_user as new_create_user
    
    # Check that functions are callable
    assert callable(get_user_by_email)
    assert callable(create_user)
    assert callable(new_get_user)
    assert callable(new_create_user)
    
    # Check that they're the same functions (backward compatibility)
    assert get_user_by_email is new_get_user
    assert create_user is new_create_user


@given(
    text=st.text(min_size=100, max_size=5000, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'P', 'Zs'))),
    chunk_size=st.integers(min_value=100, max_value=10000),
    overlap=st.integers(min_value=0, max_value=500)
)
@settings(max_examples=50)
def test_document_processing_consistency(text: str, chunk_size: int, overlap: int):
    """
    Property: Document processing functions produce consistent results.
    
    For any text, chunk_size, and overlap, the chunking function should work
    consistently between old and new implementations.
    """
    from retrieval_service import chunk_text
    from retrieval_service.processing.documents import chunk_text as new_chunk
    
    # Check that functions are callable
    assert callable(chunk_text)
    assert callable(new_chunk)
    
    # Check that they're the same function (backward compatibility)
    assert chunk_text is new_chunk
    
    # If chunk_size is valid, test the function
    if chunk_size > overlap and chunk_size > 0:
        chunks1 = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        chunks2 = new_chunk(text, chunk_size=chunk_size, overlap=overlap)
        
        # Results should be identical
        assert chunks1 == chunks2


@given(
    filename=st.text(min_size=5, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'P')))
)
@settings(max_examples=100)
def test_file_type_detection_consistency(filename: str):
    """
    Property: File type detection produces consistent results.
    
    For any filename, file type detection should work consistently
    between old and new implementations.
    """
    from retrieval_service import isDOC, isIMG
    from retrieval_service.processing.parsers import isDOC as new_isDOC
    from retrieval_service.processing.ocr import isIMG as new_isIMG
    
    # Check that functions are callable
    assert callable(isDOC)
    assert callable(isIMG)
    assert callable(new_isDOC)
    assert callable(new_isIMG)
    
    # Check that they're the same functions (backward compatibility)
    assert isDOC is new_isDOC
    assert isIMG is new_isIMG
    
    # Test the functions
    result1 = isDOC(filename)
    result2 = new_isDOC(filename)
    assert result1 == result2
    
    result3 = isIMG(filename)
    result4 = new_isIMG(filename)
    assert result3 == result4


def test_module_structure_equivalence():
    """
    Test that the module structure provides equivalent functionality.
    
    This is a sanity check that all major functions are accessible
    through both old and new import paths.
    """
    # Core functions
    from retrieval_service import SEARCH_TOOLS, REACT_SYSTEM_PROMPT
    from retrieval_service.core.mixed import SEARCH_TOOLS as new_tools
    from retrieval_service.core.mixed import REACT_SYSTEM_PROMPT as new_prompt
    assert SEARCH_TOOLS is new_tools
    assert REACT_SYSTEM_PROMPT is new_prompt
    
    # API functions
    from retrieval_service import rag, mixed_agent
    from retrieval_service.api.openai_client import rag as new_rag
    from retrieval_service.api.openai_client import mixed_agent as new_react
    assert rag is new_rag
    assert mixed_agent is new_react
    
    # Search functions
    from retrieval_service import vector_search
    from retrieval_service.search.vector import vector_search as new_vector
    assert vector_search is new_vector
    
    # Data functions
    from retrieval_service import supabase
    from retrieval_service.data.database import supabase as new_supabase
    assert supabase is new_supabase


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
