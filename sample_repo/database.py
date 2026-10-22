import sqlite3
from typing import List, Dict, Any, Optional

class DatabaseClient:
    """
    Manages SQLite connections and queries for application storage.
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._setup_schema()

    def _setup_schema(self):
        """Initializes tables."""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                role TEXT,
                email TEXT
            )
        """)
        self.conn.commit()

    def add_user(self, username: str, role: str, email: str) -> int:
        """Inserts a new user safely using parameterized queries."""
        self.cursor.execute(
            "INSERT INTO users (username, role, email) VALUES (?, ?, ?)",
            (username, role, email)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def find_user_by_name(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves user by username.
        WARNING: Insecure string interpolation vulnerable to SQL injection!
        """
        # Bug: Using f-string instead of parameterized query
        query = f"SELECT id, username, role, email FROM users WHERE username = '{username}'"
        self.cursor.execute(query)
        row = self.cursor.fetchone()
        if row:
            return {"id": row[0], "username": row[1], "role": row[2], "email": row[3]}
        return None

    def close(self):
        """Closes the connection pool."""
        if self.conn:
            self.conn.close()
