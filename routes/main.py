# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 03.12.2025
# Updated: 03.06.2026
# Website: https://bespredel.name

import os
import re

from flask import Blueprint, abort, render_template
from flask import current_app, g
from markupsafe import escape

from system.utils.counter_preview import preview_exists
from system.utils.utils import trans as translate

main_bp = Blueprint('main', __name__)


def get_app_context():
    """Get application context from g or current_app.
    
    Returns:
        dict: Application context
    """
    if not hasattr(g, 'app_context'):
        g.app_context = current_app.config.get('APP_CONTEXT')
    return g.app_context


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
