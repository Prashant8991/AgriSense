"""
Database connection — reusable psycopg2 helpers (mirrors Desktop app's db_connect)
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

# Use DATABASE_URL if available (common for Render/Heroku), else fall back to explicit
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:kali@localhost:5432/agrisense_pro")

def get_conn():
    """Return a raw psycopg2 connection."""
    return psycopg2.connect(DB_URL)

def get_dict_conn():
    """Return a connection with RealDictCursor."""
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
