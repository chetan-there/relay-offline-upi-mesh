"""MySQL database connection configured through DATABASE_URL (backend/.env).
Example: mysql+pymysql://user:password@localhost:3306/upimesh
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

def _resolve_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy backend/.env.example to backend/.env "
            "and fill in your MySQL credentials."
        )
    if url.startswith("mysql://"):
        url = "mysql+pymysql://" + url[len("mysql://"): ]
    if not url.startswith("mysql+pymysql://"):
        raise RuntimeError(
            "DATABASE_URL must be a MySQL URL, e.g. "
            "mysql+pymysql://user:password@localhost:3306/upimesh"
        )
    return url

DATABASE_URL = _resolve_database_url()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
