# app/utils/file_uploads.py
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


MAX_PDF_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_FILES_PER_REQUEST = 3

PDF_MIME_TYPES = {
    "application/pdf",
}
PDF_SIGNATURE = b"%PDF-"


class FileValidationError(Exception):
    pass


async def read_upload_limited(file: UploadFile, max_size: int) -> bytes:
    chunk_size = 1024 * 1024  # 1 MB
    total = 0
    chunks: list[bytes] = []

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break

        total += len(chunk)
        if total > max_size:
            raise FileValidationError(
                f"Файл слишком большой. Максимум: {max_size // (1024 * 1024)} МБ."
            )

        chunks.append(chunk)

    data = b"".join(chunks)
    await file.seek(0)
    return data


def validate_files_count(files: list[UploadFile], max_files: int = MAX_FILES_PER_REQUEST) -> None:
    if not files:
        raise FileValidationError("Файлы не выбраны.")

    if len(files) > max_files:
        raise FileValidationError(f"Можно загрузить не более {max_files} PDF-файлов за раз.")


def validate_pdf_bytes(
    *,
    filename: str | None,
    content_type: str | None,
    data: bytes,
) -> None:
    name = (filename or "").strip()

    if not name:
        raise FileValidationError("Файл не выбран.")

    if not name.lower().endswith(".pdf"):
        raise FileValidationError("Можно загрузить только PDF-файлы.")

    if content_type not in PDF_MIME_TYPES:
        raise FileValidationError("Неверный тип файла. Ожидается PDF.")

    if not data:
        raise FileValidationError("Файл пустой.")

    if not data.startswith(PDF_SIGNATURE):
        raise FileValidationError("Файл не похож на корректный PDF.")

    # мягкая дополнительная проверка структуры
    if b"%%EOF" not in data[-4096:]:
        raise FileValidationError("PDF повреждён или загружен не полностью.")


def build_pdf_filename() -> str:
    return f"{uuid4().hex}.pdf"


async def validate_and_read_pdf(file: UploadFile) -> bytes:
    data = await read_upload_limited(file, MAX_PDF_SIZE)
    validate_pdf_bytes(
        filename=file.filename,
        content_type=file.content_type,
        data=data,
    )
    return data


def save_bytes_to_path(data: bytes, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)