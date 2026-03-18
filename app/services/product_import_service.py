from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Category, Product, Seller, Variant


SHEET_NAME = "products_import"

# Это не "обязательные к заполнению" поля,
# а обязательные колонки, которые должны существовать в шаблоне Excel.
REQUIRED_HEADERS = [
    "product_sku",
    "product_name",
    "product_description",
    "category_name",
    "seller_name",
    "seller_city",
    "unit",
    "main_image_url",
    "gallery_urls",
    "youtube_url",
    "variant_name",
    "pack_size",
    "cost_price",
    "sale_price",
    "stock",
    "is_active",
]


@dataclass
class ImportErrorItem:
    row: int
    message: str


@dataclass
class ImportResult:
    rows_total: int = 0
    rows_success: int = 0
    rows_failed: int = 0
    products_created: int = 0
    products_updated: int = 0
    variants_created: int = 0
    variants_updated: int = 0
    categories_created: int = 0
    sellers_created: int = 0
    media_skipped: int = 0
    errors: list[ImportErrorItem] = field(default_factory=list)

    def add_error(self, row: int, message: str) -> None:
        self.rows_failed += 1
        self.errors.append(ImportErrorItem(row=row, message=message))


@dataclass
class ParsedRow:
    product_sku: str
    product_name: str
    product_description: str | None
    category_name: str
    seller_name: str
    seller_city: str | None
    unit: str
    main_image_url: str | None
    gallery_urls: list[str]
    youtube_url: str | None
    variant_name: str
    pack_size: int
    cost_price: Decimal
    sale_price: Decimal
    stock: int
    is_active: bool


class ProductImportService:
    """
    Первая версия сервиса импорта.

    Что делает:
    - читает Excel `products_import`
    - создает/обновляет Category
    - создает/обновляет Seller
    - создает/обновляет Product по SKU
    - создает/обновляет Variant по (product_id, variant_name, pack_size)

    Что пока НЕ делает:
    - не скачивает картинки
    - не сохраняет ProductImage
    - не сохраняет ProductVideo
    - только считает, что media-поля были переданы
    """

    def __init__(self, db: Session):
        self.db = db
        self._category_cache: dict[str, Category] = {}
        self._seller_cache: dict[str, Seller] = {}
        self._product_cache: dict[str, Product] = {}

    def import_from_upload(self, upload_file) -> ImportResult:
        content = upload_file.file.read()
        return self.import_from_bytes(content)

    def import_from_bytes(self, content: bytes) -> ImportResult:
        result = ImportResult()
        wb = load_workbook(filename=BytesIO(content), data_only=True)

        if SHEET_NAME not in wb.sheetnames:
            raise ValueError(f"Лист '{SHEET_NAME}' не найден в Excel-файле")

        ws = wb[SHEET_NAME]
        header_map = self._read_headers(ws)

        missing_headers = [h for h in REQUIRED_HEADERS if h not in header_map]
        if missing_headers:
            raise ValueError(
                "В Excel отсутствуют обязательные колонки: " + ", ".join(missing_headers)
            )

        seen_variant_keys: set[tuple[str, str, int]] = set()

        for row_idx in range(2, ws.max_row + 1):
            raw = self._row_to_dict(ws, row_idx, header_map)

            if self._is_empty_row(raw):
                continue

            result.rows_total += 1

            try:
                row = self._parse_and_validate_row(raw)

                variant_key = (
                    row.product_sku.casefold(),
                    row.variant_name.casefold(),
                    row.pack_size,
                )
                if variant_key in seen_variant_keys:
                    raise ValueError(
                        "Дубликат варианта внутри файла: одинаковые product_sku + variant_name + pack_size"
                    )
                seen_variant_keys.add(variant_key)

                category, category_created = self._get_or_create_category(row.category_name)
                seller, seller_created = self._get_or_create_seller(row.seller_name, row.seller_city)
                product, product_created = self._get_or_create_product(row, category.id, seller.id)
                _, variant_created = self._get_or_create_variant(product.id, row)

                if category_created:
                    result.categories_created += 1
                if seller_created:
                    result.sellers_created += 1
                if product_created:
                    result.products_created += 1
                else:
                    result.products_updated += 1
                if variant_created:
                    result.variants_created += 1
                else:
                    result.variants_updated += 1

                if row.main_image_url:
                    result.media_skipped += 1
                if row.gallery_urls:
                    result.media_skipped += len(row.gallery_urls)
                if row.youtube_url:
                    result.media_skipped += 1

                self.db.commit()
                result.rows_success += 1

            except Exception as exc:
                self.db.rollback()
                result.add_error(row_idx, str(exc))

        return result

    def _read_headers(self, ws) -> dict[str, int]:
        header_map: dict[str, int] = {}

        for col_idx in range(1, ws.max_column + 1):
            cell_value = ws.cell(row=1, column=col_idx).value
            if cell_value is None:
                continue

            normalized = self._normalize_header(str(cell_value))
            if normalized:
                header_map[normalized] = col_idx

        return header_map

    def _row_to_dict(self, ws, row_idx: int, header_map: dict[str, int]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for header, col_idx in header_map.items():
            data[header] = ws.cell(row=row_idx, column=col_idx).value
        return data

    def _is_empty_row(self, raw: dict[str, Any]) -> bool:
        return all(v is None or str(v).strip() == "" for v in raw.values())

    def _parse_and_validate_row(self, raw: dict[str, Any]) -> ParsedRow:
        product_sku = self._required_text(raw.get("product_sku"), "product_sku")
        product_name = self._required_text(raw.get("product_name"), "product_name")
        category_name = self._required_text(raw.get("category_name"), "category_name")
        seller_name = self._required_text(raw.get("seller_name"), "seller_name")
        variant_name = self._required_text(raw.get("variant_name"), "variant_name")

        cost_price = self._decimal_value(raw.get("cost_price"), "cost_price")
        sale_price = self._decimal_value(raw.get("sale_price"), "sale_price")

        if cost_price < 0:
            raise ValueError("cost_price не может быть отрицательной")
        if sale_price < 0:
            raise ValueError("sale_price не может быть отрицательной")

        pack_size = self._int_value(raw.get("pack_size"), default=1)
        if pack_size < 1:
            raise ValueError("pack_size должен быть >= 1")

        stock = self._int_value(raw.get("stock"), default=0)
        if stock < 0:
            raise ValueError("stock не может быть отрицательным")

        is_active = self._bool_01_value(raw.get("is_active"), default=True)

        row = ParsedRow(
            product_sku=product_sku,
            product_name=product_name,
            product_description=self._optional_text(raw.get("product_description")),
            category_name=category_name,
            seller_name=seller_name,
            seller_city=self._optional_text(raw.get("seller_city")),
            unit=self._optional_text(raw.get("unit")) or "шт",
            main_image_url=self._optional_text(raw.get("main_image_url")),
            gallery_urls=self._split_urls(raw.get("gallery_urls")),
            youtube_url=self._optional_text(raw.get("youtube_url")),
            variant_name=variant_name,
            pack_size=pack_size,
            cost_price=cost_price,
            sale_price=sale_price,
            stock=stock,
            is_active=is_active,
        )

        if len(row.product_sku) > 64:
            raise ValueError("product_sku длиннее 64 символов")
        if len(row.product_name) > 255:
            raise ValueError("product_name длиннее 255 символов")
        if len(row.variant_name) > 120:
            raise ValueError("variant_name длиннее 120 символов")
        if len(row.unit) > 32:
            raise ValueError("unit длиннее 32 символов")
        if row.product_description and len(row.product_description) > 2000:
            raise ValueError("product_description длиннее 2000 символов")

        return row

    def _get_or_create_category(self, category_name: str) -> tuple[Category, bool]:
        cache_key = category_name.casefold()

        if cache_key in self._category_cache:
            return self._category_cache[cache_key], False

        category = (
            self.db.query(Category)
            .filter(func.lower(Category.name) == category_name.casefold())
            .first()
        )

        created = False
        if not category:
            slug = self._make_unique_category_slug(category_name)
            category = Category(name=category_name, slug=slug)
            self.db.add(category)
            self.db.flush()
            created = True

        self._category_cache[cache_key] = category
        return category, created

    def _get_or_create_seller(self, seller_name: str, seller_city: str | None) -> tuple[Seller, bool]:
        cache_key = seller_name.casefold()

        if cache_key in self._seller_cache:
            seller = self._seller_cache[cache_key]
            if (not seller.city or not seller.city.strip()) and seller_city:
                seller.city = seller_city
                self.db.flush()
            return seller, False

        seller = (
            self.db.query(Seller)
            .filter(func.lower(Seller.name) == seller_name.casefold())
            .first()
        )

        created = False
        if not seller:
            seller = Seller(name=seller_name, city=(seller_city or "Не указан"))
            self.db.add(seller)
            self.db.flush()
            created = True
        elif (not seller.city or not seller.city.strip()) and seller_city:
            seller.city = seller_city
            self.db.flush()

        self._seller_cache[cache_key] = seller
        return seller, created

    def _get_or_create_product(
        self,
        row: ParsedRow,
        category_id: int,
        seller_id: int,
    ) -> tuple[Product, bool]:
        if row.product_sku in self._product_cache:
            product = self._product_cache[row.product_sku]
            created = False
        else:
            product = self.db.query(Product).filter(Product.sku == row.product_sku).first()
            created = product is None

            if created:
                product = Product(sku=row.product_sku)
                self.db.add(product)

            self._product_cache[row.product_sku] = product

        product.name = row.product_name
        product.description = row.product_description
        product.unit = row.unit or "шт"
        product.category_id = category_id
        product.seller_id = seller_id
        product.is_active = row.is_active

        # v1: медиа пока не сохраняем
        self.db.flush()
        return product, created

    def _get_or_create_variant(self, product_id: int, row: ParsedRow) -> tuple[Variant, bool]:
        variant = (
            self.db.query(Variant)
            .filter(
                Variant.product_id == product_id,
                func.lower(Variant.name) == row.variant_name.casefold(),
                Variant.pack_size == row.pack_size,
            )
            .first()
        )

        created = variant is None
        if created:
            variant = Variant(product_id=product_id)
            self.db.add(variant)

        variant.name = row.variant_name
        variant.pack_size = row.pack_size
        variant.unit_price_net_cost = row.cost_price
        variant.unit_price = row.sale_price
        variant.stock = row.stock
        variant.is_active = row.is_active

        self.db.flush()
        return variant, created

    def _make_unique_category_slug(self, value: str) -> str:
        base = self._slugify(value) or "category"
        slug = base
        index = 2

        while self.db.query(Category).filter(Category.slug == slug).first():
            slug = f"{base}-{index}"
            index += 1

        return slug

    @staticmethod
    def _normalize_header(value: str) -> str:
        return "_".join(value.strip().lower().split())

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join(value.strip().split())

    def _required_text(self, value: Any, field_name: str) -> str:
        text = self._optional_text(value)
        if not text:
            raise ValueError(f"Поле {field_name} обязательно")
        return text

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = self._normalize_text(str(value))
        return text or None

    @staticmethod
    def _decimal_value(value: Any, field_name: str) -> Decimal:
        if value is None or str(value).strip() == "":
            raise ValueError(f"Поле {field_name} обязательно")

        text = str(value).strip().replace(" ", "").replace(",", ".")
        try:
            return Decimal(text)
        except (InvalidOperation, ValueError):
            raise ValueError(f"Поле {field_name} должно быть числом")

    @staticmethod
    def _int_value(value: Any, default: int) -> int:
        if value is None or str(value).strip() == "":
            return default
        try:
            return int(float(str(value).strip().replace(",", ".")))
        except (ValueError, TypeError):
            raise ValueError("Ожидалось целое число")

    @staticmethod
    def _bool_01_value(value: Any, default: bool) -> bool:
        if value is None or str(value).strip() == "":
            return default

        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "да"}:
            return True
        if text in {"0", "false", "no", "нет"}:
            return False

        raise ValueError("is_active должен быть 0 или 1")

    @staticmethod
    def _split_urls(value: Any) -> list[str]:
        if value is None:
            return []

        text = str(value).strip()
        if not text:
            return []

        return [part.strip() for part in text.split(",") if part.strip()]

    @staticmethod
    def _slugify(value: str) -> str:
        value = value.strip().lower()
        allowed = []
        prev_dash = False

        for ch in value:
            if ch.isalnum():
                allowed.append(ch)
                prev_dash = False
            else:
                if not prev_dash:
                    allowed.append("-")
                    prev_dash = True

        slug = "".join(allowed).strip("-")
        return slug