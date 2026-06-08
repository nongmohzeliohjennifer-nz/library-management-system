from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=False, nullable=False)
    identifier = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student')
    theme_preference = db.Column(db.String(20), nullable=False, default='indigo')
    language = db.Column(db.String(5), nullable=False, default='en')
    failed_login_attempts = db.Column(db.Integer, nullable=False, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    identifier = db.Column(db.String(50))
    action = db.Column(db.String(255))
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.BigInteger)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    isbn = db.Column(db.String(20), unique=True, nullable=False)
    genre = db.Column(db.String(50), nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    book_type = db.Column(db.String(20), nullable=False, default='physical')
    file_path = db.Column(db.String(255), nullable=True)

class BorrowRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    request_date = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='Pending')
    returned_date = db.Column(db.DateTime, nullable=True)

    book = db.relationship('Book', backref=db.backref('borrow_records', lazy=True))
    user = db.relationship('User', backref=db.backref('borrow_records', lazy=True))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    message = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.Column(db.String(50), nullable=True)
    is_read = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref=db.backref('notifications_list', lazy=True, cascade='all, delete-orphan'))
