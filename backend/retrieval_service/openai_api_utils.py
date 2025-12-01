# openai_api_utils.py
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load API key from .env file
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables or .env file")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


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


def chat_stream(messages: list, model: str = "gpt-4o"):
    """
    Stream chat completions using GPT-4o.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model to use (default: gpt-4o)
    
    Yields:
        str: Token chunks as they arrive
    """
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        temperature=0.7,
    )
    
    for chunk in stream:
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
