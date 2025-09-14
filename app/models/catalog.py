from typing import List, Optional
from sqlalchemy import String, ForeignKey, Integer, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base

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
    image: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"))
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="products")

    variants: Mapped[List["Variant"]] = relationship(
        "Variant", back_populates="product", cascade="all, delete-orphan"
    )

class Variant(Base):
    __tablename__ = "variants"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    name: Mapped[str] = mapped_column(String(120))   # "1 литр", "1 кг" и т.д.
    pack_size: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2))
    stock: Mapped[int] = mapped_column(Integer, default=0)   # ← НОВОЕ: остаток
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    product: Mapped["Product"] = relationship("Product", back_populates="variants")
