from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User

def role_required(role):
    """Decorator to require specific role"""
    def decorator(fn):
        @wraps(fn)
        @jwt_required(locations=["cookies"])
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            user = User.query.get(int(user_id))
            if not user or user.role != role:
                return jsonify({"msg": "Access denied"}), 403
            return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__
        return wrapper
    return decorator
