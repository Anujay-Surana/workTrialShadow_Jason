"""
Property-based tests for file type processing.

**Feature: retrieval-service-refactor, Property 5: File Type Processing**

Property: For any supported file type, the system should correctly extract text 
or generate a summary without errors.

Validates: Requirements 7.4
"""

import pytest
from hypothesis import given, strategies as st, settings
from retrieval_service.processing import isIMG, isDOC, process_file_by_type, SUPPORTED_EXTS
import io


# Define supported file extensions
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif", ".gif", ".jfif", ".pjpeg", ".pjp"]
DOCUMENT_EXTENSIONS = list(SUPPORTED_EXTS)


@given(
    extension=st.sampled_from(IMAGE_EXTENSIONS + DOCUMENT_EXTENSIONS),
    base_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
)
@settings(max_examples=100)
def test_file_type_detection_consistency(extension, base_name):
    """
    Property: For any filename with a supported extension, the type detection 
    functions should correctly identify it.
    
    This tests that isIMG and isDOC correctly identify file types based on extensions.
    """
    filename = f"{base_name}{extension}"
    
    # A file should be identified as either an image or a document (or neither for unsupported types)
    is_image = isIMG(filename)
    is_document = isDOC(filename)
    
    # Check consistency: if it's an image extension, isIMG should return True
    if extension in IMAGE_EXTENSIONS:
        assert is_image, f"File {filename} should be detected as an image"
        assert not is_document, f"File {filename} should not be detected as a document"
    
    # Check consistency: if it's a document extension, isDOC should return True
    if extension in DOCUMENT_EXTENSIONS:
        assert is_document, f"File {filename} should be detected as a document"
        # Note: Some extensions might overlap, so we don't assert not is_image here


@given(
    extension=st.sampled_from(IMAGE_EXTENSIONS + DOCUMENT_EXTENSIONS),
    base_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
)
@settings(max_examples=100, deadline=None)
def test_process_file_by_type_returns_string(extension, base_name):
    """
    Property: For any supported file type, process_file_by_type should return a string
    without raising an exception.
    
    This tests that the processing function handles all supported file types gracefully,
    even with minimal/empty content.
    """
    filename = f"{base_name}{extension}"
    
    # Create minimal valid file content for different types
    # For images, we can't create valid image bytes easily, so we'll use empty bytes
    # The function should handle this gracefully
    file_content = b""
    
    # The function should not raise an exception
    try:
        result = process_file_by_type(filename, file_content)
        
        # Result should be a string
        assert isinstance(result, str), f"process_file_by_type should return a string for {filename}"
        
        # Result should not be empty
        assert len(result) > 0, f"process_file_by_type should return non-empty string for {filename}"
        
    except Exception as e:
        # If an exception occurs, it should be handled gracefully
        # The function should return an error message string, not raise
        pytest.fail(f"process_file_by_type raised an exception for {filename}: {e}")


def test_process_file_by_type_unsupported_type():
    """
    Property: For unsupported file types, process_file_by_type should return 
    a descriptive message without raising an exception.
    """
    unsupported_files = [
        ("test.xyz", b"some content"),
        ("test.unknown", b"some content"),
        ("test.bin", b"some content"),
    ]
    
    for filename, content in unsupported_files:
        result = process_file_by_type(filename, content)
        
        # Should return a string
        assert isinstance(result, str)
        
        # Should indicate unsupported type
        assert "unsupported" in result.lower() or "file" in result.lower()


def test_process_file_by_type_txt_file():
    """
    Example test: TXT files should be processed correctly.
    """
    filename = "test.txt"
    content = b"This is a test text file with some content."
    
    result = process_file_by_type(filename, content)
    
    # Should return a string
    assert isinstance(result, str)
    
    # Should contain some content (summary or extracted text)
    assert len(result) > 0


def test_process_file_by_type_image_file():
    """
    Example test: Image files should be processed (even if OCR fails gracefully).
    """
    filename = "test.jpg"
    content = b""  # Empty content - OCR should handle gracefully
    
    result = process_file_by_type(filename, content)
    
    # Should return a string
    assert isinstance(result, str)
    
    # Should indicate it's an image
    assert "image" in result.lower()


def test_isIMG_case_insensitive():
    """
    Property: File type detection should be case-insensitive.
    """
    test_cases = [
        "test.JPG",
        "test.Jpg",
        "test.jpg",
        "test.JPEG",
        "test.jpeg",
        "test.PNG",
        "test.png",
    ]
    
    for filename in test_cases:
        assert isIMG(filename), f"isIMG should detect {filename} as an image (case-insensitive)"


def test_isDOC_case_insensitive():
    """
    Property: File type detection should be case-insensitive.
    """
    test_cases = [
        "test.PDF",
        "test.pdf",
        "test.DOCX",
        "test.docx",
        "test.TXT",
        "test.txt",
    ]
    
    for filename in test_cases:
        assert isDOC(filename), f"isDOC should detect {filename} as a document (case-insensitive)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
