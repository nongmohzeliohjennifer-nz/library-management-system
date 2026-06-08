from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app import limiter

api_bp = Blueprint('api', __name__)

@api_bp.route('/my-books', methods=['GET'])
@limiter.limit("10 per minute") # Rate limiting for API security
@login_required
def get_my_books():
    """
    A protected API endpoint that returns JSON data for the authenticated user.
    """
    data = {
        "user": current_user.username,
        "role": current_user.role,
        "status": "active",
        "message": "Secure API connection established."
    }
    return jsonify(data), 200