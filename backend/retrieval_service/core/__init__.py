"""
Core business logic module.

This module contains the core business logic for the Memory Retrieval Service,
including RAG (Retrieval-Augmented Generation) and ReAct (Reasoning and Acting)
agent implementations.
"""

from .mixed import SEARCH_TOOLS, MIXED_MODE_SYSTEM_PROMPT, DEFAULT_TOP_K
from .rag import combined_search, deduplicate_results, build_rag_prompt, RAG_SYSTEM_PROMPT
from .react import react_agent, parse_action, execute_search_tool, execute_search_tool_with_results, REACT_SYSTEM_PROMPT

__all__ = [
    "SEARCH_TOOLS",
    "RAG_SYSTEM_PROMPT",
    "MIXED_MODE_SYSTEM_PROMPT",
    "REACT_SYSTEM_PROMPT",
    "DEFAULT_TOP_K",
    "combined_search",
    "deduplicate_results",
    "build_rag_prompt",
    "react_agent",
    "parse_action",
    "execute_search_tool",
    "execute_search_tool_with_results",
]
