from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config.db_config import db_settings

engine = create_engine(db_settings.url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
