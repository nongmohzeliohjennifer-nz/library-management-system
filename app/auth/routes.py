from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from app import db, limiter
from app.models import User
from app.auth.forms import LoginForm, RegistrationForm
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from app.utils import log_activity, log_security_event
from app.decorators import librarian_or_admin_required
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('library_dashboard.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        identifier_input = form.identifier.data
        password_input = form.password.data
        user = User.query.filter_by(identifier=identifier_input).first()

        if user:
            # Check if account is locked
            if user.locked_until and user.locked_until > datetime.utcnow():
                remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
                log_security_event('ACCOUNT_LOCKED', f'Login attempt on locked account', identifier_input, request.remote_addr)
                flash(f'Account locked due to too many failed attempts. Try again in {remaining} minute(s).', 'danger')
                return render_template('login.html', form=form)
            elif user.locked_until and user.locked_until <= datetime.utcnow():
                # Lockout expired, reset
                user.failed_login_attempts = 0
                user.locked_until = None
                db.session.commit()

        if user and check_password_hash(user.password, password_input):
            # Success — reset failed attempts
            user.failed_login_attempts = 0
            user.locked_until = None
            db.session.commit()
            session.clear()
            login_user(user)
            session.permanent = True
            flash(f'Welcome back, {user.identifier}!', 'success')
            log_activity(user.identifier, "User logged in successfully")
            return redirect(url_for('library_dashboard.dashboard'))

        # Failed login
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
                log_security_event('ACCOUNT_LOCKED', f'Account locked after {MAX_FAILED_ATTEMPTS} failed attempts', identifier_input, request.remote_addr)
            db.session.commit()

        log_activity(identifier_input, "Failed login attempt")
        log_security_event('FAILED_LOGIN', f'Failed login for identifier: {identifier_input}', identifier_input, request.remote_addr)
        flash('Login unsuccessful. Incorrect Credentials', 'danger')

    return render_template('login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('library_dashboard.dashboard'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        user = User(
            username=form.username.data,
            identifier=form.identifier.data,
            email=form.email.data,
            password=hashed_password,
            role=form.role.data
        )
        db.session.add(user)
        db.session.commit()

        log_activity(form.identifier.data, f"User registered successfully as {form.role.data}")
        log_security_event('USER_REGISTERED', f'New user registered: {form.identifier.data} as {form.role.data}', form.identifier.data, request.remote_addr)
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('auth.login'))
    elif request.method == 'POST':
        print("Register Form Errors:", form.errors)
    return render_template('register.html', title='Register', form=form)

@auth_bp.route('/add-user', methods=['POST'])
@limiter.limit("10 per minute")
def add_user():
    if not current_user.is_authenticated:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    if current_user.role not in ('admin', 'librarian'):
        log_security_event('UNAUTHORIZED_ACCESS', 'Non-staff user attempted add-user via API', current_user.identifier, request.remote_addr)
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400

    authorizer_password = data.get('authorizer_password')
    if not authorizer_password or not check_password_hash(current_user.password, authorizer_password):
        log_security_event('AUTHORIZATION_FAILED', 'Invalid authorizer password in add-user', current_user.identifier, request.remote_addr)
        return jsonify({'success': False, 'message': 'Invalid authorizer password'}), 403

    username = data.get('username', '').strip()
    identifier = data.get('identifier', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'student')

    if not username or not identifier or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required'}), 400

    if not all(c.isalnum() or c in ' -_#.' for c in identifier):
        return jsonify({'success': False, 'message': 'Identifier contains invalid characters'}), 400

    if role not in ('student', 'librarian', 'admin'):
        role = 'student'

    if current_user.role == 'librarian' and role != 'student':
        return jsonify({'success': False, 'message': 'Librarians can only create student accounts'}), 403

    if User.query.filter_by(identifier=identifier).first():
        return jsonify({'success': False, 'message': 'That ID is already taken'}), 409

    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'That email is already registered'}), 409

    hashed_password = generate_password_hash(password)
    user = User(
        username=username,
        identifier=identifier,
        email=email,
        password=hashed_password,
        role=role
    )
    db.session.add(user)
    db.session.commit()

    log_activity(current_user.identifier, f"User added by {current_user.role}: {identifier} as {role}")
    log_security_event('USER_ADDED', f'{current_user.identifier} added user {identifier} as {role}', current_user.identifier, request.remote_addr)
    return jsonify({'success': True, 'message': f'User {identifier} created successfully as {role}'})

@auth_bp.route('/logout')
def logout():
    if current_user.is_authenticated:
        log_activity(current_user.identifier, "User logged out")
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))
