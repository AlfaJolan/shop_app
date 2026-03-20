from __future__ import annotations

import re
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse, parse_qs

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

# 🆕 Базовые headers, чтобы запрос был больше похож на браузерный
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Connection": "close",
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


def is_google_drive_url(url: str) -> bool:
    """Проверяет, является ли ссылка ссылкой Google Drive."""
    if not url:
        return False

    parsed = urlparse(str(url).strip())
    host = (parsed.netloc or "").lower()
    return "drive.google.com" in host


def extract_google_drive_file_id(url: str) -> str:
    """
    Пытается достать file_id из популярных форматов Google Drive ссылки.

    Поддерживаемые варианты:
    - https://drive.google.com/file/d/FILE_ID/view?usp=sharing
    - https://drive.google.com/open?id=FILE_ID
    - https://drive.google.com/uc?id=FILE_ID
    """
    if not url:
        return ""

    url = str(url).strip()
    parsed = urlparse(url)

    # 🆕 Формат: /file/d/FILE_ID/...
    match = re.search(r"/file/d/([^/]+)", parsed.path)
    if match:
        return match.group(1)

    # 🆕 Формат: ?id=FILE_ID
    query = parse_qs(parsed.query)
    if "id" in query and query["id"]:
        return query["id"][0]

    return ""


def normalize_download_url(url: str) -> str:
    """
    Нормализует URL перед скачиванием.

    Сейчас:
    - если это Google Drive ссылка, превращаем ее в direct download URL
    - если это обычная ссылка, возвращаем как есть
    """
    if not is_google_drive_url(url):
        return url

    file_id = extract_google_drive_file_id(url)
    if not file_id:
        raise ValueError("Не удалось извлечь file_id из Google Drive ссылки")

    # 🆕 Прямая ссылка на скачивание файла с Google Drive
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def download_image_bytes(
    url: str,
    timeout: int = 20,
    max_size_mb: int = 10,
    retries: int = 3,
    retry_delay: float = 1.0,
) -> tuple[bytes, str]:
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

    # 🆕 Если передали Google Drive ссылку, приводим ее к прямой ссылке на скачивание
    url = normalize_download_url(url)

    max_bytes = max_size_mb * 1024 * 1024
    last_error: Exception | None = None

    # 🆕 Повторяем попытку скачивания несколько раз,
    # если сервер временно оборвал соединение или ответил нестабильно.
    for attempt in range(1, retries + 1):
        response = None
        try:
            response = requests.get(
                url,
                timeout=(10, timeout),   # 🆕 connect timeout + read timeout
                stream=True,
                headers=DEFAULT_HEADERS,
                allow_redirects=True,
            )
            response.raise_for_status()

            content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            ext = _detect_extension(url, content_type)

            if ext not in ALLOWED_IMAGE_EXTENSIONS:
                raise ValueError(f"Неподдерживаемый формат изображения: {ext or 'unknown'}")

            # 🆕 Если сервер отдает Content-Length, проверяем размер заранее
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > max_bytes:
                        raise ValueError(f"Файл слишком большой: более {max_size_mb} MB")
                except ValueError:
                    # если Content-Length битый, просто игнорируем и идем дальше по stream
                    pass

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

        except requests.RequestException as exc:
            last_error = exc

            # 🆕 Если попытки еще остались — небольшая пауза и пробуем снова
            if attempt < retries:
                time.sleep(retry_delay)
                continue

        except Exception as exc:
            last_error = exc
            break

        finally:
            if response is not None:
                response.close()

    raise ValueError(f"Не удалось скачать изображение: {last_error}")


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