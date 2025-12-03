"""
Agent definitions for the retrieval service.

This module contains tool definitions and system prompts for the ReAct agent.
Includes search tool specifications and the ReAct system prompt.
"""

import json
import os

DEFAULT_TOP_K = int(os.getenv("SEARCH_TOP_K", "5"))

SEARCH_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "vector_search",
            "description": "Semantic vector search over the user's emails, calendar events, files and attachments. Use when you want meaning-based search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query describing what you are looking for."
                    },
                    "search_types": {
                        "type": "array",
                        "description": "Optional specific embedding types to search. Leave empty to search everything.",
                        "items": {
                            "type": "string",
                            "enum": [
                                "email_context",
                                "schedule_context",
                                "file_context",
                                "attachment_context"
                            ]
                        }
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of results to retrieve.",
                        "minimum": 1,
                        "maximum": 50,
                        "default": DEFAULT_TOP_K
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "keyword_search",
            "description": "Keyword search over the user's emails, calendar events, files and attachments. Use when exact words or names matter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "User request or description; used to auto-generate keywords if keywords array is omitted."
                    },
                    "keywords": {
                        "type": "array",
                        "description": "Optional explicit keywords chosen by you. If omitted, the server will split the query into words.",
                        "items": {"type": "string"}
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of results to retrieve.",
                        "minimum": 1,
                        "maximum": 50,
                        "default": DEFAULT_TOP_K
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fuzzy_search",
            "description": "Fuzzy full-text search over the user's emails, calendar events, files and attachments. Use when the user is unsure about exact wording or spelling.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The approximate text to match."
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of results to retrieve.",
                        "minimum": 1,
                        "maximum": 50,
                        "default": DEFAULT_TOP_K
                    }
                },
                "required": ["query"]
            }
        }
    }
]

REACT_SYSTEM_PROMPT = """
You are a memory retrieval module that extracts factual context from user's personal data:
- Gmail emails
- Google Calendar events
- Google Drive files
- Gmail attachments

CRITICAL: Write in THIRD-PERSON perspective. Describe what exists in the data, not what you found.

You have access to three tools:
1) vector_search: semantic/vector search across all personal data
2) keyword_search: keyword-based search with specific keywords
3) fuzzy_search: fuzzy search for approximate matches and typos

Rules:
- Call search tools to retrieve relevant information
- You may call tools multiple times with different queries
- Keep final response SHORT (3-4 sentences max)
- Use THIRD-PERSON perspective: "User has...", "Data contains...", "Records show..."
- Do NOT use first-person: "I found...", "I see...", "Let me..."
- Focus on key facts: dates, people, actions, deadlines
- If no relevant data found, state it objectively in one sentence

Examples of correct output:
✓ "User has 2 emails about project deadline. Meeting scheduled Dec 5 at 2PM. Budget proposal due Dec 3."
✓ "Data contains 3 calendar events with Sarah this week. Next meeting is Dec 3 at 2PM."
✓ "No relevant information exists in user's personal data."

Examples of incorrect output:
✗ "I found 2 emails about project deadline."
✗ "Let me help you with that."
✗ "Here's what I discovered..."
"""
