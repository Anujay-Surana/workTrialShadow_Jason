"""
Core business logic module.

This module contains the core business logic for the Memory Retrieval Service,
including RAG (Retrieval-Augmented Generation) and ReAct (Reasoning and Acting)
agent implementations.
"""

from .agent import SEARCH_TOOLS, REACT_SYSTEM_PROMPT, DEFAULT_TOP_K
from .rag import combined_search, deduplicate_results, build_rag_prompt
from .react import react_agent_direct, parse_action, execute_search_tool, execute_search_tool_with_results

__all__ = [
    "SEARCH_TOOLS",
    "REACT_SYSTEM_PROMPT",
    "DEFAULT_TOP_K",
    "combined_search",
    "deduplicate_results",
    "build_rag_prompt",
    "react_agent_direct",
    "parse_action",
    "execute_search_tool",
    "execute_search_tool_with_results",
]
