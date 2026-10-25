from io import BytesIO
from zipfile import ZipFile

import pytest
from starlette.datastructures import Headers, UploadFile

from app.services.document_uploads import UploadValidationError, validate_document_upload


def make_upload(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
async def test_validates_pdf_signature_and_size() -> None:
    upload = make_upload("source.pdf", b"%PDF-1.7\ncontent", "application/pdf")

    validated = await validate_document_upload(upload, max_size_bytes=1024)

    assert validated.filename == "source.pdf"
    assert validated.size == 16


@pytest.mark.asyncio
async def test_rejects_extension_mime_mismatch() -> None:
    upload = make_upload("source.pdf", b"%PDF-1.7\n", "text/plain")

    with pytest.raises(UploadValidationError, match="does not match") as error:
        await validate_document_upload(upload, max_size_bytes=1024)

    assert error.value.status_code == 415


@pytest.mark.asyncio
async def test_rejects_oversized_upload() -> None:
    upload = make_upload("notes.txt", b"too large", "text/plain")

    with pytest.raises(UploadValidationError, match="maximum size") as error:
        await validate_document_upload(upload, max_size_bytes=4)

    assert error.value.status_code == 413


@pytest.mark.asyncio
async def test_accepts_structurally_valid_docx() -> None:
    content = BytesIO()
    with ZipFile(content, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
    upload = make_upload(
        "source.docx",
        content.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    validated = await validate_document_upload(upload, max_size_bytes=4096)

    assert validated.filename == "source.docx"
