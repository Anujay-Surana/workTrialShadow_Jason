"""
ReAct (Reasoning and Acting) agent implementation.

This module implements the ReAct agent pattern with Thought-Action-Observation loops
for intelligent memory retrieval from user's personal data.
"""

import re
import json
from typing import List, Dict, Tuple
from retrieval_service.search import vector_search, keyword_search, fuzzy_search
from retrieval_service.data.database import supabase
from retrieval_service.search import parse_reference_ids, fetch_references_by_ids
from retrieval_service.infrastructure.logging import log_debug, log_info, log_warning, log_error
from dotenv import load_dotenv

REACT_SYSTEM_PROMPT = """You are a memory retrieval agent that extracts factual context from user data.

CRITICAL RULES:
1. Write in THIRD-PERSON perspective
2. You MUST follow the exact format below
3. NEVER write "Observation:" yourself - the system will provide it
4. After writing an Action, STOP and WAIT for the Observation
5. In Final answer, include REFERENCE_IDS line with relevant source IDs

EXACT FORMAT TO FOLLOW:

Thought: [your reasoning]
Action: [tool_name] [query]

Then STOP. The system will provide:
Observation: [search results with IDs like email_123, schedule_456]

Then you continue:
Thought: [analyze the observation]
Action: [another search if needed]
OR
Final: [SHORT third-person summary]
REFERENCE_IDS: [comma-separated IDs from observations]

Available tools:
- vector_search [query] - Search by meaning/similarity
- keyword_search [query] - Search for exact keyword matches
- fuzzy_search [query] - Search with typo tolerance

IMPORTANT:
- DO NOT write "Observation:" yourself - it will be provided by the system
- After Action, you MUST stop and wait
- Keep Final answer SHORT (3-4 sentences max)
- Use third-person: "User has...", "Data contains...", "Records show..."
- Include REFERENCE_IDS line with IDs from the observations you used

CORRECT Example:
Thought: Need to search for emails about the project
Action: vector_search project emails
[SYSTEM PROVIDES: Observation with email_123, email_456]
Thought: Found 2 relevant emails, can provide summary
Final: User has 2 emails about project X. Deadline is Dec 15. Meeting scheduled Dec 10 at 3PM.
REFERENCE_IDS: email_123, email_456

WRONG Example (DO NOT DO THIS):
Thought: Need to search for emails
Action: vector_search project emails
Observation: Found 2 emails... [WRONG - don't write this yourself]
"""


def parse_action(text: str) -> Tuple[str, str]:
    """Parse action from agent output - strict prefix matching"""
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Check for Final answer (must be on its own line)
        if line.startswith('Final:'):
            answer = line[6:].strip()
            # Get all remaining lines after Final:
            final_index = text.find('Final:')
            if final_index != -1:
                answer = text[final_index + 6:].strip()
            return 'finish', answer
        
        # Check for Action (must be on its own line)
        if line.startswith('Action:'):
            action_text = line[7:].strip()
            
            # Parse tool and query - format: "tool_name query"
            parts = action_text.split(None, 1)  # Split on first whitespace
            if len(parts) >= 1:
                tool_name = parts[0].lower()
                query = parts[1] if len(parts) > 1 else ""
                
                if tool_name == 'vector_search':
                    return 'vector_search', query
                elif tool_name == 'keyword_search':
                    return 'keyword_search', query
                elif tool_name == 'fuzzy_search':
                    return 'fuzzy_search', query
    
    return None, None


def _format_result_for_agent(result_type: str, data: Dict, source_id: str, score: float, index: int) -> str:
    """Format a single result for agent observation, including all relevant fields except user_id"""
    
    if result_type == 'email':
        # Include all email fields except user_id
        fields = [
            f"ID: {source_id}",
            f"Subject: {data.get('subject', 'N/A')}",
            f"From: {data.get('from_user', 'N/A')}",
            f"To: {data.get('to_user', 'N/A')}",
        ]
        if data.get('cc'):
            fields.append(f"CC: {data.get('cc')}")
        if data.get('bcc'):
            fields.append(f"BCC: {data.get('bcc')}")
        fields.append(f"Date: {data.get('date', 'N/A')}")
        if data.get('thread_id'):
            fields.append(f"Thread: {data.get('thread_id')}")
        
        # Add body preview
        body = data.get('body', '')
        if body:
            fields.append(f"Body: {body[:300]}...")
        
        content = "\n".join(fields)
        return f"Result {index} [Email] (score: {score:.3f}):\n{content}"
    
    elif result_type == 'schedule':
        # Include all schedule fields except user_id
        fields = [
            f"ID: {source_id}",
            f"Title: {data.get('summary', 'N/A')}",
            f"Start: {data.get('start_time', 'N/A')}",
            f"End: {data.get('end_time', 'N/A')}",
        ]
        if data.get('location'):
            fields.append(f"Location: {data.get('location')}")
        if data.get('creator_email'):
            fields.append(f"Creator: {data.get('creator_email')}")
        if data.get('organizer_email'):
            fields.append(f"Organizer: {data.get('organizer_email')}")
        
        # Add description preview
        description = data.get('description', '')
        if description:
            fields.append(f"Description: {description[:300]}...")
        
        content = "\n".join(fields)
        return f"Result {index} [Schedule] (score: {score:.3f}):\n{content}"
    
    elif result_type == 'file':
        # Include all file fields except user_id
        fields = [
            f"ID: {source_id}",
            f"Name: {data.get('name', 'N/A')}",
            f"Path: {data.get('path', 'N/A')}",
            f"Type: {data.get('mime_type', 'N/A')}",
        ]
        if data.get('size'):
            fields.append(f"Size: {data.get('size')} bytes")
        if data.get('modified_time'):
            fields.append(f"Modified: {data.get('modified_time')}")
        
        # Add summary
        summary = data.get('summary', '')
        if summary:
            fields.append(f"Summary: {summary[:300]}...")
        
        content = "\n".join(fields)
        return f"Result {index} [File] (score: {score:.3f}):\n{content}"
    
    elif result_type == 'attachment':
        # Include all attachment fields except user_id
        fields = [
            f"ID: {source_id}",
            f"Filename: {data.get('filename', 'N/A')}",
            f"Type: {data.get('mime_type', 'N/A')}",
        ]
        if data.get('size'):
            fields.append(f"Size: {data.get('size')} bytes")
        if data.get('email_id'):
            fields.append(f"From Email: {data.get('email_id')}")
        
        # Add summary
        summary = data.get('summary', '')
        if summary:
            fields.append(f"Summary: {summary[:300]}...")
        
        content = "\n".join(fields)
        return f"Result {index} [Attachment] (score: {score:.3f}):\n{content}"
    
    return f"Result {index} [Unknown Type] (score: {score:.3f})"


async def execute_search_tool_with_results(tool: str, arg: str, user_id: str) -> Tuple[str, List[Dict]]:
    """
    Execute a search tool and return both formatted observation and raw results.
    
    Returns:
        Tuple of (formatted_observation, raw_results)
    """
    try:
        # Parse the query from arg
        query = arg.strip()
        
        # Execute appropriate search
        if tool == "vector_search":
            from retrieval_service.api.gemini_client import embed_text
            query_embedding = embed_text(query)
            results = vector_search(user_id, query_embedding, top_k=3)
        elif tool == "keyword_search":
            results = keyword_search(user_id, [query], top_k=3)
        elif tool == "fuzzy_search":
            results = fuzzy_search(user_id, query, top_k=3)
        else:
            return f"[ERROR] Unknown tool: {tool}", []
        
        if not results:
            return "No results found.", []
        
        # Format results with ALL relevant fields from database
        formatted = []
        for i, result in enumerate(results, 1):
            result_type = result.get('type')
            result_id = result.get('id')
            score = result.get('score', 0)
            source_id = f"{result_type}_{result_id}"
            
            try:
                # Fetch ALL fields except user_id
                if result_type == 'email':
                    response = supabase.table('emails').select('*')\
                        .eq('user_id', user_id).eq('id', result_id).execute()
                elif result_type == 'schedule':
                    response = supabase.table('schedules').select('*')\
                        .eq('user_id', user_id).eq('id', result_id).execute()
                elif result_type == 'file':
                    response = supabase.table('files').select('*')\
                        .eq('user_id', user_id).eq('id', result_id).execute()
                elif result_type == 'attachment':
                    response = supabase.table('attachments').select('*')\
                        .eq('user_id', user_id).eq('id', result_id).execute()
                else:
                    continue
                
                if response.data and len(response.data) > 0:
                    data = response.data[0]
                    # Remove user_id from data before formatting
                    data.pop('user_id', None)
                    formatted_result = _format_result_for_agent(result_type, data, source_id, score, i)
                    formatted.append(formatted_result)
            
            except Exception as e:
                log_error(f"Error fetching {result_type} {result_id}: {e}")
                continue
        
        observation = "\n\n".join(formatted) if formatted else "No results found."
        return observation, results
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"[ERROR] {str(e)}", []


async def execute_search_tool(tool: str, arg: str, user_id: str) -> str:
    """
    Execute a search tool and return formatted observation.
    Convenience wrapper around execute_search_tool_with_results.
    """
    observation, _ = await execute_search_tool_with_results(tool, arg, user_id)
    return observation


async def react_agent(messages: List[Dict], user_id: str, max_iterations: int = 10) -> Dict:
    """
    Real ReAct agent with Thought-Action-Observation loop.
    Returns complete result as JSON with third-person perspective.
    """
    from retrieval_service.api.openai_client import async_client
    import os
    
    verbose = os.getenv("VERBOSE_OUTPUT", "false").lower() == "true"
    
    agent_messages = [
        {"role": "system", "content": REACT_SYSTEM_PROMPT}
    ] + messages
    
    iteration = 0
    process_steps = []
    all_search_results = []  # Track all results for reference selection
    
    while iteration < max_iterations:
        iteration += 1
        
        response = await async_client.chat.completions.create(
            model="gpt-4o",
            messages=agent_messages,
            temperature=0,
            stop=["Observation:"]  # Stop generation if model tries to write Observation
        )
        
        output = response.choices[0].message.content
        
        if verbose:
            log_info(f"[ReAct] Iteration {iteration}:")
            log_info(output)
            log_info("---")
        
        # Check if model hallucinated an Observation
        if "Observation:" in output.lower():
            # Remove the hallucinated observation
            output = output.split("Observation:")[0].strip()
            if verbose:
                log_warning("[ReAct] WARNING: Model tried to write Observation, removed it")
        
        tool, arg = parse_action(output)
        
        if not tool:
            agent_messages.append({"role": "assistant", "content": output})
            process_steps.append({"step": "thought", "iteration": iteration, "content": output})
            continue
        
        if tool == "finish":
            # Extract content and parse REFERENCE_IDS
            full_output = arg.strip()
            content, selected_ids = parse_reference_ids(full_output)
            
            # Fetch full reference data for selected IDs
            selected_references = fetch_references_by_ids(
                selected_ids,
                all_search_results,
                verbose=verbose
            )
            
            result = {
                "content": content,
                "references": selected_references
            }
            if verbose:
                result["process"] = process_steps
                result["llm_selected_ids"] = selected_ids
            return result
        
        # Execute search tool and collect results
        observation, search_results = await execute_search_tool_with_results(tool, arg, user_id)
        all_search_results.extend(search_results)
        
        process_steps.append({
            "step": "action",
            "iteration": iteration,
            "tool": tool,
            "observation": observation[:200]
        })
        
        agent_messages.append({"role": "assistant", "content": output})
        agent_messages.append({"role": "user", "content": f"Observation: {observation}"})
    
    # Max iterations reached
    answer = "Maximum search iterations reached. No sufficient information found in user's personal data."
    
    result = {
        "content": answer,
        "references": []
    }
    
    if verbose:
        result["process"] = process_steps
    
    return result
