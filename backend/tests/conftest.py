"""
app.database requires DATABASE_URL at import time. The tests never connect to
that URL (they build their own engines in the db_session fixture), so a
placeholder is enough to let `from app.database import Base` import cleanly.
"""
import os

os.environ.setdefault(
    "DATABASE_URL",
    "mysql+pymysql://placeholder:placeholder@localhost:3306/placeholder",
)
