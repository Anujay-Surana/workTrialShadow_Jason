"""
OCR utilities for text extraction from images.

This module provides OCR (Optical Character Recognition) functionality
using EasyOCR to extract text from various image formats.
"""

import io
import easyocr
from retrieval_service.infrastructure.logging import log_debug, log_info, log_error

# Global OCR reader instance (initialized once)
_reader = None


def isIMG(filename: str) -> bool:
    """
    Check whether a filename has a common image extension.
    Supports many typical image formats.
    
    Args:
        filename: Name of the file to check
        
    Returns:
        bool: True if filename has an image extension, False otherwise
    """
    if not isinstance(filename, str):
        return False

    img_exts = {
        ".jpg", ".jpeg", ".png", ".bmp",
        ".webp", ".tiff", ".tif",
        ".gif", ".jfif", ".pjpeg", ".pjp"
    }

    lower = filename.lower()
    return any(lower.endswith(ext) for ext in img_exts)


def init_model(langs=['en']):
    """
    Initialize the OCR model.
    Call this once at program startup to avoid slow first-time loading
    inside API request handlers.
    
    Args:
        langs: List of language codes to support (default: ['en'])
    """
    global _reader
    if _reader is None:
        log_info("[OCR] Initializing EasyOCR model...")
        _reader = easyocr.Reader(langs)  # load model only once
        log_info("[OCR] Model initialized successfully")


def extractOCR(img_bytes: bytes) -> str:
    """
    Extract text from image bytes.
    
    Args:
        img_bytes: Raw bytes of the image file
        
    Returns:
        str: Extracted text from the image, with lines joined by newlines
    """
    global _reader
    if _reader is None:
        log_debug("[OCR] Reader not initialized, initializing with default language...")
        _reader = easyocr.Reader(['en'])

    # Skip very small images (likely decorative elements like bullets, spacers)
    if len(img_bytes) < 100:  # Less than 100 bytes
        log_debug("[OCR] Skipping very small image (likely decorative)")
        return ""
    
    try:
        log_debug("[OCR] Extracting text from image...")
        result = _reader.readtext(img_bytes, detail=0)
        log_debug(f"[OCR] Extracted {len(result)} text segments")
        return "\n".join(result)
    except Exception as e:
        # Silently skip images that can't be processed (corrupted, empty, etc.)
        log_debug(f"[OCR] Could not process image: {e}")
        return ""
