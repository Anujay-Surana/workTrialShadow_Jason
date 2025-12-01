# gemeni_api_utils.py

import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Initialize Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def embed_text(
    text: str,
    model: str = "gemini-embedding-001",
    dim: int = 1536,
    max_retries: int = 3,
):
    """
    Generate a text embedding using Gemini with retry logic.

    Args:
        text (str): Input text.
        model (str): Gemini embedding model.
        dim (int): Output dimensionality (e.g., 768, 1536, 3072).
        max_retries (int): Maximum number of retry attempts.

    Returns:
        list: Embedding vector.
    """
    import time
    
    for attempt in range(max_retries):
        try:
            result = genai.embed_content(
                model=model,
                content=text,
                output_dimensionality=dim,
            )
            return result["embedding"]
        except Exception as e:
            error_str = str(e)
            # Check if it's a retryable error (timeout, rate limit, server error)
            is_retryable = any(code in error_str for code in ["504", "503", "429", "500", "Deadline", "timeout", "Too Many Requests"])
            
            if attempt < max_retries - 1 and is_retryable:
                # Exponential backoff: 1s, 2s, 4s
                wait_time = 1 * (2 ** attempt)
                print(f"Gemini API error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                # Non-retryable error or final attempt
                print(f"Gemini API error after {max_retries} attempts: {e}")
                raise
    
    raise Exception("Failed to embed text after all retries")
