"""
auth.py
Implements FR1 (User Login): authenticate users using username and password.
Same file as the Streamlit version — this logic doesn't change based on framework.
"""

from database import get_connection, hash_password


def authenticate(username: str, password: str):
    """
    Checks the given username/password against the database.
    Returns the user's info as a dict if valid, otherwise None.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()

    if user is None:
        return None  # no such username

    if user["password_hash"] != hash_password(password):
        return None  # wrong password

    return dict(user)


def get_all_users():
    """Used by the Admin dashboard to show registered users."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, full_name, role, email FROM users")
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users