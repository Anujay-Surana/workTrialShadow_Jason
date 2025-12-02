"""
Real ReAct Agent Implementation
Uses Thought -> Action -> Observation loop pattern
"""

import re
import json
from typing import List, Dict, Tuple, AsyncGenerator
from .search_utils import vector_search, keyword_search, fuzzy_search
from .supabase_utils import supabase

REACT_SYSTEM_PROMPT = """You are a ReAct agent helping users find information from their personal knowledge base.

You must follow this loop format:

Thought: your reasoning about what to do next
Action: semantic_search query here
OR
Action: keyword_search query here  
OR
Action: fuzzy_search query here
OR
Final: your answer here

Available tools:
- semantic_search - Search by meaning/similarity
- keyword_search - Search for exact keyword matches
- fuzzy_search - Search with typo tolerance

After each action is executed, you will receive:
Observation: <tool output with search results>

Then continue the loop.

Guidelines:
- Think step by step about what information you need
- Try different search strategies if one doesn't work
- When you have enough information to answer, use: Final: your answer
- If after multiple attempts you cannot find information, use: Final: explanation

Example:
Thought: I need to search for emails about the project
Action: semantic_search project emails
"""


def parse_action(text: str) -> Tuple[str, str]:
    """Parse action from agent output - simple prefix matching"""
    lines = text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Check for Final answer
        if line.startswith('Final:'):
            answer = line[6:].strip()  # Remove "Final:" prefix
            return 'finish', answer
        
        # Check for Action
        if line.startswith('Action:'):
            action_text = line[7:].strip()  # Remove "Action:" prefix
            
            # Try to extract tool and query
            if action_text.startswith('semantic_search'):
                query = action_text[15:].strip()  # Remove "semantic_search"
                return 'semantic_search', query
            elif action_text.startswith('keyword_search'):
                query = action_text[14:].strip()  # Remove "keyword_search"
                return 'keyword_search', query
            elif action_text.startswith('fuzzy_search'):
                query = action_text[12:].strip()  # Remove "fuzzy_search"
                return 'fuzzy_search', query
    
    return None, None


async def execute_search_tool(tool: str, arg: str, user_id: str) -> str:
    """Execute a search tool and return formatted observation"""
    try:
        # Parse the query from arg
        query = arg.strip()
        
        if tool == "vector_search":
            # Use embedding-based search
            from .gemni_api_utils import embed_text
            query_embedding = embed_text(query)
            from .search_utils import vector_search
            results = vector_search(user_id, query_embedding, top_k=3)
        elif tool == "keyword_search":
            # Keyword search with single query
            results = keyword_search(user_id, [query], top_k=3)
        elif tool == "fuzzy_search":
            results = fuzzy_search(user_id, query, top_k=3)
        else:
            return f"[ERROR] Unknown tool: {tool}"
        
        if not results:
            return "No results found."
        
        # Format results with context from database
        formatted = []
        for i, result in enumerate(results, 1):
            result_type = result.get('type')
            result_id = result.get('id')
            score = result.get('score', 0)
            
            try:
                # Fetch content based on type
                if result_type == 'email':
                    response = supabase.table('emails').select('subject, body, from_user, date')\
                        .eq('user_id', user_id).eq('id', result_id).execute()
                    if response.data:
                        email = response.data[0]
                        content = f"Subject: {email.get('subject', 'N/A')}\nFrom: {email.get('from_user', 'N/A')}\nDate: {email.get('date', 'N/A')}\n{email.get('body', '')[:200]}"
                        formatted.append(f"Result {i} [Email] (score: {score:.3f}):\n{content}")
                
                elif result_type == 'schedule':
                    response = supabase.table('schedules').select('summary, description, start_time, location')\
                        .eq('user_id', user_id).eq('id', result_id).execute()
                    if response.data:
                        schedule = response.data[0]
                        content = f"Title: {schedule.get('summary', 'N/A')}\nTime: {schedule.get('start_time', 'N/A')}\nLocation: {schedule.get('location', 'N/A')}\n{schedule.get('description', '')[:200]}"
                        formatted.append(f"Result {i} [Schedule] (score: {score:.3f}):\n{content}")
                
                elif result_type == 'file':
                    response = supabase.table('files').select('name, summary, mime_type')\
                        .eq('user_id', user_id).eq('id', result_id).execute()
                    if response.data:
                        file = response.data[0]
                        content = f"Name: {file.get('name', 'N/A')}\nType: {file.get('mime_type', 'N/A')}\n{file.get('summary', 'No summary')[:200]}"
                        formatted.append(f"Result {i} [File] (score: {score:.3f}):\n{content}")
                
                elif result_type == 'attachment':
                    response = supabase.table('attachments').select('filename, summary, mime_type')\
                        .eq('user_id', user_id).eq('id', result_id).execute()
                    if response.data:
                        attachment = response.data[0]
                        content = f"Filename: {attachment.get('filename', 'N/A')}\nType: {attachment.get('mime_type', 'N/A')}\n{attachment.get('summary', 'No summary')[:200]}"
                        formatted.append(f"Result {i} [Attachment] (score: {score:.3f}):\n{content}")
            
            except Exception as e:
                print(f"Error fetching {result_type} {result_id}: {e}")
                continue
        
        return "\n\n".join(formatted) if formatted else "No results found."
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"[ERROR] {str(e)}"


async def react_agent_stream(messages: List[Dict], user_id: str, max_iterations: int = 10) -> AsyncGenerator:
    """
    Real ReAct agent with Thought-Action-Observation loop
    Streams the thinking process and final answer
    """
    from .openai_api_utils import async_client
    
    # Add system prompt
    agent_messages = [
        {"role": "system", "content": REACT_SYSTEM_PROMPT}
    ] + messages
    
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        # Get agent's thought and action
        response = await async_client.chat.completions.create(
            model="gpt-4o",
            messages=agent_messages,
            temperature=0
        )
        
        output = response.choices[0].message.content
        
        # Stream the thought process
        yield {
            "type": "react_step",
            "iteration": iteration,
            "content": output
        }
        
        # Parse action
        tool, arg = parse_action(output)
        
        if not tool:
            # No valid action found, append and continue
            agent_messages.append({"role": "assistant", "content": output})
            continue
        
        # Check if finish action
        if tool == "finish":
            # Stream final answer
            yield {
                "type": "react_final",
                "answer": arg
            }
            return
        
        # Execute search tool
        observation = await execute_search_tool(tool, arg, user_id)
        
        # Stream observation
        yield {
            "type": "react_observation",
            "tool": tool,
            "observation": observation
        }
        
        # Add to conversation history
        agent_messages.append({"role": "assistant", "content": output})
        agent_messages.append({"role": "user", "content": f"Observation: {observation}"})
    
    # Max iterations reached
    yield {
        "type": "react_final",
        "answer": "I've reached the maximum number of search iterations. Based on the information gathered, I may not have found exactly what you're looking for. Please try rephrasing your question or provide more specific details."
    }
