from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base
from sqlalchemy import create_engine
from contextlib import contextmanager
import os

from api.utils.settings import BASE_DIR


DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'proj.db')}"

def get_db_engine():
    return create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

engine = get_db_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db_session = scoped_session(SessionLocal)

Base = declarative_base()

def create_database():
    return Base.metadata.create_all(bind=engine)

def get_db():
    db = db_session()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_with_ctx_manager():
    db = db_session()
    try:
        yield db
    finally:
        db.close()
