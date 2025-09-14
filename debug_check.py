# debug_check.py
from app.db import SessionLocal
from app.models.catalog import Product, Variant

db = SessionLocal()
print("=== PRODUCTS ===")
for p in db.query(Product).order_by(Product.name).all():
    print(f"id={p.id} name={p.name!r} image={p.image!r}")

print("\n=== VARIANTS ===")
for v in db.query(Variant).order_by(Variant.id).all():
    print(f"id={v.id} product_id={v.product_id} name={v.name!r} price={v.unit_price}")
db.close()
