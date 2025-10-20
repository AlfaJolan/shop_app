from typing import List, Optional
from sqlalchemy import String, ForeignKey, Integer, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base



class Seller(Base):
    __tablename__ = "sellers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)   # имя продавца
    city: Mapped[str] = mapped_column(String(120), nullable=False)   # город продавца

    # отношение: один продавец → много продуктов
    products: Mapped[List["Product"]] = relationship("Product", back_populates="seller")
    salespersons = relationship("Salesperson", back_populates="seller", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    products: Mapped[List["Product"]] = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    sku: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    unit: Mapped[str] = mapped_column(String(32), default="шт")
    # 🔹 URL изображения товара (опционально) для превью
    image: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
     # 🔹 Описание товара
    description: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"))
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="products")

    seller_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sellers.id"))   # 🔹 связь с продавцом
    seller: Mapped[Optional["Seller"]] = relationship("Seller", back_populates="products")

    variants: Mapped[List["Variant"]] = relationship(
        "Variant", back_populates="product", cascade="all, delete-orphan"
    )
    # 🔹 Дополнительные картинки (галерея на странице товара)
    images: Mapped[List["ProductImage"]] = relationship(
        "ProductImage", back_populates="product", cascade="all, delete-orphan"
    )

    # 🔹 Видео
    videos: Mapped[List["ProductVideo"]] = relationship(
        "ProductVideo", back_populates="product", cascade="all, delete-orphan"
    )

class Variant(Base):
    __tablename__ = "variants"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    name: Mapped[str] = mapped_column(String(120))   # "1 литр", "1 кг" и т.д.
    pack_size: Mapped[int] = mapped_column(Integer, default=1)
    # Себестоимость
    unit_price_net_cost: Mapped[float] = mapped_column(Numeric(12, 2))
    # Цена товара
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2))
    stock: Mapped[int] = mapped_column(Integer, default=0)   # ← НОВОЕ: остаток
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    product: Mapped["Product"] = relationship("Product", back_populates="variants")

class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))

    # 🔹 путь к дополнительной картинке (uploads/products/123/extra1.jpg)
    image_url: Mapped[str] = mapped_column(String(255))

    # 🔹 порядок сортировки в галерее
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped["Product"] = relationship("Product", back_populates="images")



class ProductVideo(Base):
    __tablename__ = "product_videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))

    # 🔹 ссылка на видео (YouTube/Vimeo или путь к локальному файлу)
    video_url: Mapped[str] = mapped_column(String(255))

    # 🔹 заголовок или подпись (опционально)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # 🔹 порядок сортировки (если у товара несколько видео)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped["Product"] = relationship("Product", back_populates="videos")

