# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 28.04.2025
# Website: https://bespredel.name

import json
import os
import re
from functools import wraps
from threading import Lock
from typing import Any

from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for
from flask_httpauth import HTTPBasicAuth
from flask_socketio import SocketIO
from markupsafe import escape
from werkzeug import Response
from werkzeug.security import check_password_hash, generate_password_hash

# from werkzeug.middleware.proxy_fix import ProxyFix  # For NGINX
from system.managers.config_manager import init_config
from system.managers.database_manager import DatabaseManager
from system.core.object_counter import ObjectCounter
from system.managers.thread_manager import ThreadManager
from system.utils.utils import get_system_info, is_ajax, slug, system_check, trans as translate
from system.db.models.base_model import TablePrefixBase

# --------------------------------------------------------------------------------
# Init and Config
# --------------------------------------------------------------------------------

# Init config
config = init_config()

# System check
system_check()

# Generate and save secret key if not set
if not config.get("server.secret_key"):
    secret_key = os.urandom(40).hex()
    config.set("server.secret_key", secret_key)
    config.save_config()

# General settings
debug = config.get("debug", False)
locations = list(config.get("detections", {}).keys())
locations_dict = dict([(k, v['label']) for k, v in config.get("detections", {}).items()])

# Start Flask
app = Flask(__name__)

# Fix for NGINX
# app.wsgi_app = ProxyFix(app.wsgi_app)  # For NGINX
# Config Flask
app.config['SECRET_KEY'] = config.get("server.secret_key")
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure Socket.IO
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

# Auth
auth = HTTPBasicAuth()
users = config.get("users", {})

# Set table prefix
TablePrefixBase.set_table_prefix(config.get("db.prefix", ""))

# Start DB
db_uri = config.get("db.uri") or "sqlite:///:memory:"
db_manager = DatabaseManager(uri=db_uri, prefix=config.get("db.prefix"))

# Init objects
object_counters: dict[str, ObjectCounter] = {}
thread_manager: ThreadManager = ThreadManager()
lock: Lock = Lock()


# --------------------------------------------------------------------------------
# Helpers functions
# --------------------------------------------------------------------------------

# Template filter
@app.template_filter('slug')
def _slug(string: str) -> str:
    """
    Convert a string to a URL-friendly slug.

    Args:
        string (str): The input string to convert

    Returns:
        str: URL-friendly slug version of the input string
    """
    if not string:
        return ""
    return slug(string)


@app.template_global()
def trans(string: str, **kwargs: dict) -> str:
    """
    Translate a string using the configured language.

    Args:
        string (str): The string to translate
        **kwargs (dict): Additional translation parameters

    Returns:
        str: Translated string
    """
    if kwargs.get('lang') is None:
        kwargs['lang'] = config.get('general.default_language', 'ru')
    return translate(string, **kwargs)


@app.template_global()
def counter_status(key: str) -> str:
    """
    Get the current status of a counter.

    Args:
        key (str): The counter identifier

    Returns:
        str: Status of the counter ('stopped', 'paused', or 'running')
    """
    if key not in thread_manager.threads:
        return 'stopped'
    if object_counters[key].is_pause():
        return 'paused'
    return 'running'


@app.template_global()
def counter_status_class(key: str) -> str:
    """
    Get the CSS class for a counter's status.

    Args:
        key (str): The counter identifier

    Returns:
        str: CSS class name based on counter status
    """
    if key not in thread_manager.threads:
        return 'secondary'
    if object_counters[key].is_pause():
        return 'warning'
    return 'success'


# Context processor
@app.context_processor
def utility_processor() -> dict:
    """
    Add global variables to all template contexts.

    Returns:
        dict: Dictionary containing global template variables
    """
    return dict(config=config)


# Auth handlers
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
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None


def object_detector_init(location: str) -> dict[Any, Any]:
    """
    Initialize an object detector for a specific location.

    Args:
        location (str): The identifier for the detection location

    Returns:
        dict[Any, Any]: Dictionary containing initialized object counters

    Note:
        This function is thread-safe and uses a global lock for synchronization
    """
    global object_counters, db_manager, socketio
    with lock:
        if location not in object_counters:
            detector_config = config.get("detections." + location)
            object_counters[location] = ObjectCounter(
                location=location,
                config_manager=config,
                socketio=socketio,
                video_path=detector_config['video_path'],
                db_manager=db_manager,
                weights=detector_config['weights_path'],
                counting_area=detector_config['counting_area'],
                counting_area_color=tuple(detector_config['counting_area_color'])
            )
    return object_counters


def require_location(f):
    """
    Decorator to check if a location exists in the object_counters dictionary.

    Args:
        f (function): The function to decorate

    Returns:
        function: Decorated function
    """

    @wraps(f)
    def decorated_function(location, *args, **kwargs):
        location = str(escape(location))
        if location not in object_counters:
            abort(400, trans('Detection config not found'))
        return f(location, *args, **kwargs)

    return decorated_function


def process_custom_fields(form_config: dict, current_count: dict) -> list:
    """
    Process custom fields for a specific location.

    Args:
        form_config (dict): The form configuration
        current_count (dict): The current count data

    Returns:
        list: List of processed custom fields
    """
    custom_fields = []
    for field in form_config.get('custom_fields', {}).values():
        field_copy = field.copy()
        field_copy['value'] = (
            current_count.get('custom_fields', {}).get(field['name'], "")
            if current_count and current_count.get('custom_fields')
            else form_config.get('default_value', "")
        )
        custom_fields.append(field_copy)
    return custom_fields


# --------------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------------

@app.route('/')
def index() -> str:
    """
    Render the main index page.

    Returns:
        str: Rendered HTML template with list of available counters and their status
    """
    return render_template(
        'index.html',
        object_counters=locations_dict,
        running_counters=thread_manager.threads)


@app.route('/counter/<string:location>')
@app.route('/counter/<string:location>/video')
def counter_video(location: str = None) -> str:
    """
    Display the video counter interface for a specific location.

    Args:
        location (str): The identifier for the detection location

    Returns:
        str: Rendered HTML template with video counter interface

    Raises:
        HTTPException: If the location configuration is not found
    """
    location = str(escape(location))
    if location not in locations:
        abort(400, trans('Detection config not found'))

    object_detector_init(location)
    if location in object_counters:
        thread_manager.start_thread(location, object_counters[location].run_frames)

    # Get form config
    form_config = config.get('form', {})

    # Process custom fields
    custom_fields = process_custom_fields(form_config, object_counters[location].get_current_count())

    return render_template(
        'counters/show_video.html',
        title=locations_dict.get(location, ),
        location=location,
        is_paused=object_counters[location].is_pause(),
        form_config=form_config,
        custom_fields=custom_fields,
        counter_on_sidebar=True
    )


@app.route('/counter_get_frames/<string:location>')
@require_location
def counter_get_frames(location: str = None) -> Response:
    """
    Stream video frames for a specific location.

    Args:
        location (str): The identifier for the detection location

    Returns:
        Response: MIME type response containing video frames
    """
    return Response(
        object_counters[location].get_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/counter/<string:location>/text')
def counter_text(location: str = None) -> str:
    """
    Display the text-based counter interface for a specific location.

    Args:
        location (str): The identifier for the detection location

    Returns:
        str: Rendered HTML template with text counter interface

    Raises:
        HTTPException: If the location configuration is not found
    """
    location = str(escape(location))
    if location not in locations:
        abort(400, trans('Detection config not found'))

    object_detector_init(location)
    if location in object_counters:
        thread_manager.start_thread(location, object_counters[location].run_frames)

    # Get form config
    form_config = config.get('form', {})

    # Process custom fields
    custom_fields = process_custom_fields(form_config, object_counters[location].get_current_count())

    return render_template(
        'counters/show_text.html',
        title=locations_dict.get(location, ),
        location=location,
        is_paused=object_counters[location].is_pause(),
        form_config=form_config,
        custom_fields=custom_fields,
        # counter_on_sidebar=False
    )


@app.route('/counter_dual/<string:location_first>/<string:location_second>')
@app.route('/counter_dual/text/<string:location_first>/<string:location_second>')
def counter_dual_text(location_first: str, location_second: str) -> str:
    """
    Display a dual counter interface for two locations.

    Args:
        location_first (str): The identifier for the first detection location
        location_second (str): The identifier for the second detection location

    Returns:
        str: Rendered HTML template with dual counter interface

    Raises:
        HTTPException: If either location configuration is not found
    """
    location_first = str(escape(location_first))
    location_second = str(escape(location_second))
    if location_first not in locations or location_second not in locations:
        abort(400, trans('Detection config not found'))

    # Init objects and threads for first location
    object_detector_init(location_first)
    if location_first in object_counters:
        thread_manager.start_thread(location_first, object_counters[location_first].run_frames)

    # Init objects and threads for second location
    object_detector_init(location_second)
    if location_second in object_counters:
        thread_manager.start_thread(location_second, object_counters[location_second].run_frames)

    # Page title
    title = locations_dict.get(location_first, ) + ' - ' + locations_dict.get(location_second, )

    return render_template(
        'counters/show_text_multi.html',
        title=title,
        location_in=location_first,
        location_out=location_second,
        location_in_label=locations_dict.get(location_first, ),
        location_out_label=locations_dict.get(location_second, ),
    )


# --------------------------------------------------------------------------------

@app.route('/save_count/<string:location>', methods=['POST'])
@require_location
def save_count(location: str = None) -> dict:
    """
    Save the current count for a specific location.

    Args:
        location (str): The identifier for the detection location

    Returns:
        dict: Dictionary containing total, defect, and correct counts
    """
    correct_count = int(escape(request.form['correct_count']))
    defect_count = int(escape(request.form['defect_count']))
    custom_fields = request.form['custom_fields'] if 'custom_fields' in request.form else ""
    result = object_counters[location].save_count(
        location=location,
        correct_count=correct_count,
        defect_count=defect_count,
        custom_fields=custom_fields,
        active=1
    )

    return {
        'total_count': result['total'],
        'defect_count': result['defect'],
        'correct_count': result['correct']
    }


@app.route('/reset_count/<string:location>')
@require_location
def reset_count(location: str = None) -> dict:
    """
    Reset the counter for a specific location.

    Args:
        location (str): The identifier for the detection location

    Returns:
        dict: Dictionary with reset counts (all set to 0)
    """
    object_counters[location].reset_count(location=location)
    return {'total_count': 0, 'defect_count': 0, 'correct_count': 0}


@app.route('/reset_count_current/<string:location>', methods=['POST'])
@require_location
def reset_count_current(location: str = None) -> dict:
    """
    Reset the current count for a specific location.

    Args:
        location (str): The identifier for the detection location

    Returns:
        dict: Dictionary with current count set to 0
    """
    correct_count = int(escape(request.form['correct_count']))
    defect_count = int(escape(request.form['defect_count']))
    object_counters[location].reset_count_current(
        location=location,
        correct_count=correct_count,
        defect_count=defect_count
    )
    return {'current_count': 0}


@app.route('/save_capture/<string:location>')
@require_location
def save_capture(location: str = None) -> dict[str, str] | Response:
    """
    Save a capture from the current video frame.

    Args:
        location (str): The identifier for the detection location

    Returns:
        dict[str, str] | Response: Status response or redirect
    """
    object_counters[location].save_capture()

    if is_ajax() is True:
        return {'status': 'saved'}
    return redirect(url_for('index'))


# --------------------------------------------------------------------------------

@app.route('/start_count/<string:location>')
@require_location
def start_count(location: str = None) -> dict[str, str] | Response:
    """
    Start the counter for a specific location.

    Args:
        location (str): The identifier for the detection location

    Returns:
        dict[str, str] | Response: Status response or redirect
    """
    object_counters[location].start()

    if is_ajax() is True:
        return {'status': 'started'}
    return redirect(url_for('index'))


@app.route('/pause_count/<string:location>')
@require_location
def pause_count(location: str = None) -> dict[str, str] | Response:
    """
    Pause the counter for a specific location.

    Args:
        location (str): The identifier for the detection location

    Returns:
        dict[str, str] | Response: Status response or redirect
    """
    object_counters[location].pause()

    if is_ajax() is True:
        return {'status': 'paused'}
    return redirect(url_for('index'))


@app.route('/stop_count/<string:location>')
@require_location
def stop_count(location: str = None) -> dict[str, str] | Response:
    """
    Stop the counter for a specific location.

    Args:
        location (str): The identifier for the detection location

    Returns:
        dict[str, str] | Response: Status response or redirect
    """
    object_counters[location].stop()
    del object_counters[location]
    thread_manager.stop_thread(location)

    if is_ajax() is True:
        return {'status': 'stopped'}
    return redirect(url_for('index'))


# --------------------------------------------------------------------------------

@app.route('/settings')
@auth.login_required
def settings() -> str:
    """
    Display the application settings page.

    Returns:
        str: Rendered HTML template with settings interface

    Note:
        This route requires authentication
    """
    return render_template('settings.html', _config=config.read_config())


@app.route('/settings_save', methods=['POST'])
@auth.login_required
def settings_save() -> Response:
    """
    Save application settings.

    Returns:
        Response: Redirect to settings page with flash message

    Note:
        This route requires authentication
    """
    form_data = request.form.to_dict()

    # Retrieving users from a form and encrypting passwords
    for key, value in form_data.items():
        if key.startswith('users-'):
            if value == '':
                form_data[key] = config.get('users.' + key.replace('users-', ''))
            else:
                form_data[key] = generate_password_hash(value)

    # Saving updated form data to a configuration file
    config.save_from_request(form_data)

    flash(trans('Settings saved'))
    return redirect(url_for('settings'))


# --------------------------------------------------------------------------------

@app.route('/reports')
def reports() -> str:
    """
    Display the main reports page.

    Returns:
        str: Rendered HTML template with reports overview
    """
    return render_template(
        'reports/index.html',
        object_counters=locations_dict
    )


@app.route('/reports/<string:location>')
def report_list(location: str = None) -> str:
    """
    Display paginated list of reports for a specific location.

    Args:
        location (str): The identifier for the detection location

    Returns:
        str: Rendered HTML template with paginated reports list

    Raises:
        HTTPException: If the location is not found or invalid
    """
    r_page = request.args.get('page', 1, type=int)
    per_page = 10

    if location is None:
        abort(404, trans('Page not found'))

    pagination = db_manager.get_paginated(location, r_page, per_page)

    if pagination is None:
        abort(404, trans('Page not found'))

    items = pagination['results']
    current_page = pagination['page']
    total_items = pagination['total']
    total_pages = (total_items + per_page - 1) // per_page

    return render_template(
        'reports/list.html',
        object_counters=locations_dict,
        items=items,
        location=location,
        current_page=current_page,
        total_pages=total_pages,
        json=json
    )


@app.route('/reports/<string:location>/<int:id>')
def report_show(location: str, id: int) -> str:
    """
    Display detailed view of a specific report.

    Args:
        location (str): The identifier for the detection location
        id (int): The report ID

    Returns:
        str: Rendered HTML template with report details

    Raises:
        HTTPException: If the report is not found
    """
    counter = db_manager.get_count(id)

    if counter is None:
        abort(404, trans('Page not found'))

    return render_template(
        'reports/show.html',
        location=location,
        counter=counter,
        json=json
    )


# --------------------------------------------------------------------------------

@app.route('/system_info')
@auth.login_required
def system_info() -> str:
    """
    Display system information page.

    Returns:
        str: Rendered HTML template with system information

    Note:
        This route requires authentication
    """
    sys_info = get_system_info()
    return render_template('system_info.html', sys_info=sys_info)


@app.route('/page/<string:name>')
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
        abort(404, trans('Page not found'))

    path = os.path.join(app.root_path, 'templates', 'pages', page_name + '.html')
    if os.path.exists(path) is False or os.path.isfile(path) is False:
        abort(404, trans('Page not found'))

    return render_template('pages/' + page_name + '.html')


# --------------------------------------------------------------------------------
# Server run
# --------------------------------------------------------------------------------

if __name__ == '__main__':
    """
    Main entry point for the application.
    Starts the Flask development server with configured settings.
    """
    socketio.run(
        app,
        host=config.get('server.host'),
        port=config.get('server.port', 8080),
        debug=config.get('general.debug', False),
        log_output=config.get('server.log_output', True),
        use_reloader=config.get('server.use_reloader', False),
        allow_unsafe_werkzeug=config.get('general.allow_unsafe_werkzeug', config.get('general.debug', False))
    )
