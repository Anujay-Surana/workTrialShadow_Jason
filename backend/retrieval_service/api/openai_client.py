"""
OpenAI API Client and Agent Functions.

Handles LLM interactions for RAG and ReAct modes including:
- Chat completions for general LLM inference
- RAG mode with retrieval and context generation
- Mixed mode with tool calling (ReAct)

All text generation and summarization operations use OpenAI API.
"""

import os
import re
import json
import time
from typing import List
from dotenv import load_dotenv
from openai import AsyncOpenAI
from retrieval_service.infrastructure.logging import log_debug, log_info, log_warning, log_error
from retrieval_service.infrastructure.monitoring import monitor
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables or .env file")

async_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def chat_completion(messages: list, model: str = "gpt-4o", max_retries: int = 3):
    """
    Get chat completion using GPT-4o (async) with retry logic.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model to use (default: gpt-4o)
        max_retries: Maximum number of retry attempts
    
    Returns:
        str: Complete response text
    """
    for attempt in range(max_retries):
        try:
            response = await async_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
            )
            
            monitor.log_request('openai', 'chat_completion', 'success', attempt)
            return response.choices[0].message.content
            
        except Exception as e:
            error_str = str(e)
            # Check if it's a retryable error (timeout, rate limit, server error)
            is_retryable = any(code in error_str for code in ["504", "503", "429", "500", "timeout", "rate_limit"])
            
            if attempt < max_retries - 1 and is_retryable:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = 1 * (2 ** attempt)
                log_warning(f"OpenAI API error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                monitor.log_request('openai', 'chat_completion', 'retry', attempt)
                time.sleep(wait_time)
            else:
                # Non-retryable error or final attempt
                log_error(f"OpenAI API error after {max_retries} attempts: {e}")
                monitor.log_request('openai', 'chat_completion', 'error', attempt)
                raise


async def rag(messages, user_id: str, query: str, user_info: dict):
    """
    Direct RAG mode: Perform retrieval and generate context summary.
    LLM decides which references to return.
    Returns complete result as JSON.
    """
    # Lazy imports to avoid circular dependency
    from retrieval_service.core import combined_search, build_rag_prompt
    from retrieval_service.search import parse_reference_ids, fetch_references_by_ids
    
    verbose = os.getenv("VERBOSE_OUTPUT", "false").lower() == "true"
    process_steps = []
    
    # Perform combined search
    try:
        context, all_references, raw_results = combined_search(
            user_id=user_id,
            query=query,
            top_k=5
        )
        process_steps.append({"step": "search", "result_count": len(all_references)})
        
    except Exception as e:
        if verbose:
            log_warning(f"[RAG] Search error: {e}")
        context = ""
        all_references = []
        raw_results = []
    
    # Build RAG prompt with raw results
    rag_prompt = build_rag_prompt(query, context, user_info, raw_results)
    messages_copy = messages[:-1]
    messages_copy.append({"role": "user", "content": rag_prompt})
    
    # Use chat_completion with retry logic
    llm_output = await chat_completion(messages_copy, model="gpt-4o")
    
    # Parse LLM output to extract content and reference IDs
    content, selected_ids = parse_reference_ids(llm_output)
    
    # Fetch full reference data for selected IDs
    selected_references = fetch_references_by_ids(
        selected_ids,
        raw_results,
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


async def mixed_agent(messages, user_id: str, query: str, user_info: dict, max_iterations: int = 5):
    """
    Mixed mode: RAG with tool calling.
    - Starts with initial RAG search
    - AI can call search tools multiple times
    - AI outputs REFERENCE_IDS in the final response
    - Program parses REFERENCE_IDS and fetches full data
    """
    # Lazy imports to avoid circular dependency
    from retrieval_service.core import SEARCH_TOOLS, combined_search, build_rag_prompt
    from retrieval_service.search import parse_reference_ids, fetch_references_by_ids, execute_search_tool
    
    verbose = os.getenv("VERBOSE_OUTPUT", "false").lower() == "true"
    
    all_raw_results = []  # Collect all search results for ID lookup
    process_steps = []
    
    # Perform initial combined search (RAG)
    try:
        context, all_references, raw_results = combined_search(
            user_id=user_id,
            query=query,
            top_k=5
        )
        process_steps.append({"step": "search", "result_count": len(all_references)})
        all_raw_results.extend(raw_results)
        
    except Exception as e:
        if verbose:
            log_warning(f"[MIXED] Initial search error: {e}")
        context = ""
        all_references = []
        raw_results = []
    
    # Build RAG prompt with raw results
    rag_prompt = build_rag_prompt(query, context, user_info, raw_results)
    messages_copy = messages[:-1]
    messages_copy.append({"role": "user", "content": rag_prompt})
    
    iteration = 0
    
    # Tool calling loop
    while iteration < max_iterations:
        iteration += 1
        if verbose:
            log_debug(f"[MIXED] Tool calling iteration {iteration}/{max_iterations}")
        
        # Retry logic for tool calling
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await async_client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages_copy,
                    tools=SEARCH_TOOLS,
                    tool_choice="auto",
                )
                monitor.log_request('openai', 'tool_calling', 'success', attempt)
                break
            except Exception as e:
                error_str = str(e)
                is_retryable = any(code in error_str for code in ["504", "503", "429", "500", "timeout", "rate_limit"])
                
                if attempt < max_retries - 1 and is_retryable:
                    wait_time = 1 * (2 ** attempt)
                    log_warning(f"OpenAI tool calling error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                    monitor.log_request('openai', 'tool_calling', 'retry', attempt)
                    time.sleep(wait_time)
                else:
                    log_error(f"OpenAI tool calling error after {max_retries} attempts: {e}")
                    monitor.log_request('openai', 'tool_calling', 'error', attempt)
                    raise

        assistant_msg = response.choices[0].message
        tool_calls = assistant_msg.tool_calls or []
        
        if not tool_calls:
            # AI has finished and provided final response
            if verbose:
                log_debug(f"[MIXED] No more tool calls, AI provided final response")
            llm_output = assistant_msg.content
            break
        
        messages_copy.append(assistant_msg)
        
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments or "{}")

            tool_output = await execute_search_tool(function_name, arguments, user_id)

            # Collect raw results for later ID lookup
            if tool_output.get("raw_results"):
                all_raw_results.extend(tool_output["raw_results"])

            # Send context to AI (not references)
            simplified_output = {
                "ok": tool_output.get("ok", True),
                "result_count": len(tool_output.get("references", [])),
                "context": tool_output.get("context", "No results found")
            }
            
            if not tool_output.get("ok"):
                simplified_output["error"] = tool_output.get("error", "Unknown error")

            messages_copy.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": json.dumps(simplified_output, ensure_ascii=False),
            })

            result_count = len(tool_output.get("references", []))
            process_steps.append({
                "step": "tool_call",
                "tool": function_name,
                "result_count": result_count
            })
    else:
        # Loop ended due to max iterations, need final completion
        if verbose:
            log_debug(f"[MIXED] Max iterations reached, generating final response")
        llm_output = await chat_completion(messages_copy, model="gpt-4o")
    
    # Parse REFERENCE_IDS from LLM output
    content, selected_ids = parse_reference_ids(llm_output)
    
    if verbose:
        log_debug(f"[MIXED] LLM selected IDs: {selected_ids}")
    
    # Fetch full reference data for selected IDs
    selected_references = fetch_references_by_ids(
        selected_ids,
        all_raw_results,
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
