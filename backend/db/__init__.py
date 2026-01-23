import sqlite3
import os
from pathlib import Path
from .schema import create_schema

def get_db():
    """Get database connection"""
    db_dir = Path(__file__).parent.parent / 'data'
    db_dir.mkdir(exist_ok=True)
    
    db_path = os.getenv('DB_PATH', str(db_dir / 'nextstep.db'))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    conn.execute('PRAGMA foreign_keys = ON')
    
    # Create schema if needed
    create_schema(conn)
    
    return conn
