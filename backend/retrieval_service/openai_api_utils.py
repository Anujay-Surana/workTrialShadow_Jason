# openai_api_utils.py
import os
from typing import List
from dotenv import load_dotenv
from openai import OpenAI, AsyncOpenAI
from retrieval_service.agent import SEARCH_TOOLS
from retrieval_service.search_utils import execute_search_tool
import json

# Load API key from .env file
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables or .env file")

# Initialize OpenAI clients (sync for non-streaming, async for streaming)
client = OpenAI(api_key=OPENAI_API_KEY)
async_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


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


async def chat_stream(messages: list, model: str = "gpt-4o"):
    """
    Stream chat completions using GPT-4o (async).
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model to use (default: gpt-4o)
    
    Yields:
        str: Token chunks as they arrive
    """
    stream = await async_client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        temperature=0.7,
    )
    
    async for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            yield chunk.choices[0].delta.content

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
        print(f"[WARNING] File {filename} exceeds {max_chars} chars, truncating to limit")
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
    print(f"[INFO] File {filename} is large ({len(text)} chars), using chunked summarization")
    
    # Step 1: Split into chunks
    chunks = chunk_text(text, chunk_size=chunk_size)
    print(f"[INFO] Split into {len(chunks)} chunks")
    
    # Step 2: Summarize each chunk (map)
    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        try:
            summary = summarize_chunk(chunk, i, len(chunks))
            chunk_summaries.append(summary)
            print(f"[INFO] Summarized chunk {i+1}/{len(chunks)}")
        except Exception as e:
            print(f"[ERROR] Failed to summarize chunk {i+1}: {e}")
            chunk_summaries.append(f"[Error summarizing section {i+1}]")
    
    # Step 3: Combine summaries (reduce)
    final_summary = combine_summaries(chunk_summaries, filename)
    print(f"[INFO] Created final summary for {filename}")
    
    return final_summary

async def rag_direct_stream(messages, user_id: str, user_message: str, user_info: dict):
    """
    Direct RAG mode: Perform retrieval first, then stream response.
    This is simpler and more reliable than ReAct agent mode.
    """
    from retrieval_service.rag_utils import combined_search, build_rag_prompt
    
    # Step 1: Contextualize the query if there's conversation history
    search_query = user_message
    
    # Check if there are previous messages (excluding system message)
    previous_messages = [m for m in messages if m.get("role") in ["user", "assistant"]]
    
    if len(previous_messages) > 1:  # Has history beyond current message
        # Create a contextual query that incorporates conversation history
        try:
            contextualization_prompt = f"""Given the conversation history and the latest user question, 
rewrite the question to be a standalone search query that includes necessary context from the conversation.
Do not answer the question, just rewrite it as a clear search query.

Conversation history:
{chr(10).join([f"{m['role']}: {m['content'][:200]}" for m in previous_messages[:-1]])}

Latest question: {user_message}

Standalone search query:"""
            
            contextualization_response = await async_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": contextualization_prompt}],
                temperature=0.0,
            )
            
            search_query = contextualization_response.choices[0].message.content.strip()
            print(f"[RAG] Contextualized query: {user_message} -> {search_query}")
            
        except Exception as e:
            print(f"[RAG] Error contextualizing query, using original: {e}")
            search_query = user_message
    
    # Step 2: Perform combined search with contextualized query
    yield {
        "type": "search_start",
        "message": "Searching your data..."
    }
    
    try:
        context, references, raw_results = combined_search(
            user_id=user_id,
            query=search_query,
            top_k=5
        )
        
        yield {
            "type": "search_end",
            "result_count": len(references)
        }
        
    except Exception as e:
        print(f"[RAG] Search error: {e}")
        context = ""
        references = []
    
    # Signal that we're about to start generating response
    yield {
        "type": "generation_start",
        "message": "Generating response..."
    }
    
    # Step 3: Build RAG prompt with context
    rag_prompt = build_rag_prompt(user_message, context, user_info)
    
    # Replace the last user message with the RAG-enhanced prompt
    messages_copy = messages[:-1]  # Remove last user message
    messages_copy.append({"role": "user", "content": rag_prompt})
    
    # Step 3: Stream response
    stream = await async_client.chat.completions.create(
        model="gpt-4o",
        messages=messages_copy,
        stream=True,
        temperature=0.7,
    )
    
    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield {
                "type": "content",
                "content": delta.content,
            }
    
    # Step 4: Send references
    if references:
        yield {
            "type": "references",
            "references": references
        }
    
    yield {"type": "done"}


async def react_with_tools_stream(messages, user_id: str, max_iterations: int = 5):
    """
    Persistent ReAct loop that keeps trying until it gets results or reaches max iterations.
    """
    all_references = []
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        print(f"[AGENT] ReAct iteration {iteration}/{max_iterations}")
        
        # ---------- Step: Call model with tools ----------
        response = await async_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=SEARCH_TOOLS,
            tool_choice="auto",
        )

        assistant_msg = response.choices[0].message
        tool_calls = assistant_msg.tool_calls or []
        
        # If no tool calls, model is ready to respond
        if not tool_calls:
            print(f"[AGENT] No more tool calls, ready to respond")
            messages.append(assistant_msg)
            break
        
        # ---------- Execute tool calls ----------
        messages.append(assistant_msg)
        
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments or "{}")

            # Send tool call start event
            yield {
                "type": "tool_call_start",
                "tool": function_name,
                "query": arguments.get('query', ''),
                "search_types": arguments.get('search_types', [])
            }

            # Real tool execution
            tool_output = await execute_search_tool(function_name, arguments, user_id)

            # Collect references
            if tool_output.get("references"):
                all_references.extend(tool_output["references"])

            # Send tool result back to model
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": json.dumps(tool_output, ensure_ascii=False),
            })

            # Send tool call end event
            result_count = len(tool_output.get("references", []))
            yield {
                "type": "tool_call_end",
                "tool": function_name,
                "result_count": result_count
            }
        
        # Loop continues - model can decide to call more tools or respond

    # ---------- Final: Stream the response ----------
    stream = await async_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield {
                "type": "content",
                "content": delta.content,
            }

    if all_references:
        yield {
            "type": "references",
            "references": all_references
        }

    yield {"type": "done"}
