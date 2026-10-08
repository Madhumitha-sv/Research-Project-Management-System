"""
app.py
Module 1 (Login, Logout, Dashboard) + Module 2 (Projects, Tasks, User Management) — Flask + Postgres.

Run with:
    python app.py
"""

from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_migrate import Migrate
from flask_wtf import CSRFProtect 
from datetime import date, datetime

from models import db, User, Project, Task, project_members
from authentication import authenticate, get_all_users
from database import (
    init_db,
    username_exists,
    username_exists_for_other,
    add_user,
    get_user_by_id,
    update_user,
    delete_user,
)

app = Flask(__name__)
app.secret_key = "change-this-to-any-random-string"  # Flask needs this to keep sessions secure

csrf = CSRFProtect(app) 

import hashlib

AVATAR_PALETTE = [
    "#F97066", "#F79009", "#EAAA08", "#4CA30D",
    "#0E9384", "#155EEF", "#7A5AF8", "#DD2590",
]

def avatar_color(user_id):
    idx = int(hashlib.md5(str(user_id).encode()).hexdigest(), 16) % len(AVATAR_PALETTE)
    return AVATAR_PALETTE[idx]

app.jinja_env.filters['avatar_color'] = avatar_color

# --- Database configuration ---
app.config['SQLALCHEMY_DATABASE_URI'] = (
    'postgresql+psycopg2://postgres:sql@localhost:5432/research'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)


@app.cli.command("seed-db")
def seed_db():
    """Run manually with: python -m flask seed-db
    (only after `flask db upgrade` has created the tables)."""
    init_db()
    print("Demo accounts seeded (or already existed).")


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        if session["user"]["role"] != "Admin":
            flash("You don't have permission to do that.")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper


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

        session["user"] = {
            "user_id": user["user_id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
            "email": user["email"],
        }
        return redirect(url_for("dashboard"))

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
    users = get_all_users() if user["role"] == "Admin" else None

    return render_template("dashboard.html", user=user, users=users)


# ---------------------------------------------------------------------------
# Module 2 helpers
# ---------------------------------------------------------------------------
def user_can_manage_project(project, user):
    """Owner or Admin can manage a project (change status, add members, create tasks)."""
    return user['role'] == 'Admin' or project.owner_id == user['user_id']


def get_project_or_404(project_id):
    project = Project.query.get(project_id)
    if project is None:
        abort(404)
    return project


def _fmt_date(d):
    """Dates may come back as date objects or strings depending on the column type."""
    if not d:
        return None
    if isinstance(d, (date, datetime)):
        return d.strftime('%Y-%m-%d')
    return str(d)[:10]


def _serialize_project(p):
    owner = User.query.get(p.owner_id)
    tasks = list(p.tasks)
    total = len(tasks)
    done = sum(1 for t in tasks if t.status == 'Completed')
    progress = int(round(done / total * 100)) if total else 0

    return {
        'id': p.project_id,
        'title': p.title,
        'description': p.description or '',
        'status': p.status,
        'owner': owner.full_name if owner else 'Unassigned',
        'members': [m.full_name for m in p.members],
        'start_date': _fmt_date(p.start_date),
        'end_date': _fmt_date(p.end_date),
        'progress': progress,
        'task_total': total,
        'task_done': done,
        'url': url_for('project_detail', project_id=p.project_id),
    }


# ---------------------------------------------------------------- Projects

@app.route('/projects')
@login_required
def projects():
    user = session['user']

    if user['role'] == 'Admin':
        project_list = Project.query.order_by(Project.created_at.desc()).all()
    else:
        project_list = (
            Project.query
            .outerjoin(project_members, project_members.c.project_id == Project.project_id)
            .filter(
                db.or_(
                    Project.owner_id == user['user_id'],
                    project_members.c.user_id == user['user_id'],
                )
            )
            .distinct()
            .order_by(Project.created_at.desc())
            .all()
        )

    rows = [_serialize_project(p) for p in project_list]
    can_create = user['role'] in ('Admin', 'Faculty')

    return render_template('projects.html', projects=rows, can_create=can_create)


@app.route('/projects/new', methods=['GET', 'POST'])
@login_required
def new_project():
    user = session['user']
    if user['role'] not in ('Admin', 'Faculty'):
        abort(403)

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        start_date = request.form.get('start_date') or None
        end_date = request.form.get('end_date') or None

        if not title:
            flash('Title is required.')
            return render_template('new_project.html')

        project = Project(
            title=title,
            description=description,
            status='Active',
            owner_id=user['user_id'],
            start_date=start_date,
            end_date=end_date,
        )
        db.session.add(project)
        db.session.commit()
        flash('Project created.')
        return redirect(url_for('projects'))

    return render_template('new_project.html')


@app.route('/projects/<int:project_id>')
@login_required
def project_detail(project_id):
    user = session['user']
    project = get_project_or_404(project_id)
    is_owner = user_can_manage_project(project, user)
    is_member = any(m.user_id == user['user_id'] for m in project.members)

    if not (is_owner or is_member):
        abort(403)

    available_members = []
    if is_owner:
        member_ids = {m.user_id for m in project.members} | {project.owner_id}
        available_members = (
            User.query
            .filter(User.user_id.notin_(member_ids))
            .order_by(User.full_name)
            .all()
        )

    tasks_sorted = sorted(project.tasks, key=lambda t: (t.due_date is None, t.due_date))

    return render_template(
        'project_detail.html',
        project=project, members=project.members, tasks=tasks_sorted,
        is_owner=is_owner, available_members=available_members,
    )


@app.route('/projects/<int:project_id>/status', methods=['POST'])
@login_required
def update_project_status(project_id):
    user = session['user']
    project = get_project_or_404(project_id)

    if not user_can_manage_project(project, user):
        abort(403)

    new_status = request.form.get('status')
    if new_status not in ('Active', 'On Hold', 'Completed'):
        abort(400)

    project.status = new_status
    db.session.commit()
    flash('Project status updated.')
    return redirect(url_for('project_detail', project_id=project_id))


@app.route('/projects/<int:project_id>/members', methods=['POST'])
@login_required
def add_member(project_id):
    user = session['user']
    project = get_project_or_404(project_id)

    if not user_can_manage_project(project, user):
        abort(403)

    new_user_id = request.form.get('user_id', type=int)
    if not new_user_id:
        abort(400)

    member = User.query.get(new_user_id)
    if member is None:
        abort(400)

    if member not in project.members:
        project.members.append(member)
        db.session.commit()

    flash('Member added.')
    return redirect(url_for('project_detail', project_id=project_id))


# ------------------------------------------------------------------- Tasks

@app.route('/tasks')
@login_required
def tasks():
    user = session['user']

    if user['role'] == 'Admin':
        rows = Task.query.join(Project).all()
    elif user['role'] == 'Faculty':
        rows = (
            Task.query.join(Project)
            .filter(db.or_(Project.owner_id == user['user_id'], Task.assigned_to == user['user_id']))
            .all()
        )
    else:  # Student
        rows = Task.query.filter(Task.assigned_to == user['user_id']).all()

    rows = sorted(rows, key=lambda t: (t.due_date is None, t.due_date))
    return render_template('tasks.html', tasks=rows)


@app.route('/projects/<int:project_id>/tasks/new', methods=['GET', 'POST'])
@login_required
def new_task(project_id):
    user = session['user']
    project = get_project_or_404(project_id)

    if not user_can_manage_project(project, user):
        abort(403)

    members = project.members

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        assigned_to = request.form.get('assigned_to', type=int)
        due_date = request.form.get('due_date') or None

        if not title:
            flash('Title is required.')
            return render_template('new_task.html', project=project, members=members)

        if assigned_to and not any(m.user_id == assigned_to for m in members):
            abort(400)

        task = Task(
            project_id=project_id,
            title=title,
            description=description,
            assigned_to=assigned_to,
            due_date=due_date,
            status='Pending',
            created_by=user['user_id'],
        )
        db.session.add(task)
        db.session.commit()
        flash('Task created.')
        return redirect(url_for('project_detail', project_id=project_id))

    return render_template('new_task.html', project=project, members=members)


@app.route('/tasks/<int:task_id>/status', methods=['POST'])
@login_required
def update_task_status(task_id):
    user = session['user']
    task = Task.query.get(task_id)
    if task is None:
        abort(404)

    is_owner = user['role'] == 'Admin' or task.project.owner_id == user['user_id']
    is_assignee = task.assigned_to == user['user_id']
    if not (is_owner or is_assignee):
        abort(403)

    new_status = request.form.get('status')
    if new_status not in ('Pending', 'In Progress', 'Completed'):
        abort(400)

    task.status = new_status
    db.session.commit()
    flash('Task status updated.')
    return redirect(request.referrer or url_for('tasks'))


# ---------------------------------------------------------------------------
# /users/add — Admin creates a new user directly
# ---------------------------------------------------------------------------
@app.route("/users/add", methods=["GET", "POST"])
@admin_required
def add_user_route():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        role = request.form.get("role", "").strip()
        password = request.form.get("password", "")

        if not full_name or not username or not password or not role:
            flash("Please fill in all required fields.")
            return render_template("user_form.html", mode="add", form_data=request.form)

        if role not in ("Admin", "Faculty", "Student"):
            flash("Please select a valid role.")
            return render_template("user_form.html", mode="add", form_data=request.form)

        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return render_template("user_form.html", mode="add", form_data=request.form)

        if username_exists(username):
            flash("That username is already taken.")
            return render_template("user_form.html", mode="add", form_data=request.form)

        add_user(username, password, full_name, role, email)
        flash(f"User '{username}' created.")
        return redirect(url_for("dashboard"))

    return render_template("user_form.html", mode="add", form_data={})


# ---------------------------------------------------------------------------
# /users/edit/<id> — Admin updates an existing user
# ---------------------------------------------------------------------------
@app.route("/users/edit/<int:user_id>", methods=["GET", "POST"])
@admin_required
def edit_user_route(user_id):
    existing = get_user_by_id(user_id)
    if existing is None:
        flash("User not found.")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        role = request.form.get("role", "").strip()
        password = request.form.get("password", "")  # optional on edit

        if not full_name or not username or not role:
            flash("Please fill in all required fields.")
            return render_template("user_form.html", mode="edit", form_data=request.form, user_id=user_id)

        if role not in ("Admin", "Faculty", "Student"):
            flash("Please select a valid role.")
            return render_template("user_form.html", mode="edit", form_data=request.form, user_id=user_id)

        if password and len(password) < 6:
            flash("Password must be at least 6 characters.")
            return render_template("user_form.html", mode="edit", form_data=request.form, user_id=user_id)

        if username_exists_for_other(username, user_id):
            flash("That username is already taken.")
            return render_template("user_form.html", mode="edit", form_data=request.form, user_id=user_id)

        update_user(user_id, username, full_name, role, email, password if password else None)
        flash(f"User '{username}' updated.")
        return redirect(url_for("dashboard"))

    return render_template("user_form.html", mode="edit", form_data=existing, user_id=user_id)


# ---------------------------------------------------------------------------
# /users/delete/<id> — Admin removes a user
# ---------------------------------------------------------------------------
@app.route("/users/delete/<int:user_id>", methods=["POST"])
@admin_required
def delete_user_route(user_id):
    if user_id == session["user"]["user_id"]:
        flash("You can't delete your own account while logged in.")
        return redirect(url_for("dashboard"))

    delete_user(user_id)
    flash("User deleted.")
    return redirect(url_for("dashboard"))

import hashlib

# --- avatar colors (skip if you already added this earlier) ---
AVATAR_PALETTE = [
    "#F97066", "#F79009", "#EAAA08", "#4CA30D",
    "#0E9384", "#155EEF", "#7A5AF8", "#DD2590",
]

def avatar_color(user_id):
    idx = int(hashlib.md5(str(user_id).encode()).hexdigest(), 16) % len(AVATAR_PALETTE)
    return AVATAR_PALETTE[idx]

app.jinja_env.filters['avatar_color'] = avatar_color


# --- Team: Admin sees everyone; Faculty/Student see people on shared projects ---
@app.route('/team')
@login_required
def team():
    user = session['user']

    if user['role'] == 'Admin':
        return render_template('team.html', members=get_all_users())

    uid = user['user_id']
    if user['role'] == 'Faculty':
        project_list = (
            Project.query
            .filter(db.or_(Project.owner_id == uid, Project.members.any(User.user_id == uid)))
            .all()
        )
    else:  # Student
        project_list = Project.query.filter(Project.members.any(User.user_id == uid)).all()

    people = {}
    for p in project_list:
        for person in [p.owner] + list(p.members):
            if person.user_id == uid:
                continue
            entry = people.setdefault(person.user_id, {'user': person, 'projects': []})
            if p not in entry['projects']:
                entry['projects'].append(p)

    teammates = sorted(people.values(), key=lambda e: e['user'].full_name)
    return render_template('team_directory.html', teammates=teammates)


# --- Settings: every user edits their own account ---
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    me = User.query.get(session['user']['user_id'])
    if me is None:
        session.pop('user', None)
        return redirect(url_for('login'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not full_name:
            flash('Full name is required.')
            return redirect(url_for('settings'))

        if password:
            if password != confirm_password:
                flash('Passwords do not match.')
                return redirect(url_for('settings'))
            if len(password) < 6:
                flash('Password must be at least 6 characters.')
                return redirect(url_for('settings'))
            me.password_hash = hash_password(password)

        me.full_name = full_name
        me.email = email
        db.session.commit()

        # Keep the navbar in sync with the change
        session['user']['full_name'] = full_name
        session['user']['email'] = email
        session.modified = True

        flash('Settings updated.')
        return redirect(url_for('settings'))

    current = {
        'user_id': me.user_id,
        'username': me.username,
        'full_name': me.full_name,
        'role': me.role,
        'email': me.email,
    }
    return render_template('settings.html', current=current)

if __name__ == "__main__":
    app.run(debug=True)