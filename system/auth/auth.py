# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 22.01.2026
# Updated: 22.01.2026
# Website: https://bespredel.name

from functools import wraps

from flask import current_app, g
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash as werkzeug_check_password_hash, generate_password_hash as werkzeug_generate_password_hash


def get_app_context():
    """
    Get application context from g or current_app.
    
    Returns:
        dict: Application context dictionary
    """
    if not hasattr(g, 'app_context'):
        g.app_context = current_app.config.get('APP_CONTEXT')
    return g.app_context


def get_auth() -> HTTPBasicAuth:
    """
    Get auth instance from app context.
    
    Returns:
        HTTPBasicAuth: HTTPBasicAuth instance
    """
    context = get_app_context()
    return context['auth']


def setup_auth(context: dict = None) -> HTTPBasicAuth:
    """
    Setup and configure authentication.
    
    This function configures the password verification callback for HTTPBasicAuth.
    It should be called once during application initialization.
    The function is idempotent - it can be called multiple times safely.
    
    Args:
        context (dict, optional): Application context dictionary. If not provided,
                                 will try to get it from Flask's application context.
    
    Returns:
        HTTPBasicAuth: Configured HTTPBasicAuth instance
    """
    # Get auth instance
    if context is not None:
        auth = context['auth']
        users = context['users']
    else:
        # Try to get from Flask context (for runtime use)
        try:
            auth = get_auth()
            context = get_app_context()
            users = context['users']
        except RuntimeError:
            # Working outside of application context
            raise RuntimeError(
                "setup_auth() called without context and outside Flask application context. "
                "Provide context parameter during initialization."
            )

    # Check if verify_password is already set to avoid re-registration
    if not hasattr(auth, '_cvcounter_configured'):
        @auth.verify_password
        def verify_password(username: str, password: str) -> str | None:
            """
            Verify user credentials for authentication.
            
            Args:
                username (str): The username to verify
                password (str): The password to verify
            
            Returns:
                str | None: Username if credentials are valid, None otherwise
            """
            # Get users from context (may have been updated)
            if context is not None:
                current_users = context['users']
            else:
                try:
                    current_context = get_app_context()
                    current_users = current_context['users']
                except RuntimeError:
                    current_users = users

            if username in current_users and werkzeug_check_password_hash(current_users.get(username), password):
                return username
            return None

        # Mark as configured to avoid re-registration
        auth._cvcounter_configured = True

    return auth


def login_required(f):
    """
    Decorator to require authentication for a route.
    
    Usage:
        @blueprint.route('/protected')
        @login_required
        def protected_route():
            return "This requires authentication"
    
    Args:
        f: The function to decorate
    
    Returns:
        function: Decorated function that requires authentication
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = setup_auth()

        @auth.login_required
        def _wrapped():
            return f(*args, **kwargs)

        return _wrapped()

    return decorated_function


# Re-export werkzeug password functions for convenience
def generate_password_hash(password: str) -> str:
    """
    Generate a password hash.
    
    Args:
        password (str): Plain text password
    
    Returns:
        str: Hashed password
    """
    return werkzeug_generate_password_hash(password)


def check_password_hash(pwhash: str, password: str) -> bool:
    """
    Check if a password matches a hash.
    
    Args:
        pwhash (str): Password hash
        password (str): Plain text password to check
    
    Returns:
        bool: True if password matches hash, False otherwise
    """
    return werkzeug_check_password_hash(pwhash, password)
