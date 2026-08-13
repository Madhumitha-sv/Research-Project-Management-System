"""
authentication.py
Implements FR1 (User Login): authenticate users using username and password.
Now queries Postgres via SQLAlchemy instead of raw sqlite3.
"""

from models import User
from database import hash_password


def authenticate(username: str, password: str):
    """
    Checks the given username/password against the database.
    Returns the user's info as a dict if valid, otherwise None.
    """
    user = User.query.filter_by(username=username).first()

    if user is None:
        return None  # no such username

    if user.password_hash != hash_password(password):
        return None  # wrong password

    return {
        "user_id": user.user_id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "email": user.email,
    }


def get_all_users():
    """Used by the Admin dashboard to show registered users."""
    users = User.query.order_by(User.full_name).all()
    return [
        {
            "user_id": u.user_id,
            "username": u.username,
            "full_name": u.full_name,
            "role": u.role,
            "email": u.email,
        }
        for u in users
    ]