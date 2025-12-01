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

def summarize_doc(text: str, filename: str, max_chars: int = 8000) -> str:
    """
    Summarize long text docs using the cheapest OpenAI model available.

    - Automatically truncates input to prevent overspending
    - Uses gpt-4o-mini which is the lowest-cost model
    """
    if not isinstance(text, str):
        raise ValueError("summarize() expects a string")

    # Safety limit: prevent sending extremely long text
    if len(text) > max_chars:
        text = text[:max_chars] + "\n...[input truncated]"

    prompt = f"Please summarize the following extracted file named {filename} in a concise way (only first {max_chars} chars are shown), starting with 'A(n) XXXX file ...':\n\n{text}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",   # Cheapest high-quality model
        messages=[
            {"role": "system", "content": "You are a concise summarization assistant."},
            {"role": "user", "content": prompt},
        ]
    )

    return response.choices[0].message.content.strip()
