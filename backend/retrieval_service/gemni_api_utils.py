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
):
    """
    Generate a text embedding using Gemini.

    Args:
        text (str): Input text.
        model (str): Gemini embedding model.
        dim (int): Output dimensionality (e.g., 768, 1536, 3072).

    Returns:
        list: Embedding vector.
    """

    result = genai.embed_content(
        model=model,
        content=text,
        output_dimensionality=dim,
    )

    return result["embedding"]