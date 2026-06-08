from flask import Blueprint, render_template, abort, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash
from app import db, limiter
from app.models import User, ActivityLog, Book, BorrowRecord, Notification
from app.library_dashboard.forms import BookForm
from app.utils import log_activity, log_security_event
from app.decorators import admin_required, librarian_or_admin_required
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
from flask import current_app

dash_bp = Blueprint('library_dashboard', __name__)

def send_notification(message, category, user_id=None):
    notification = Notification(
        user_id=user_id,
        message=message,
        category=category
    )
    db.session.add(notification)
    db.session.commit()

@dash_bp.route('/')
def index():
    return redirect(url_for('auth.login'))

@dash_bp.route('/dashboard')
@login_required
def dashboard():
    unread_count = Notification.query.filter(
        Notification.is_read == False,
        ((Notification.user_id == current_user.id) | (Notification.category == 'available'))
    ).count()
    return render_template('dashboard.html', unread_count=unread_count)

@dash_bp.route('/get-hub/<hub_type>')
@login_required
def get_hub(hub_type):
    if hub_type == 'admin':
        if current_user.role != 'admin':
            log_security_event('UNAUTHORIZED_HUB', 'Non-admin attempted admin hub', current_user.identifier, request.remote_addr)
            abort(403)
        log_activity(current_user.identifier, "Viewed Admin Hub")
        logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(15).all()
        total_logs = ActivityLog.query.count()
        users = User.query.filter(User.role.in_(['librarian', 'student'])).all()
        return render_template('hubs/admin_hub.html', logs=logs, total_logs=total_logs, users=users)

    elif hub_type == 'librarian':
        if current_user.role not in ['librarian', 'admin']:
            log_security_event('UNAUTHORIZED_HUB', 'Non-staff attempted librarian hub', current_user.identifier, request.remote_addr)
            abort(403)
        log_activity(current_user.identifier, "Viewed Librarian Hub")
        form = BookForm()
        books = Book.query.order_by(Book.id.desc()).all()
        pending_requests = BorrowRecord.query.filter_by(status='Pending').all()
        students = User.query.filter_by(role='student').all()
        active_borrows = BorrowRecord.query.join(Book).filter(
            Book.book_type == 'physical',
            BorrowRecord.status.in_(['Approved', 'Collected'])
        ).all()
        return render_template('hubs/librarian_hub.html', form=form, books=books, pending_requests=pending_requests, students=students, active_borrows=active_borrows)

    elif hub_type == 'student':
        search_query = request.args.get('search', '').strip()
        if search_query:
            log_activity(current_user.identifier, f"Searched catalog for: '{search_query}'")
            books = Book.query.filter(
                (Book.title.ilike(f'%{search_query}%')) |
                (Book.author.ilike(f'%{search_query}%'))
            ).all()
        else:
            log_activity(current_user.identifier, "Viewed Student Hub Catalog")
            books = Book.query.all()

        my_records = BorrowRecord.query.filter_by(user_id=current_user.id).all()

        now = datetime.utcnow()
        active_records = []
        for record in my_records:
            if record.book.book_type == 'digital' and record.due_date and record.due_date < now:
                if record.status == 'Approved':
                    record.status = 'Returned'
                    record.returned_date = now
                    db.session.commit()
            else:
                active_records.append(record)

        return render_template('hubs/student_hub.html', books=books, records=active_records, search_query=search_query)

    elif hub_type == 'notifications':
        log_activity(current_user.identifier, "Viewed Notifications Hub")
        if current_user.role in ['admin', 'librarian']:
            notifications = Notification.query.order_by(Notification.created_at.desc()).limit(30).all()
        else:
            notifications = Notification.query.filter(
                (Notification.user_id == current_user.id) | (Notification.category == 'available')
            ).order_by(Notification.created_at.desc()).limit(20).all()
        for n in notifications:
            n.is_read = True
        db.session.commit()
        return render_template('hubs/notifications.html', notifications=notifications)

    elif hub_type == 'settings':
        log_activity(current_user.identifier, "Viewed Settings Hub")
        return render_template('hubs/settings_hub.html')

    abort(404)

@dash_bp.route('/add-book', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def add_book():
    if current_user.role not in ['librarian', 'admin']:
        log_security_event('UNAUTHORIZED_ACTION', 'Non-staff attempted to add book', current_user.identifier, request.remote_addr)
        abort(403)
    form = BookForm()
    if form.validate_on_submit():
        existing_book = Book.query.filter_by(isbn=form.isbn.data).first()
        if existing_book:
            flash(f"A book with ISBN {form.isbn.data} already exists!", "danger")
        else:
            saved_file_path = None
            if form.book_type.data == 'digital' and form.file_path.data:
                file = form.file_path.data
                filename = secure_filename(file.filename)
                if not filename:
                    flash("Invalid file name.", "danger")
                    return redirect(url_for('library_dashboard.dashboard', hub='librarian'))
                upload_folder = current_app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True)
                full_path = os.path.join(upload_folder, filename)
                file.save(full_path)
                saved_file_path = filename

            book = Book(
                title=form.title.data,
                author=form.author.data,
                isbn=form.isbn.data,
                genre=form.genre.data,
                book_type=form.book_type.data,
                file_path=saved_file_path
            )
            db.session.add(book)
            db.session.commit()
            log_activity(current_user.identifier, f"Added book: {book.title}")
            log_security_event('BOOK_ADDED', f'Book added: {book.title} by {book.author}', current_user.identifier, request.remote_addr)
            send_notification(f"New book '{book.title}' by {book.author} has been added to the library catalog and is available.", 'available')
            flash(f'Book "{book.title}" added successfully!', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {field}: {error}", 'danger')
    return redirect(url_for('library_dashboard.dashboard', hub='librarian'))

@dash_bp.route('/delete-book/<int:book_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def delete_book(book_id):
    if current_user.role not in ['librarian', 'admin']:
        abort(403)
    book = Book.query.get_or_404(book_id)
    title = book.title

    BorrowRecord.query.filter_by(book_id=book.id).delete()
    db.session.delete(book)
    db.session.commit()
    log_activity(current_user.identifier, f"Deleted book: {title}")
    log_security_event('BOOK_DELETED', f'Book deleted: {title}', current_user.identifier, request.remote_addr)
    flash(f'Book "{title}" was deleted.', 'success')
    return redirect(url_for('library_dashboard.dashboard', hub='librarian'))

@dash_bp.route('/borrow-book/<int:book_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def borrow_book(book_id):
    book = Book.query.get_or_404(book_id)
    now = datetime.utcnow()

    overdue_records = BorrowRecord.query.filter(
        BorrowRecord.user_id == current_user.id,
        BorrowRecord.status.in_(['Approved', 'Collected']),
        BorrowRecord.due_date < now
    ).all()

    if overdue_records:
        flash("You must return the due book that is with you before you can borrow again.", "warning")
        return redirect(url_for('library_dashboard.dashboard', hub='student'))

    if book.book_type == 'physical':
        active_physical = BorrowRecord.query.join(Book).filter(
            BorrowRecord.user_id == current_user.id,
            BorrowRecord.status.in_(['Pending', 'Approved', 'Collected']),
            Book.book_type == 'physical'
        ).first()

        if active_physical:
            flash("You can only borrow one physical book at a time.", "danger")
            return redirect(url_for('library_dashboard.dashboard', hub='student'))

        record = BorrowRecord(book_id=book.id, user_id=current_user.id, status='Pending')
        db.session.add(record)
        db.session.commit()
        log_activity(current_user.identifier, f"Requested physical book: {book.title}")
        send_notification(f"New pending request for physical book '{book.title}' by student {current_user.identifier}.", 'pending')
        flash(f'Request for "{book.title}" submitted to librarian.', 'success')

    else:
        record = BorrowRecord(
            book_id=book.id,
            user_id=current_user.id,
            status='Approved',
            due_date=now + timedelta(days=7)
        )
        db.session.add(record)
        db.session.commit()
        log_activity(current_user.identifier, f"Borrowed digital book: {book.title}")
        send_notification(f"Digital book '{book.title}' has been added to your collection.", 'reserved', user_id=current_user.id)
        flash(f'Digital book "{book.title}" added to your collection.', 'success')

    return redirect(url_for('library_dashboard.dashboard', hub='student'))

@dash_bp.route('/return-book/<int:record_id>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def return_book(record_id):
    record = BorrowRecord.query.get_or_404(record_id)
    if record.user_id != current_user.id:
        log_security_event('UNAUTHORIZED_RETURN', f'User {current_user.identifier} attempted to return another user\'s book', current_user.identifier, request.remote_addr)
        abort(403)

    record.status = 'Returned'
    record.returned_date = datetime.utcnow()
    db.session.commit()

    log_activity(current_user.identifier, f"Returned book: {record.book.title}")
    send_notification(f"Book '{record.book.title}' has been returned by user {current_user.identifier}.", 'returned', user_id=record.user_id)
    send_notification(f"Book '{record.book.title}' is now available for borrowing.", 'available')
    flash(f'You returned "{record.book.title}".', 'success')
    return redirect(url_for('library_dashboard.dashboard', hub='student'))

@dash_bp.route('/manage-request/<int:record_id>/<action>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def manage_request(record_id, action):
    if current_user.role not in ['librarian', 'admin']:
        log_security_event('UNAUTHORIZED_ACTION', 'Non-staff attempted to manage request', current_user.identifier, request.remote_addr)
        abort(403)

    record = BorrowRecord.query.get_or_404(record_id)
    if action == 'accept':
        record.status = 'Approved'
        record.due_date = datetime.utcnow() + timedelta(days=14)
        log_activity(current_user.identifier, f"Accepted physical book request for: {record.book.title} by user {record.user.identifier}")
        send_notification(f"Book '{record.book.title}' has been reserved for {record.user.username} ({record.user.identifier}).", 'reserved', user_id=record.user_id)
        flash('Request approved.', 'success')
    elif action == 'reject':
        record.status = 'Rejected'
        log_activity(current_user.identifier, f"Rejected physical book request for: {record.book.title} by user {record.user.identifier}")
        flash('Request rejected.', 'success')
    else:
        flash('Invalid action.', 'danger')
        return redirect(url_for('library_dashboard.dashboard', hub='librarian'))

    db.session.commit()
    return redirect(url_for('library_dashboard.dashboard', hub='librarian'))

@dash_bp.route('/admin/export-logs')
@login_required
@limiter.limit("3 per minute")
def export_logs():
    if current_user.role != 'admin':
        abort(403)

    log_activity(current_user.identifier, "Exported activity logs")
    log_security_event('LOGS_EXPORTED', 'Admin exported activity logs', current_user.identifier, request.remote_addr)
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).all()

    def generate():
        yield "ID\tIdentifier\tAction\tIP Address\tTimestamp(ms)\n"
        for log in logs:
            yield f"{log.id}\t{log.identifier}\t{log.action}\t{log.ip_address}\t{log.timestamp}\n"

    return Response(generate(), mimetype='text/plain', headers={"Content-Disposition": "attachment;filename=activity_logs.txt"})

@dash_bp.route('/read-digital/<int:record_id>')
@login_required
@limiter.limit("10 per minute")
def read_digital(record_id):
    record = BorrowRecord.query.get_or_404(record_id)
    if record.user_id != current_user.id or record.status != 'Approved' or record.book.book_type != 'digital':
        abort(403)

    if record.due_date and record.due_date < datetime.utcnow():
        flash("This digital book has expired.", "danger")
        return redirect(url_for('library_dashboard.dashboard', hub='student'))

    log_activity(current_user.identifier, f"Started reading digital book: {record.book.title}")
    return render_template('digital_reader.html', book=record.book)

@dash_bp.route('/delete-user/<int:user_id>', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def delete_user(user_id):
    user_to_delete = User.query.get_or_404(user_id)

    if current_user.role == 'admin':
        if user_to_delete.role not in ['student', 'librarian']:
            abort(403)
    elif current_user.role == 'librarian':
        if user_to_delete.role != 'student':
            abort(403)
    else:
        abort(403)

    if user_to_delete.id == current_user.id:
        flash("You cannot delete your own account!", "danger")
        log_security_event('SELF_DELETE_ATTEMPT', f'User attempted to delete own account', current_user.identifier, request.remote_addr)
        return redirect(url_for('library_dashboard.dashboard'))

    password = request.form.get('password', '')
    if not password or not check_password_hash(current_user.password, password):
        log_security_event('DELETE_FAILED', f'Invalid password for delete user {user_to_delete.identifier}', current_user.identifier, request.remote_addr)
        flash("Invalid password. Deletion cancelled.", "danger")
        return redirect(url_for('library_dashboard.dashboard'))

    BorrowRecord.query.filter_by(user_id=user_to_delete.id).delete()
    Notification.query.filter_by(user_id=user_to_delete.id).delete()

    deleted_identifier = user_to_delete.identifier
    deleted_role = user_to_delete.role

    db.session.delete(user_to_delete)
    db.session.commit()

    log_activity(current_user.identifier, f"Deleted user account: {deleted_identifier} ({deleted_role})")
    log_security_event('USER_DELETED', f'Deleted user: {deleted_identifier} ({deleted_role})', current_user.identifier, request.remote_addr)
    flash(f"Account for {deleted_identifier} has been deleted.", "success")

    if current_user.role == 'admin':
        return redirect(url_for('library_dashboard.dashboard', hub='admin'))
    else:
        return redirect(url_for('library_dashboard.dashboard', hub='librarian'))

@dash_bp.route('/manage-collection/<int:record_id>/<action>', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def manage_collection(record_id, action):
    if current_user.role not in ['librarian', 'admin']:
        abort(403)

    record = BorrowRecord.query.get_or_404(record_id)
    if action == 'collect':
        if record.status != 'Approved':
            flash("Only approved/reserved requests can be collected.", "warning")
            return redirect(url_for('library_dashboard.dashboard', hub='librarian'))

        record.status = 'Collected'
        db.session.commit()

        log_activity(current_user.identifier, f"Marked book as collected: {record.book.title} by {record.user.identifier}")
        send_notification(f"Student {record.user.identifier} has collected the book '{record.book.title}' from the library.", 'collected', user_id=record.user_id)
        flash(f"Book '{record.book.title}' marked as collected.", "success")

    elif action == 'return':
        if record.status not in ['Approved', 'Collected']:
            flash("Only approved or collected books can be returned.", "warning")
            return redirect(url_for('library_dashboard.dashboard', hub='librarian'))

        record.status = 'Returned'
        record.returned_date = datetime.utcnow()
        db.session.commit()

        log_activity(current_user.identifier, f"Librarian marked book as returned: {record.book.title} by {record.user.identifier}")
        send_notification(f"Book '{record.book.title}' has been returned by user {record.user.identifier}.", 'returned', user_id=record.user_id)
        send_notification(f"Book '{record.book.title}' is now available for borrowing.", 'available')
        flash(f"Book '{record.book.title}' marked as returned.", "success")

    else:
        flash('Invalid action.', 'danger')

    return redirect(url_for('library_dashboard.dashboard', hub='librarian'))
