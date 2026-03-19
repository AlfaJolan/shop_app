from __future__ import annotations

import uuid
from pathlib import Path
from urllib.parse import urlparse

import requests


UPLOAD_DIR = Path("app/static/uploads/products")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
CONTENT_TYPE_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def extract_youtube_id(url: str) -> str:
    """Вытаскивает YouTube video id из разных форматов ссылки."""
    if not url:
        return ""

    url = url.strip()

    if "v=" in url:
        return url.split("v=")[-1].split("&")[0]

    if "youtu.be/" in url:
        return url.split("youtu.be/")[-1].split("?")[0]

    if "/shorts/" in url:
        return url.split("/shorts/")[-1].split("?")[0]

    return url


def download_image_bytes(url: str, timeout: int = 20, max_size_mb: int = 10) -> tuple[bytes, str]:
    """
    Скачивает изображение по URL.
    Возвращает:
      - bytes контента
      - расширение файла (например, '.jpg')

    Проверяет:
      - статус ответа
      - content-type
      - размер файла
    """
    if not url or not str(url).strip():
        raise ValueError("Пустой URL изображения")

    url = str(url).strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError("URL изображения должен начинаться с http:// или https://")

    response = requests.get(url, timeout=timeout, stream=True)
    response.raise_for_status()

    content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    ext = _detect_extension(url, content_type)

    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f"Неподдерживаемый формат изображения: {ext or 'unknown'}")

    max_bytes = max_size_mb * 1024 * 1024
    chunks: list[bytes] = []
    total_size = 0

    for chunk in response.iter_content(chunk_size=8192):
        if not chunk:
            continue
        total_size += len(chunk)
        if total_size > max_bytes:
            raise ValueError(f"Файл слишком большой: более {max_size_mb} MB")
        chunks.append(chunk)

    content = b"".join(chunks)
    if not content:
        raise ValueError("Пустой файл изображения")

    return content, ext


def save_main_image_bytes(content: bytes, ext: str) -> str:
    """
    Сохраняет главное фото товара в app/static/uploads/products
    и возвращает имя файла для Product.image.
    """
    ext = _normalize_extension(ext)
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(content)
    return filename


def save_gallery_image_bytes(product_id: int, content: bytes, ext: str) -> str:
    """
    Сохраняет фото галереи в app/static/uploads/products/{product_id}/gallery
    и возвращает имя файла для ProductImage.image_url.
    """
    ext = _normalize_extension(ext)
    gallery_dir = UPLOAD_DIR / str(product_id) / "gallery"
    gallery_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = gallery_dir / filename
    filepath.write_bytes(content)
    return filename


def delete_main_image_file(filename: str | None) -> None:
    """Удаляет главное фото товара, если файл существует."""
    if not filename:
        return

    filepath = UPLOAD_DIR / filename
    try:
        if filepath.exists():
            filepath.unlink()
    except Exception:
        pass


def delete_gallery_image_file(product_id: int, filename: str | None) -> None:
    """Удаляет файл из галереи товара, если файл существует."""
    if not filename:
        return

    filepath = UPLOAD_DIR / str(product_id) / "gallery" / filename
    try:
        if filepath.exists():
            filepath.unlink()
    except Exception:
        pass


def clear_product_gallery_dir(product_id: int) -> None:
    """Удаляет все файлы из папки галереи товара."""
    gallery_dir = UPLOAD_DIR / str(product_id) / "gallery"
    if not gallery_dir.exists():
        return

    for item in gallery_dir.iterdir():
        try:
            if item.is_file():
                item.unlink()
        except Exception:
            pass


def _detect_extension(url: str, content_type: str) -> str:
    """
    Определяет расширение файла:
    1. сначала по Content-Type
    2. если не нашли — по URL
    """
    if content_type in CONTENT_TYPE_TO_EXT:
        return CONTENT_TYPE_TO_EXT[content_type]

    parsed = urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    return _normalize_extension(ext)


def _normalize_extension(ext: str) -> str:
    if not ext:
        return ".jpg"

    ext = ext.lower().strip()
    if not ext.startswith("."):
        ext = f".{ext}"

    if ext == ".jpeg":
        return ".jpg"

    return ext