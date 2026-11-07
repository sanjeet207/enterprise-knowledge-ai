"""Turn an uploaded file into plain text. PDF and Word readers are imported only when needed."""
import io
import os

MAX_BYTES = 5 * 1024 * 1024
MAX_CHARS = 500_000
ALLOWED = {".txt", ".md", ".csv", ".pdf", ".docx"}


class ExtractError(ValueError):
    """The file cannot be used. The message is safe to show to the person uploading."""


def extension(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


def extract_text(filename: str, data: bytes) -> str:
    ext = extension(filename)
    if ext not in ALLOWED:
        raise ExtractError("Unsupported file type. Upload .pdf, .docx, .txt, .md or .csv")
    if not data:
        raise ExtractError("The file is empty")
    if len(data) > MAX_BYTES:
        raise ExtractError("The file is larger than 5 MB")
    if ext == ".pdf":
        text = _pdf(data)
    elif ext == ".docx":
        text = _docx(data)
    else:
        text = _plain(data)
    text = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip()
    if not text:
        raise ExtractError("No readable text found (a scanned PDF needs OCR first)")
    if len(text) > MAX_CHARS:
        raise ExtractError("The document has too much text (limit 500,000 characters)")
    return text


def _plain(data: bytes) -> str:
    if b"\x00" in data[:4096]:
        raise ExtractError("This does not look like a text file")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _pdf(data: bytes) -> str:
    if not data.startswith(b"%PDF"):
        raise ExtractError("This is not a valid PDF")
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ExtractError("The PDF is password protected")
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except ExtractError:
        raise
    except Exception:
        raise ExtractError("Could not read this PDF")


def _docx(data: bytes) -> str:
    if not data.startswith(b"PK"):
        raise ExtractError("This is not a valid Word document")
    try:
        from docx import Document
        document = Document(io.BytesIO(data))
        lines = [p.text for p in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                lines.append(" | ".join(cell.text.strip() for cell in row.cells))
        return "\n".join(lines)
    except Exception:
        raise ExtractError("Could not read this Word document")
