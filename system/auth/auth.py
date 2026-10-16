# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 22.01.2026
# Updated: 29.07.2026
# Website: https://bespredel.name

from __future__ import annotations
from functools import wraps
from typing import Optional
from urllib.parse import urljoin, urlparse
from flask import (
    flash,
    current_app,
    has_app_context,
    has_request_context,
    jsonify,
    redirect,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash as werkzeug_check_password_hash
from werkzeug.security import generate_password_hash as werkzeug_generate_password_hash
from system.utils.app_context import get_app_context
from system.utils.i18n import trans as translate
from system.utils.utils import is_ajax

SESSION_USER_KEY = 'auth_user'


def _users() -> dict:
    """
    Return the users dictionary from the app context.
    
    Returns:
        dict: The users dictionary
    """
    try:
        return dict(get_app_context().get('users') or {})
    except RuntimeError:
        return {}


def auth_enabled() -> bool:
    """
    Return True when at least one user is configured.
    
    Returns:
        bool: True if at least one user is configured
    """
    return bool(_users())


def setup_auth(context: dict = None, app=None):
    """
    Configure session cookie defaults for auth.

    Args:
        context: Application context (optional, kept for API compatibility).
        app: Flask application instance (optional).

    Returns:
        None
    """
    flask_app = app
    if flask_app is None and has_app_context():
        flask_app = current_app
    if flask_app is not None:
        flask_app.config.setdefault('SESSION_COOKIE_HTTPONLY', True)
        flask_app.config.setdefault('SESSION_COOKIE_SAMESITE', 'Lax')
    return None


def get_auth():
    """
    Deprecated compatibility stub (Basic Auth removed).
    
    Returns:
        None
    """
    return None


def verify_credentials(username: str, password: str) -> bool:
    """
    Verify username/password against config ``users`` hashes.

    Args:
        username: Login name.
        password: Plain-text password.

    Returns:
        bool: True if credentials are valid.
    """
    if not username or password is None:
        return False
    users = _users()
    stored = users.get(username)
    if not stored:
        return False
    try:
        return bool(werkzeug_check_password_hash(stored, password))
    except (ValueError, TypeError):
        return False


def login_user(username: str) -> None:
    """
    Store authenticated username in the Flask session.
    
    Args:
        username (str): The username to store
    
    Returns:
        None
    """
    session[SESSION_USER_KEY] = username
    session.permanent = True


def logout_user() -> None:
    """
    Clear authentication from the Flask session.
    
    Returns:
        None
    """
    session.pop(SESSION_USER_KEY, None)
    session.modified = True


def get_authenticated_username() -> Optional[str]:
    """
    Return the logged-in username from the session, if still valid in config.

    Returns:
        str | None: Username or None.
    """
    if not has_request_context():
        return None
    if not auth_enabled():
        return None

    username = session.get(SESSION_USER_KEY)
    if not username:
        return None
    if username not in _users():
        logout_user()
        return None
    return str(username)


def _safe_next_url(target: Optional[str]) -> Optional[str]:
    """
    Allow only relative same-host redirects.
    
    Args:
        target (Optional[str]): The target URL
    
    Returns:
        Optional[str]: The safe next URL
    """
    if not target:
        return None
    target = target.strip()
    if not target.startswith('/') or target.startswith('//'):
        return None
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, target))
    if test.scheme not in ('http', 'https') or ref.netloc != test.netloc:
        return None
    return target


def login_required(f):
    """
    Require a valid session when users are configured.
    
    Args:
        f: The function to decorate
    
    Returns:
        function: The decorated function
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not auth_enabled():
            return f(*args, **kwargs)

        if get_authenticated_username():
            return f(*args, **kwargs)

        if is_ajax() or request.accept_mimetypes.best == 'application/json':
            return jsonify({
                'status': 'error',
                'message': translate('Authentication required to access this resource.'),
            }), 401

        next_url = request.full_path if request.query_string else request.path
        if next_url.endswith('?'):
            next_url = next_url[:-1]
        return redirect(url_for('main.login', next=next_url))

    return decorated_function


def generate_password_hash(password: str) -> str:
    """
    Generate a password hash for storage in config ``users``.
    
    Args:
        password (str): The password to hash
    
    Returns:
        str: The generated password hash
    """
    return werkzeug_generate_password_hash(password)


def check_password_hash(pwhash: str, password: str) -> bool:
    """
    Check if a password matches a hash.
    
    Args:
        pwhash (str): The password hash to check
        password (str): The password to check
    
    Returns:
        bool: True if the password matches the hash
    """
    return werkzeug_check_password_hash(pwhash, password)


# Re-export helper used by login route
__all__ = [
    'SESSION_USER_KEY',
    'auth_enabled',
    'setup_auth',
    'get_auth',
    'verify_credentials',
    'login_user',
    'logout_user',
    'get_authenticated_username',
    'login_required',
    'generate_password_hash',
    'check_password_hash',
    '_safe_next_url',
]
