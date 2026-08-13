# models.py
# Assumes `db = SQLAlchemy()` is created here or imported from an extensions
# module and initialized on your Flask app with app.init_app(db) / db.init_app(app).

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150))
    role = db.Column(db.String(20), nullable=False)  # 'Admin' | 'Faculty' | 'Student'

    __table_args__ = (
        db.CheckConstraint("role IN ('Admin', 'Faculty', 'Student')", name='ck_user_role'),
    )


# Many-to-many association: which users belong to which project.
project_members = db.Table(
    'project_members',
    db.Column('project_id', db.Integer,
              db.ForeignKey('projects.project_id', ondelete='CASCADE'), primary_key=True),
    db.Column('user_id', db.Integer,
              db.ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True),
)


class Project(db.Model):
    __tablename__ = 'projects'

    project_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default='Active')
    owner_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    owner = db.relationship('User', foreign_keys=[owner_id])
    members = db.relationship('User', secondary=project_members, backref='projects_member_of')
    tasks = db.relationship('Task', backref='project', cascade='all, delete-orphan')

    __table_args__ = (
        db.CheckConstraint("status IN ('Active', 'On Hold', 'Completed')", name='ck_project_status'),
    )


class Task(db.Model):
    __tablename__ = 'tasks'

    task_id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.project_id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    due_date = db.Column(db.Date)
    status = db.Column(db.String(20), nullable=False, default='Pending')
    created_by = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    assignee = db.relationship('User', foreign_keys=[assigned_to])

    __table_args__ = (
        db.CheckConstraint("status IN ('Pending', 'In Progress', 'Completed')", name='ck_task_status'),
    )
