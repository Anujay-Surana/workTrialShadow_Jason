"""
Document Processing Utilities
Handles document summarization, chunking, and text processing using OpenAI API.
"""

from openai import OpenAI
import os
from dotenv import load_dotenv
from retrieval_service.infrastructure.logging import log_debug, log_info, log_warning, log_error

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


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
    
    log_debug(f"[Documents] Split text into {len(chunks)} chunks")
    return chunks


def summarize_chunk(chunk: str, chunk_index: int, total_chunks: int) -> str:
    """
    Summarize a single chunk of text using OpenAI API.
    
    Args:
        chunk: Text chunk to summarize
        chunk_index: Index of this chunk (0-based)
        total_chunks: Total number of chunks
    
    Returns:
        Summary of the chunk
    """
    prompt = f"Summarize this section (part {chunk_index + 1} of {total_chunks}):\n\n{chunk}"
    
    log_debug(f"[Documents] Summarizing chunk {chunk_index + 1}/{total_chunks}")
    
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
    Combine multiple chunk summaries into one final summary using OpenAI API.
    
    Args:
        summaries: List of chunk summaries
        filename: Name of the original file
    
    Returns:
        Final combined summary
    """
    combined_text = "\n\n".join([f"Section {i+1}: {summary}" for i, summary in enumerate(summaries)])
    
    prompt = f"Combine these section summaries of the file '{filename}' into one cohesive summary. Start with 'A(n) [file type] file...':\n\n{combined_text}"
    
    log_debug(f"[Documents] Combining {len(summaries)} summaries for {filename}")
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a summarization assistant. Create a unified summary from multiple parts."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    
    return response.choices[0].message.content.strip()


def summarize(text: str, max_chars: int = 8000) -> str:
    """
    Summarize long text using OpenAI API (gpt-4o-mini).

    - Automatically truncates input to prevent overspending
    - Uses gpt-4o-mini which is the lowest-cost model
    
    Args:
        text: Text to summarize
        max_chars: Maximum characters to process
        
    Returns:
        Summary text
        
    Raises:
        ValueError: If text is not a string
    """
    if not isinstance(text, str):
        raise ValueError("summarize() expects a string")

    # Safety limit: prevent sending extremely long text
    if len(text) > max_chars:
        log_warning(f"[Documents] Text exceeds {max_chars} chars, truncating")
        text = text[:max_chars] + "\n...[input truncated]"

    prompt = f"Please summarize the following content in a concise way (only first {max_chars} chars are shown):\n\n{text}"

    log_debug("[Documents] Generating summary with OpenAI")
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a concise summarization assistant."},
            {"role": "user", "content": prompt},
        ]
    )

    return response.choices[0].message.content.strip()


def summarize_doc(text: str, filename: str, max_chars: int = 30000, chunk_size: int = 6000) -> str:
    """
    Summarize long text docs using map-reduce approach with chunking and OpenAI API.
    
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
        
    Raises:
        ValueError: If text is not a string
    """
    if not isinstance(text, str):
        raise ValueError("summarize_doc() expects a string")
    
    # Safety limit: prevent processing extremely long text
    if len(text) > max_chars:
        log_warning(f"[Documents] File {filename} exceeds {max_chars} chars, truncating to limit")
        text = text[:max_chars]
    
    # If text is small enough, summarize directly
    if len(text) <= chunk_size:
        prompt = f"Please summarize this file named '{filename}' concisely, starting with 'A(n) [file type] file...':\n\n{text}"
        
        log_debug(f"[Documents] Summarizing {filename} directly (small file)")
        
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
    log_info(f"[Documents] File {filename} is large ({len(text)} chars), using chunked summarization")
    
    # Step 1: Split into chunks
    chunks = chunk_text(text, chunk_size=chunk_size)
    log_info(f"[Documents] Split into {len(chunks)} chunks")
    
    # Step 2: Summarize each chunk (map)
    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        try:
            summary = summarize_chunk(chunk, i, len(chunks))
            chunk_summaries.append(summary)
            log_info(f"[Documents] Summarized chunk {i+1}/{len(chunks)}")
        except Exception as e:
            log_error(f"[Documents] Failed to summarize chunk {i+1}: {e}")
            chunk_summaries.append(f"[Error summarizing section {i+1}]")
    
    # Step 3: Combine summaries (reduce)
    final_summary = combine_summaries(chunk_summaries, filename)
    log_info(f"[Documents] Created final summary for {filename}")
    
    return final_summary
