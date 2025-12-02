import json

from retrieval_service import openai_api_utils
from retrieval_service.search_utils import DEFAULT_TOP_K

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
You are a ReAct (Reason + Act) assistant for personal retrieval on top of the user's:
- Gmail emails
- Google Calendar events
- Google Drive files
- Gmail attachments

You have access to three tools:
1) vector_search: semantic/vector search across all personal data.
2) keyword_search: keyword-based search where YOU can choose specific keywords.
3) fuzzy_search: fuzzy search for approximate matches and typos.

General rules:
- Always think in hidden chain-of-thought (do NOT output your reasoning).
- Try anything you can to find relevant personal data to answer the user's question, dig deeply.
- If the user's question might require looking into their personal data, call one or more search tools.
- You may call tools multiple times, refine queries, use different modes (semantic/keyword/fuzzy) and different top_k.
- Tools return both raw results and a 'context' string that already summarizes the content. Use that context to answer.
- If the question does NOT require personal data (e.g., general knowledge), answer directly without calling tools.
- Be explicit about what information comes from the retrieved context vs. your general knowledge.
- If context is missing or insufficient, say so honestly.
- if the tool result is not satisfactory, try again with different queries or modes until you find useful information.
- Only stop when you think failure is unavoidable.

When you answer the user, respond in Markdown.
"""