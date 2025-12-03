"""
Processing module for document and image processing.

This module provides a unified interface for:
- OCR text extraction from images
- Document parsing from various formats
- Document summarization and chunking
"""

from .ocr import isIMG, init_model, extractOCR
from .parsers import isDOC, extractDOC, SUPPORTED_EXTS
from .documents import summarize, summarize_doc, chunk_text
from retrieval_service.infrastructure.logging import log_error


def process_file_by_type(file_name: str, file_content: bytes) -> str:
    """
    Process file content and return summary.
    
    This function automatically detects the file type and applies the appropriate
    processing method (OCR for images, parsing + summarization for documents).
    
    Args:
        file_name: Name of the file
        file_content: Raw bytes content of the file
    
    Returns:
        str: Summary of the file content
    """
    if isIMG(file_name):
        try:
            text = extractOCR(file_content)
            return "An image with following extracted text: " + text if text else "An image file with no extractable text."
        except Exception as e:
            log_error(f"Error processing image {file_name}: {e}")
            return "An image file with no extractable text."
    if isDOC(file_name):
        try:
            text = extractDOC(file_content, filename=file_name)
            return summarize_doc(text, filename=file_name)
        except Exception as e:
            log_error(f"Error processing document {file_name}: {e}")
            return "A document file with no extractable text."
    return "A file of unsupported type for extraction named `" + file_name + "`."


__all__ = [
    # OCR functions
    'isIMG',
    'init_model',
    'extractOCR',
    
    # Parser functions
    'isDOC',
    'extractDOC',
    'SUPPORTED_EXTS',
    
    # Document functions
    'summarize',
    'summarize_doc',
    'chunk_text',
    
    # Unified interface
    'process_file_by_type',
]
