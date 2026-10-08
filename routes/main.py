# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 03.12.2025
# Updated: 29.07.2026
# Website: https://bespredel.name

import os
import re
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from markupsafe import escape
from system.auth import (
    _safe_next_url,
    auth_enabled,
    get_authenticated_username,
    login_user,
    logout_user,
    verify_credentials,
)
from system.utils.app_context import get_app_context
from system.utils.counter_preview import preview_exists
from system.utils.i18n import trans as translate

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index() -> str:
    """
    Render the main index page.

    Returns:
        str: Rendered HTML template with list of available counters and their status
    """
    context = get_app_context()
    locations_dict = context['locations_dict']
    thread_manager = context['thread_manager']

    return render_template(
        'index.html',
        object_counters=locations_dict,
        running_counters=thread_manager.threads,
        counter_previews={loc: preview_exists(loc) for loc in locations_dict},
    )


@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Show login form or authenticate against config ``users``.
    
    Returns:
        str: Rendered HTML template for the login page
    """
    if not auth_enabled():
        flash(translate('Authentication is disabled (no users in config).'))
        return redirect(url_for('main.index'))

    next_url = _safe_next_url(request.values.get('next')) or url_for('main.index')
    if get_authenticated_username():
        return redirect(next_url)

    error = ''
    username = ''
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        if verify_credentials(username, password):
            login_user(username)
            flash(translate('Logged in successfully'))
            return redirect(next_url)
        error = translate('Invalid username or password')

    return render_template(
        'login.html',
        error=error,
        username=username,
        next_url=next_url,
    )


@main_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    Clear the session and return to the home page.
    
    Returns:
        str: Redirect to the home page
    """
    logout_user()
    flash(translate('You have been logged out.'))
    return redirect(url_for('main.index'))


@main_bp.route('/page/<string:name>')
def page(name: str = None) -> str:
    """
    Display a static page by name.

    Args:
        name (str): The name of the page to display

    Returns:
        str: Rendered HTML template for the requested page

    Raises:
        HTTPException: If the page is not found
    """
    page_name = str(escape(name))
    page_name = re.sub('[^A-Za-z0-9-_]+', '', page_name)

    if page_name == '':
        abort(404, translate('Page not found'))

    app = current_app
    path = os.path.join(app.root_path, 'templates', 'pages', page_name + '.html')
    if os.path.exists(path) is False or os.path.isfile(path) is False:
        abort(404, translate('Page not found'))

    return render_template('pages/' + page_name + '.html')
