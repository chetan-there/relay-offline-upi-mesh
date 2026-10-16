"""
Schema initialization: verifies the MySQL connection, creates any missing
tables, and seeds the demo accounts if the accounts table is empty. Safe to run
repeatedly - it never drops or overwrites existing data.

Run manually (from backend/):   python -m app.init_db
Also called automatically on FastAPI startup.
"""
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from . import models  # noqa: F401  (registers the tables on Base.metadata)
from .database import Base, SessionLocal, engine
from .ledger_service import seed_accounts


def init_db() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError:
        # `from None` keeps connection details out of the traceback.
        raise RuntimeError(
            "Could not connect to MySQL. Check that the server is running and that "
            "DATABASE_URL (backend/.env) has the right host, port, user, password and database."
        ) from None

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_accounts(db)
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("MySQL connection OK. Tables ready: " + ", ".join(sorted(Base.metadata.tables)))
