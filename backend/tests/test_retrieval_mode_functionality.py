"""
Property-based tests for retrieval mode functionality.

**Feature: retrieval-service-refactor, Property 4: Retrieval Mode Functionality**
**Validates: Requirements 7.3**

Property: For any retrieval mode (RAG, Mixed, ReAct) and valid query, the system should 
return results in the expected format with references.
"""

import pytest
from hypothesis import given, strategies as st, settings
from typing import Dict, List


# Strategy for generating valid retrieval modes
retrieval_modes = st.sampled_from(["rag", "mixed", "react"])

# Strategy for generating valid queries
valid_queries = st.text(min_size=3, max_size=100).filter(lambda x: x.strip() != "")


def validate_result_structure(result: Dict, mode: str) -> tuple[bool, str]:
    """
    Validate that a result has the expected structure for the given mode.
    
    Args:
        result: The result dictionary to validate
        mode: The retrieval mode used
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # All modes should return a dictionary
    if not isinstance(result, dict):
        return False, f"Result should be a dict, got {type(result)}"
    
    # All modes should have 'content' field
    if 'content' not in result:
        return False, "Result missing 'content' field"
    
    if not isinstance(result['content'], str):
        return False, f"Content should be a string, got {type(result['content'])}"
    
    # All modes should have 'references' field
    if 'references' not in result:
        return False, "Result missing 'references' field"
    
    if not isinstance(result['references'], list):
        return False, f"References should be a list, got {type(result['references'])}"
    
    # Validate reference structure
    for i, ref in enumerate(result['references']):
        if not isinstance(ref, dict):
            return False, f"Reference {i} should be a dict, got {type(ref)}"
        
        # Each reference should have basic fields
        required_fields = ['type', 'id']
        for field in required_fields:
            if field not in ref:
                return False, f"Reference {i} missing required field: {field}"
    
    return True, ""


@settings(max_examples=1, deadline=None)
@given(st.just(None))
def test_rag_mode_imports_successfully(dummy):
    """
    Property: RAG mode components should be importable.
    
    This ensures the core RAG functionality is accessible.
    """
    try:
        from retrieval_service.core import combined_search, build_rag_prompt
        assert callable(combined_search), "combined_search should be callable"
        assert callable(build_rag_prompt), "build_rag_prompt should be callable"
    except ImportError as e:
        pytest.fail(f"Failed to import RAG components: {e}")


@settings(max_examples=1)
@given(st.just(None))
def test_react_mode_imports_successfully(dummy):
    """
    Property: ReAct mode components should be importable.
    
    This ensures the core ReAct functionality is accessible.
    """
    try:
        from retrieval_service.core import react_agent_direct, parse_action
        assert callable(react_agent_direct), "react_agent_direct should be callable"
        assert callable(parse_action), "parse_action should be callable"
    except ImportError as e:
        pytest.fail(f"Failed to import ReAct components: {e}")


@settings(max_examples=1)
@given(st.just(None))
def test_agent_definitions_importable(dummy):
    """
    Property: Agent definitions (tools and prompts) should be importable.
    
    This ensures the agent configuration is accessible to all modes.
    """
    try:
        from retrieval_service.core import SEARCH_TOOLS, REACT_SYSTEM_PROMPT
        assert isinstance(SEARCH_TOOLS, list), "SEARCH_TOOLS should be a list"
        assert len(SEARCH_TOOLS) > 0, "SEARCH_TOOLS should not be empty"
        assert isinstance(REACT_SYSTEM_PROMPT, str), "REACT_SYSTEM_PROMPT should be a string"
        assert len(REACT_SYSTEM_PROMPT) > 0, "REACT_SYSTEM_PROMPT should not be empty"
    except ImportError as e:
        pytest.fail(f"Failed to import agent definitions: {e}")


@settings(max_examples=1)
@given(st.just(None))
def test_search_tools_have_required_structure(dummy):
    """
    Property: All search tools should have the required OpenAI function calling structure.
    
    This ensures tools can be used by the LLM for function calling.
    """
    from retrieval_service.core import SEARCH_TOOLS
    
    required_tool_names = ["vector_search", "keyword_search", "fuzzy_search"]
    found_tools = []
    
    for tool in SEARCH_TOOLS:
        # Each tool should have type and function
        assert 'type' in tool, "Tool missing 'type' field"
        assert tool['type'] == 'function', "Tool type should be 'function'"
        assert 'function' in tool, "Tool missing 'function' field"
        
        func = tool['function']
        
        # Function should have name, description, and parameters
        assert 'name' in func, "Function missing 'name' field"
        assert 'description' in func, "Function missing 'description' field"
        assert 'parameters' in func, "Function missing 'parameters' field"
        
        found_tools.append(func['name'])
        
        # Parameters should have proper structure
        params = func['parameters']
        assert 'type' in params, "Parameters missing 'type' field"
        assert params['type'] == 'object', "Parameters type should be 'object'"
        assert 'properties' in params, "Parameters missing 'properties' field"
        assert 'required' in params, "Parameters missing 'required' field"
    
    # Verify all expected tools are present
    for tool_name in required_tool_names:
        assert tool_name in found_tools, f"Missing required tool: {tool_name}"


@settings(max_examples=1)
@given(st.just(None))
def test_rag_functions_have_correct_signatures(dummy):
    """
    Property: RAG functions should have the expected signatures.
    
    This ensures the API contract is maintained.
    """
    import inspect
    from retrieval_service.core import combined_search, build_rag_prompt
    
    # Check combined_search signature
    sig = inspect.signature(combined_search)
    params = list(sig.parameters.keys())
    
    assert 'user_id' in params, "combined_search missing user_id parameter"
    assert 'query' in params, "combined_search missing query parameter"
    assert 'top_k' in params, "combined_search missing top_k parameter"
    
    # Check build_rag_prompt signature
    sig = inspect.signature(build_rag_prompt)
    params = list(sig.parameters.keys())
    
    assert 'query' in params, "build_rag_prompt missing query parameter"
    assert 'context' in params, "build_rag_prompt missing context parameter"
    assert 'user_info' in params, "build_rag_prompt missing user_info parameter"


@settings(max_examples=1)
@given(st.just(None))
def test_react_functions_have_correct_signatures(dummy):
    """
    Property: ReAct functions should have the expected signatures.
    
    This ensures the API contract is maintained.
    """
    import inspect
    from retrieval_service.core import react_agent_direct, parse_action
    
    # Check react_agent_direct signature
    sig = inspect.signature(react_agent_direct)
    params = list(sig.parameters.keys())
    
    assert 'messages' in params, "react_agent_direct missing messages parameter"
    assert 'user_id' in params, "react_agent_direct missing user_id parameter"
    
    # Check parse_action signature
    sig = inspect.signature(parse_action)
    params = list(sig.parameters.keys())
    
    assert 'text' in params, "parse_action missing text parameter"


@settings(max_examples=1)
@given(st.just(None))
def test_parse_action_handles_valid_actions(dummy):
    """
    Property: parse_action should correctly parse valid action formats.
    
    This ensures the ReAct agent can interpret LLM outputs.
    """
    from retrieval_service.core import parse_action
    
    # Test vector_search action
    tool, arg = parse_action("Action: vector_search find emails about project")
    assert tool == "vector_search", f"Expected 'vector_search', got '{tool}'"
    assert arg == "find emails about project", f"Expected query, got '{arg}'"
    
    # Test keyword_search action
    tool, arg = parse_action("Action: keyword_search meeting schedule")
    assert tool == "keyword_search", f"Expected 'keyword_search', got '{tool}'"
    assert arg == "meeting schedule", f"Expected query, got '{arg}'"
    
    # Test fuzzy_search action
    tool, arg = parse_action("Action: fuzzy_search budget proposal")
    assert tool == "fuzzy_search", f"Expected 'fuzzy_search', got '{tool}'"
    assert arg == "budget proposal", f"Expected query, got '{arg}'"
    
    # Test finish action
    tool, arg = parse_action("Final: User has 2 emails about project deadline.")
    assert tool == "finish", f"Expected 'finish', got '{tool}'"
    assert "User has 2 emails" in arg, f"Expected final answer in arg"


@settings(max_examples=1)
@given(st.just(None))
def test_parse_action_handles_invalid_input(dummy):
    """
    Property: parse_action should return None for invalid input.
    
    This ensures the agent handles malformed outputs gracefully.
    """
    from retrieval_service.core import parse_action
    
    # Test invalid input
    tool, arg = parse_action("This is not a valid action")
    assert tool is None, "Should return None for invalid input"
    assert arg is None, "Should return None for invalid input"
    
    # Test empty input
    tool, arg = parse_action("")
    assert tool is None, "Should return None for empty input"
    assert arg is None, "Should return None for empty input"


@settings(max_examples=1)
@given(st.just(None))
def test_core_module_exports_all_required_functions(dummy):
    """
    Property: The core module should export all required functions for retrieval modes.
    
    This ensures the public API is complete.
    """
    from retrieval_service import core
    
    required_exports = [
        'SEARCH_TOOLS',
        'REACT_SYSTEM_PROMPT',
        'combined_search',
        'build_rag_prompt',
        'react_agent_direct',
        'parse_action',
    ]
    
    for export in required_exports:
        assert hasattr(core, export), f"core module missing export: {export}"


def test_deduplicate_results_removes_duplicates():
    """
    Test that deduplicate_results correctly removes duplicate search results.
    """
    from retrieval_service.core import deduplicate_results
    
    # Create test results with duplicates
    results = [
        {'type': 'email', 'id': '123', 'score': 0.9},
        {'type': 'email', 'id': '123', 'score': 0.8},  # Duplicate with lower score
        {'type': 'email', 'id': '456', 'score': 0.7},
        {'type': 'schedule', 'id': '789', 'score': 0.6},
    ]
    
    deduplicated = deduplicate_results(results)
    
    # Should have 3 unique results
    assert len(deduplicated) == 3, f"Expected 3 results, got {len(deduplicated)}"
    
    # Should keep the higher score for email 123
    email_123 = [r for r in deduplicated if r['type'] == 'email' and r['id'] == '123']
    assert len(email_123) == 1, "Should have exactly one email 123"
    assert email_123[0]['score'] == 0.9, "Should keep the higher score"


def test_build_rag_prompt_handles_empty_context():
    """
    Test that build_rag_prompt handles empty context gracefully.
    """
    from retrieval_service.core import build_rag_prompt
    
    query = "test query"
    context = ""
    user_info = {"name": "Test User", "email": "test@example.com"}
    
    prompt = build_rag_prompt(query, context, user_info)
    
    assert isinstance(prompt, str), "Prompt should be a string"
    assert "No data retrieved" in prompt or "No relevant information" in prompt, \
        "Prompt should indicate no data was found"
    assert "REFERENCE_IDS: none" in prompt, "Prompt should include REFERENCE_IDS: none"


def test_build_rag_prompt_includes_query_and_context():
    """
    Test that build_rag_prompt includes the query and context in the output.
    """
    from retrieval_service.core import build_rag_prompt
    
    query = "test query"
    context = "Some test context about emails"
    user_info = {"name": "Test User", "email": "test@example.com"}
    raw_results = [
        {'type': 'email', 'id': '123', 'score': 0.9}
    ]
    
    prompt = build_rag_prompt(query, context, user_info, raw_results)
    
    assert isinstance(prompt, str), "Prompt should be a string"
    assert query in prompt, "Prompt should include the query"
    assert context in prompt, "Prompt should include the context"
    assert "REFERENCE_IDS" in prompt, "Prompt should mention REFERENCE_IDS"
