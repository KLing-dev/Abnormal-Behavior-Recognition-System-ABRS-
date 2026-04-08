from sqlalchemy.orm import Session
from models.base import SessionLocal


def get_db_session() -> Session:
    return SessionLocal()


def close_db_session(session: Session):
    if session:
        session.close()
