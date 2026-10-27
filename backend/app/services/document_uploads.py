import codecs
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from fastapi import UploadFile

ALLOWED_DOCUMENT_TYPES: dict[str, frozenset[str]] = {
    ".pdf": frozenset({"application/pdf"}),
    ".docx": frozenset({"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}),
    ".txt": frozenset({"text/plain"}),
    ".md": frozenset({"text/markdown", "text/plain"}),
    ".html": frozenset({"text/html"}),
}
TEXT_EXTENSIONS = frozenset({".txt", ".md", ".html"})
READ_CHUNK_SIZE = 1024 * 1024


class UploadValidationError(ValueError):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    filename: str
    content_type: str
    size: int


def _safe_filename(filename: str | None) -> str:
    normalized = (filename or "").replace("\\", "/")
    safe_name = Path(normalized).name.strip()
    if not safe_name or len(safe_name) > 512:
        raise UploadValidationError("A valid filename of at most 512 characters is required")
    return safe_name


def _validate_docx(file: UploadFile) -> None:
    try:
        file.file.seek(0)
        with ZipFile(file.file) as archive:
            names = set(archive.namelist())
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise UploadValidationError("The uploaded file is not a valid DOCX document")
    except (BadZipFile, OSError) as exc:
        raise UploadValidationError("The uploaded file is not a valid DOCX document") from exc
    finally:
        file.file.seek(0)


async def validate_document_upload(file: UploadFile, max_size_bytes: int) -> ValidatedUpload:
    filename = _safe_filename(file.filename)
    extension = Path(filename).suffix.lower()
    allowed_mime_types = ALLOWED_DOCUMENT_TYPES.get(extension)
    if allowed_mime_types is None:
        raise UploadValidationError(
            "Unsupported file type. Allowed types: PDF, DOCX, TXT, MD, HTML",
            status_code=415,
        )

    content_type = (file.content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if content_type not in allowed_mime_types:
        raise UploadValidationError(
            f"MIME type '{content_type or 'missing'}' does not match {extension}",
            status_code=415,
        )

    total_size = 0
    first_bytes = b""
    decoder = codecs.getincrementaldecoder("utf-8")() if extension in TEXT_EXTENSIONS else None
    await file.seek(0)
    try:
        while chunk := await file.read(READ_CHUNK_SIZE):
            if not first_bytes:
                first_bytes = chunk[:8]
            total_size += len(chunk)
            if total_size > max_size_bytes:
                raise UploadValidationError(
                    f"File exceeds the maximum size of {max_size_bytes // (1024 * 1024)} MB",
                    status_code=413,
                )
            if decoder is not None:
                decoder.decode(chunk)
        if decoder is not None:
            decoder.decode(b"", final=True)
    except UnicodeDecodeError as exc:
        raise UploadValidationError("Text documents must use UTF-8 encoding") from exc
    finally:
        await file.seek(0)

    if total_size == 0:
        raise UploadValidationError("The uploaded file is empty")
    if extension == ".pdf" and not first_bytes.startswith(b"%PDF-"):
        raise UploadValidationError("The uploaded file is not a valid PDF document")
    if extension == ".docx":
        _validate_docx(file)

    return ValidatedUpload(filename=filename, content_type=content_type, size=total_size)
