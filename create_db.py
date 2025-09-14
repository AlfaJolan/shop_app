from app.db import Base, engine
# До create_all обязательно импортируем модели:
import app.models.catalog  # noqa
import app.models.order    # noqa
import app.models.invoice  # noqa

Base.metadata.create_all(bind=engine)
print("DB created at:", engine.url)
