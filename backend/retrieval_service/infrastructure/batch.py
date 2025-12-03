"""
Batch Processing Utilities
Optimizes API calls by batching requests with timeout support
"""

from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
import os
from dotenv import load_dotenv
from .logging import log_debug, log_info, log_warning, log_error
from .monitoring import monitor

load_dotenv()


# Dynamic batching removed - caused event loop conflicts in sync contexts


async def batch_embed_gemini(texts: List[str], model: str = "models/gemini-embedding-001", dim: int = 1536, batch_size: int = 100) -> List[List[float]]:
    """
    Batch embed texts using Gemini API with gemini-embedding-001 (1536 dimensions)
    
    Gemini API has limits on batch size, so we split large requests into smaller batches.
    
    Args:
        texts: List of texts to embed
        model: Gemini embedding model (default: gemini-embedding-001)
        dim: Output dimensionality (default: 1536)
        batch_size: Maximum texts per API call (default: 100)
    
    Returns:
        List of embedding vectors (each 1536 dimensions)
    """
    if not texts:
        return []
    
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    
    all_embeddings = []
    
    # Process in batches to avoid API limits
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        
        try:
            result = genai.embed_content(
                model=model,
                content=batch,
                task_type="retrieval_document",
                output_dimensionality=dim
            )
            
            # Handle both single and batch results
            if isinstance(result['embedding'][0], list):
                # Batch result
                all_embeddings.extend(result['embedding'])
            else:
                # Single result
                all_embeddings.append(result['embedding'])
            
            monitor.log_request('gemini', 'embeddings', 'success', 0)
            log_debug(f"Embedded batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size} ({len(batch)} texts)")
            
        except Exception as e:
            log_error(f"Error in batch embedding (batch {i//batch_size + 1}): {e}")
            monitor.log_request('gemini', 'embeddings', 'error', 1)
            raise
    
    return all_embeddings


def batch_insert_supabase(table: Any, records: List[Dict], batch_size: int = 1000, max_retries: int = 3) -> None:
    """
    Batch insert records into Supabase with retry logic
    
    Args:
        table: Supabase table object
        records: List of records to insert
        batch_size: Records per batch
        max_retries: Maximum retry attempts per batch
    """
    import time
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(records) + batch_size - 1) // batch_size
        
        for attempt in range(max_retries):
            try:
                table.insert(batch).execute()
                monitor.log_request('supabase', 'insert', 'success', attempt)
                log_debug(f"Inserted batch {batch_num}/{total_batches} ({len(batch)} records)")
                break  # Success, move to next batch
                
            except Exception as e:
                error_str = str(e)
                is_retryable = any(keyword in error_str.lower() for keyword in [
                    'server disconnected', 'timeout', 'connection', 'network',
                    'temporarily unavailable', '503', '504', '429'
                ])
                
                if attempt < max_retries - 1 and is_retryable:
                    wait_time = 2 * (2 ** attempt)  # 2s, 4s, 8s
                    log_warning(f"Supabase insert error (batch {batch_num}/{total_batches}, attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                    monitor.log_request('supabase', 'insert', 'retry', attempt)
                    time.sleep(wait_time)
                else:
                    log_error(f"Supabase insert failed after {max_retries} attempts (batch {batch_num}/{total_batches}): {e}")
                    monitor.log_request('supabase', 'insert', 'error', attempt)
                    raise
