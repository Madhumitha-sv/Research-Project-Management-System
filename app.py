"""
app.py
Module 1: Login, Logout, and Dashboard — Flask version.

Run with:
    python app.py
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import init_db, username_exists, add_user
from authentication import authenticate, get_all_users

app = Flask(__name__)
app.secret_key = "change-this-to-any-random-string"  # Flask needs this to keep sessions secure

# Make sure the database + demo users exist before the app starts serving pages
init_db()


# ---------------------------------------------------------------------------
# / — redirects to the right page depending on login state
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# /login — shows the form (GET) and handles submission (POST)
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Please enter both username and password.")
            return render_template("login.html")

        user = authenticate(username, password)
        if user is None:
            flash("Invalid username or password.")
            return render_template("login.html")

        # Store only what we need in the session — never the password hash
        session["user"] = {
            "user_id": user["user_id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
            "email": user["email"],
        }
        return redirect(url_for("dashboard"))

    # GET request — just show the empty login form
    return render_template("login.html")


# ---------------------------------------------------------------------------
# /register — shows the signup form (GET) and creates the account (POST)
# ---------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        role = request.form.get("role", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name or not username or not password or not role:
            flash("Please fill in all required fields.")
            return render_template("register.html")

        if role not in ("Admin", "Faculty", "Student"):
            flash("Please select a valid role.")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return render_template("register.html")

        if username_exists(username):
            flash("That username is already taken.")
            return render_template("register.html")

        add_user(username, password, full_name, role, email)
        flash("Account created. You can log in now.")
        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------------------------------------------------------------------
# /logout — clears the session and sends the user back to login
# ---------------------------------------------------------------------------
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# /dashboard — role-based dashboard, only visible when logged in
# ---------------------------------------------------------------------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    user = session["user"]
    # Only fetch the full user list if an Admin is viewing (used in the table)
    users = get_all_users() if user["role"] == "Admin" else None

    return render_template("dashboard.html", user=user, users=users)


if __name__ == "__main__":
    app.run(debug=True)