from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user
import logging
import os

logger = logging.getLogger('security_audit')
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'security_audit.log')
handler = logging.FileHandler(log_path, mode='a')
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.WARNING)
logger.propagate = False

def log_audit(event, detail=''):
    logger.warning(f'{event} | {detail} | User: {getattr(current_user, "identifier", "Anonymous")} | IP: {getattr(current_user, "remote_addr", "unknown")}')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if current_user.role != 'admin':
            log_audit('UNAUTHORIZED ACCESS', f'Non-admin user attempted admin endpoint')
            flash('You do not have permission to access this resource.', 'danger')
            return redirect(url_for('library_dashboard.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def librarian_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if current_user.role not in ('librarian', 'admin'):
            log_audit('UNAUTHORIZED ACCESS', f'Non-librarian user attempted librarian endpoint')
            flash('You do not have permission to access this resource.', 'danger')
            return redirect(url_for('library_dashboard.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def librarian_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if current_user.role not in ('librarian', 'admin'):
            log_audit('UNAUTHORIZED ACCESS', f'Non-staff user attempted staff endpoint')
            flash('You do not have permission to access this resource.', 'danger')
            return redirect(url_for('library_dashboard.dashboard'))
        return f(*args, **kwargs)
    return decorated_function
