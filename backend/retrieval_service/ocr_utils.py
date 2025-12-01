# ocr_utils.py
import io
import easyocr

# Global OCR reader instance (initialized once)
_reader = None


def isIMG(filename: str) -> bool:
    """
    Check whether a filename has a common image extension.
    Supports many typical image formats.
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
    """
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(langs)  # load model only once


def extractOCR(img_bytes: bytes) -> str:
    """
    Extract text from image bytes.
    """
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(['en'])

    result = _reader.readtext(img_bytes, detail=0)

    return "\n".join(result)

