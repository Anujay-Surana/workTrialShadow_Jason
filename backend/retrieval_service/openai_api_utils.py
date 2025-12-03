# openai_api_utils.py
import os
from typing import List
from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI
from retrieval_service.agent import SEARCH_TOOLS
from retrieval_service.search_utils import execute_search_tool
import json

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables or .env file")

VERBOSE_OUTPUT = os.getenv("VERBOSE_OUTPUT", "false").lower() == "true"

client = OpenAI(api_key=OPENAI_API_KEY)
async_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

def log(message: str):
    """Log message only if VERBOSE_OUTPUT is enabled"""
    if VERBOSE_OUTPUT:
        print(message)


def summarize(text: str, max_chars: int = 8000) -> str:
    """
    Summarize long text using the cheapest OpenAI model available.

    - Automatically truncates input to prevent overspending
    - Uses gpt-4o-mini which is the lowest-cost model
    """
    if not isinstance(text, str):
        raise ValueError("summarize() expects a string")

    # Safety limit: prevent sending extremely long text
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[input truncated]"

    prompt = f"Please summarize the following content in a concise way (only first {max_chars} chars are shown):\n\n{text}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",   # Cheapest high-quality model
        messages=[
            {"role": "system", "content": "You are a concise summarization assistant."},
            {"role": "user", "content": prompt},
        ]
    )

    return response.choices[0].message.content.strip()


async def chat_completion(messages: list, model: str = "gpt-4o"):
    """
    Get chat completion using GPT-4o (async).
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model to use (default: gpt-4o)
    
    Returns:
        str: Complete response text
    """
    response = await async_client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7,
    )
    
    return response.choices[0].message.content

def chunk_text(text: str, chunk_size: int = 6000, overlap: int = 200) -> list[str]:
    """
    Split text into overlapping chunks for processing.
    
    Args:
        text: Text to chunk
        chunk_size: Target size for each chunk
        overlap: Number of characters to overlap between chunks
    
    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to break at a sentence or paragraph boundary
        if end < len(text):
            # Look for paragraph break first
            last_para = text[start:end].rfind('\n\n')
            if last_para > chunk_size * 0.5:  # At least 50% of chunk size
                end = start + last_para
            else:
                # Look for sentence break
                last_period = text[start:end].rfind('. ')
                if last_period > chunk_size * 0.5:
                    end = start + last_period + 1
        
        chunks.append(text[start:end])
        start = end - overlap if end < len(text) else end
    
    return chunks


def summarize_chunk(chunk: str, chunk_index: int, total_chunks: int) -> str:
    """
    Summarize a single chunk of text.
    
    Args:
        chunk: Text chunk to summarize
        chunk_index: Index of this chunk (0-based)
        total_chunks: Total number of chunks
    
    Returns:
        Summary of the chunk
    """
    prompt = f"Summarize this section (part {chunk_index + 1} of {total_chunks}):\n\n{chunk}"
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a summarization assistant. Provide concise summaries."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    
    return response.choices[0].message.content.strip()


def combine_summaries(summaries: list[str], filename: str) -> str:
    """
    Combine multiple chunk summaries into one final summary.
    
    Args:
        summaries: List of chunk summaries
        filename: Name of the original file
    
    Returns:
        Final combined summary
    """
    combined_text = "\n\n".join([f"Section {i+1}: {summary}" for i, summary in enumerate(summaries)])
    
    prompt = f"Combine these section summaries of the file '{filename}' into one cohesive summary. Start with 'A(n) [file type] file...':\n\n{combined_text}"
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a summarization assistant. Create a unified summary from multiple parts."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    
    return response.choices[0].message.content.strip()


def summarize_doc(text: str, filename: str, max_chars: int = 30000, chunk_size: int = 6000) -> str:
    """
    Summarize long text docs using map-reduce approach with chunking.
    
    - For small texts (< chunk_size): Direct summarization
    - For large texts: 
      1. Split into chunks
      2. Summarize each chunk (map)
      3. Combine summaries (reduce)
    - Uses gpt-4o-mini for cost efficiency
    
    Args:
        text: Text to summarize
        filename: Name of the file
        max_chars: Maximum characters to process (safety limit)
        chunk_size: Size of each chunk for processing
    
    Returns:
        Final summary
    """
    if not isinstance(text, str):
        raise ValueError("summarize_doc() expects a string")
    
    # Safety limit: prevent processing extremely long text
    if len(text) > max_chars:
        log(f"[WARNING] File {filename} exceeds {max_chars} chars, truncating to limit")
        text = text[:max_chars]
    
    # If text is small enough, summarize directly
    if len(text) <= chunk_size:
        prompt = f"Please summarize this file named '{filename}' concisely, starting with 'A(n) [file type] file...':\n\n{text}"
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a concise summarization assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        
        return response.choices[0].message.content.strip()
    
    # Map-reduce approach for large texts
    log(f"[INFO] File {filename} is large ({len(text)} chars), using chunked summarization")
    
    # Step 1: Split into chunks
    chunks = chunk_text(text, chunk_size=chunk_size)
    log(f"[INFO] Split into {len(chunks)} chunks")
    
    # Step 2: Summarize each chunk (map)
    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        try:
            summary = summarize_chunk(chunk, i, len(chunks))
            chunk_summaries.append(summary)
            log(f"[INFO] Summarized chunk {i+1}/{len(chunks)}")
        except Exception as e:
            log(f"[ERROR] Failed to summarize chunk {i+1}: {e}")
            chunk_summaries.append(f"[Error summarizing section {i+1}]")
    
    # Step 3: Combine summaries (reduce)
    final_summary = combine_summaries(chunk_summaries, filename)
    log(f"[INFO] Created final summary for {filename}")
    
    return final_summary

async def rag_direct(messages, user_id: str, query: str, user_info: dict):
    """
    Direct RAG mode: Perform retrieval and generate context summary.
    LLM decides which references to return.
    Returns complete result as JSON.
    """
    from retrieval_service.rag_utils import combined_search, build_rag_prompt
    from retrieval_service.supabase_utils import supabase
    import os
    import re
    
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
            log(f"[RAG] Search error: {e}")
        context = ""
        all_references = []
        raw_results = []
    
    # Build RAG prompt with raw results
    rag_prompt = build_rag_prompt(query, context, user_info, raw_results)
    messages_copy = messages[:-1]
    messages_copy.append({"role": "user", "content": rag_prompt})
    
    response = await async_client.chat.completions.create(
        model="gpt-4o",
        messages=messages_copy,
        temperature=0.3,
    )
    
    llm_output = response.choices[0].message.content
    
    # Parse LLM output to extract content and reference IDs
    content = llm_output
    selected_ids = []
    
    # Extract REFERENCE_IDS line
    ref_match = re.search(r'REFERENCE_IDS:\s*(.+?)(?:\n|$)', llm_output, re.IGNORECASE)
    if ref_match:
        ref_line = ref_match.group(1).strip()
        # Remove the REFERENCE_IDS line from content
        content = re.sub(r'REFERENCE_IDS:.*?(?:\n|$)', '', llm_output, flags=re.IGNORECASE).strip()
        
        if ref_line.lower() != 'none':
            # Parse comma-separated IDs
            selected_ids = [id.strip() for id in ref_line.split(',') if id.strip()]
    
    # Import the helper function
    from retrieval_service.react_agent_utils import fetch_full_reference
    
    # Fetch full reference data for selected IDs
    selected_references = []
    for ref_id in selected_ids:
        try:
            # Parse type and ID from format like "email_123" or just "123"
            if '_' in ref_id:
                ref_type, ref_db_id = ref_id.split('_', 1)
            else:
                # Try to find in raw_results
                matching = [r for r in raw_results if str(r.get('id')) == ref_id]
                if matching:
                    ref_type = matching[0].get('type')
                    ref_db_id = ref_id
                else:
                    continue
            
            # Fetch complete row from database
            full_ref = fetch_full_reference(ref_type, ref_db_id)
            if full_ref:
                selected_references.append(full_ref)
        
        except Exception as e:
            if verbose:
                log(f"[RAG] Error fetching reference {ref_id}: {e}")
            continue
    
    result = {
        "content": content,
        "references": selected_references
    }
    
    if verbose:
        result["process"] = process_steps
        result["llm_selected_ids"] = selected_ids
    
    return result


async def react_with_tools_direct(messages, user_id: str, max_iterations: int = 5):
    """
    ReAct loop with tool calling. Returns complete result as JSON.
    """
    import os
    verbose = os.getenv("VERBOSE_OUTPUT", "false").lower() == "true"
    
    all_references = []
    process_steps = []
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        if verbose:
            log(f"[AGENT] ReAct iteration {iteration}/{max_iterations}")
        
        response = await async_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=SEARCH_TOOLS,
            tool_choice="auto",
        )

        assistant_msg = response.choices[0].message
        tool_calls = assistant_msg.tool_calls or []
        
        if not tool_calls:
            if verbose:
                log(f"[AGENT] No more tool calls, ready to respond")
            messages.append(assistant_msg)
            break
        
        messages.append(assistant_msg)
        
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments or "{}")

            tool_output = await execute_search_tool(function_name, arguments, user_id)

            if tool_output.get("references"):
                all_references.extend(tool_output["references"])

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": json.dumps(tool_output, ensure_ascii=False),
            })

            result_count = len(tool_output.get("references", []))
            process_steps.append({
                "step": "tool_call",
                "tool": function_name,
                "result_count": result_count
            })

    response = await async_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
    )

    content = response.choices[0].message.content
    
    result = {
        "content": content,
        "references": all_references
    }
    
    if verbose:
        result["process"] = process_steps
    
    return result
