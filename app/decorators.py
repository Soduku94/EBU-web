from functools import wraps
from flask_login import current_user
from flask import abort

def admin_required(f):
    """
    Chỉ cho phép Admin truy cập.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role.name != 'Admin':
            abort(403) # Trả về lỗi 403 Forbidden (Cấm truy cập)
        return f(*args, **kwargs)
    return decorated_function