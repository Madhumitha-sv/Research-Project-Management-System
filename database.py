"""
database.py
Handles the SQLite connection and table setup for Module 1 (Login/Logout/Dashboard).
This file doesn't know or care whether Flask or Streamlit is calling it.
"""

import sqlite3
import hashlib

DB_NAME = "research_system.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # lets us access columns by name, e.g. row["username"]
    return conn


def hash_password(password: str) -> str:
    """Simple SHA-256 hashing so passwords are never stored as plain text."""
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    """Creates the users table if it doesn't exist, and seeds demo accounts on first run."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('Admin', 'Faculty', 'Student')),
            email TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        _seed_default_users(conn)

    conn.close()


def _seed_default_users(conn):
    """Adds one demo account per role so the app is testable immediately."""
    demo_users = [
        ("admin",    "admin123",   "System Administrator", "Admin",   "admin@research.edu"),
        ("faculty1", "faculty123", "Dr. Priya Sharma",      "Faculty", "priya@research.edu"),
        ("student1", "student123", "Arjun Kumar",           "Student", "arjun@research.edu"),
    ]
    cursor = conn.cursor()
    for username, password, full_name, role, email in demo_users:
        cursor.execute(
            "INSERT INTO users (username, password_hash, full_name, role, email) VALUES (?, ?, ?, ?, ?)",
            (username, hash_password(password), full_name, role, email),
        )
    conn.commit()

def username_exists(username: str) -> bool:
    """Checks if a username is already taken."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def add_user(username, password, full_name, role, email):
    """Used later by the User Management module (Admin only) — included now so it's ready."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash, full_name, role, email) VALUES (?, ?, ?, ?, ?)",
        (username, hash_password(password), full_name, role, email),
    )
    conn.commit()
    conn.close()