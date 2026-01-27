from app.db.session import Base, engine
from app.db import models  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
