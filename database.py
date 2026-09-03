"""
database.py
Seeds demo accounts into Postgres. Table creation and schema changes are
handled by Flask-Migrate (see the migrations/ folder), not here.
"""

import hashlib
from models import db, User


def hash_password(password: str) -> str:
    """Simple SHA-256 hashing so passwords are never stored as plain text."""
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    """
    Seeds demo accounts on first run.
    Must be called inside an app context — see app.py, which wraps this
    call in `with app.app_context():`.
    """
    if User.query.count() == 0:
        _seed_default_users()


def _seed_default_users():
    """Adds one demo account per role so the app is testable immediately."""
    demo_users = [
        ("admin",    "admin123",   "System Administrator", "Admin",   "admin@research.edu"),
        ("faculty1", "faculty123", "Dr. Priya Sharma",      "Faculty", "priya@research.edu"),
        ("student1", "student123", "Arjun Kumar",           "Student", "arjun@research.edu"),
    ]
    for username, password, full_name, role, email in demo_users:
        db.session.add(User(
            username=username,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            email=email,
        ))
    db.session.commit()


def username_exists(username: str) -> bool:
    """Checks if a username is already taken."""
    return User.query.filter_by(username=username).first() is not None


def add_user(username, password, full_name, role, email):
    """Used by registration and later by the User Management module (Admin only)."""
    user = User(
        username=username,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        email=email,
    )
    db.session.add(user)
    db.session.commit()


def get_user_by_id(user_id):
    """Fetch a single user's details — used to pre-fill the edit form."""
    user = User.query.get(user_id)
    if user is None:
        return None
    return {
        "user_id": user.user_id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "email": user.email,
    }


def username_exists_for_other(username: str, exclude_user_id: int) -> bool:
    """Like username_exists, but ignores the user being edited (so saving
    their own unchanged username doesn't falsely flag as taken)."""
    return User.query.filter(
        User.username == username,
        User.user_id != exclude_user_id,
    ).first() is not None


def update_user(user_id, username, full_name, role, email, password=None):
    """Updates a user's details, including username. Password is optional — only changed if provided."""
    user = User.query.get(user_id)
    if user is None:
        return
    user.username = username
    user.full_name = full_name
    user.role = role
    user.email = email
    if password:
        user.password_hash = hash_password(password)
    db.session.commit()

def delete_user(user_id):
    """Permanently removes a user."""
    user = User.query.get(user_id)
    if user is None:
        return
    db.session.delete(user)
    db.session.commit()