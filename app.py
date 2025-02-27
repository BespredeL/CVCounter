# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 23.01.2025
# Website: https://bespredel.name

import json
import os
import re
from threading import Lock, Thread
from typing import Any

from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for
from flask_httpauth import HTTPBasicAuth
from flask_socketio import SocketIO
from markupsafe import escape
from werkzeug import Response
from werkzeug.security import check_password_hash, generate_password_hash

# from werkzeug.middleware.proxy_fix import ProxyFix  # For NGINX
from config import config
from system.database_manager import DatabaseManager
from system.object_counter import ObjectCounter
from system.utils import get_system_info, is_ajax, slug, system_check, trans as translate

# --------------------------------------------------------------------------------
# Init and Config
# --------------------------------------------------------------------------------

# System check
system_check()

# General settings
debug = config.get("debug", False)
locations = list(config.get("detections", {}).keys())
locations_dict = dict([(k, v['label']) for k, v in config.get("detections", {}).items()])

# Start Flask
app = Flask(__name__)

# Fix for NGINX
# app.wsgi_app = ProxyFix(app.wsgi_app)  # For NGINX
# Config Flask
app.config['SECRET_KEY'] = config.get("server.secret_key", os.urandom(40))
app.config["TEMPLATES_AUTO_RELOAD"] = True
socketio = SocketIO(app)

# Auth
auth = HTTPBasicAuth()
users = config.get("users", {})

# Start DB
db_manager = DatabaseManager(uri=config.get("db.uri", "sqlite:///:memory:"), prefix=config.get("db.prefix"))

# Init objects
object_counters: dict[str, ObjectCounter] = {}
threading_detectors: dict[str, Thread] = {}
lock: Lock = Lock()


# --------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------

# Template filter
@app.template_filter('slug')
def _slug(string: str) -> str:
    if not string:
        return ""
    return slug(string)


@app.template_global()
def trans(string: str, **kwargs: dict) -> str:
    if kwargs.get('lang') is None:
        kwargs['lang'] = config.get('general.default_language', 'ru')
    return translate(string, **kwargs)


@app.template_global()
def counter_status(key: str) -> str:
    if key not in threading_detectors:
        return 'stopped'
    if object_counters[key].is_pause():
        return 'paused'
    return 'running'


@app.template_global()
def counter_status_class(key: str) -> str:
    if key not in threading_detectors:
        return 'secondary'
    if object_counters[key].is_pause():
        return 'warning'
    return 'success'


# Context processor
@app.context_processor
def utility_processor() -> dict:
    return dict(config=config)


# Auth handlers
@auth.verify_password
def verify_password(username: str, password: str) -> str | None:
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None


# --------------------------------------------------------------------------------
# Functions
# --------------------------------------------------------------------------------

def object_detector_init(location: str) -> dict[Any, Any]:
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


# --------------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------------

@app.route('/')
def index() -> str:
    return render_template(
        'index.html',
        object_counters=locations_dict,
        running_counters=threading_detectors)


@app.route('/counter/<string:location>')
@app.route('/counter/<string:location>/video')
def counter_video(location: str = None) -> str:
    location = str(escape(location))
    if location not in locations:
        abort(400, trans('Detection config not found'))

    object_detector_init(location)
    with lock:
        if location not in threading_detectors and location in object_counters:
            threading_detectors[location] = Thread(target=object_counters[location].run_frames)
            threading_detectors[location].start()

    # Get form config
    form_config = config.get('form', {})

    # Process custom fields
    custom_fields = []
    current_count = object_counters[location].get_current_count()
    for field in form_config.get('custom_fields', {}).values():
        field_copy = field.copy()
        if current_count and current_count['custom_fields']:
            field_copy['value'] = current_count['custom_fields'].get(field['name'], "")
        else:
            field_copy['value'] = form_config['default_value'] if 'default_value' in form_config else ""
        custom_fields.append(field_copy)

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
def counter_get_frames(location: str = None) -> Response:
    location = str(escape(location))
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    return Response(
        object_counters[location].get_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/counter/<string:location>/text')
def counter_text(location: str = None) -> str:
    location = str(escape(location))
    if location not in locations:
        abort(400, trans('Detection config not found'))

    object_detector_init(location)
    with lock:
        if location not in threading_detectors and location in object_counters:
            threading_detectors[location] = Thread(target=object_counters[location].run_frames)
            threading_detectors[location].start()

    # Get form config
    form_config = config.get('form', {})

    # Process custom fields
    custom_fields = []
    current_count = object_counters[location].get_current_count()
    for field in form_config.get('custom_fields', {}).values():
        field_copy = field.copy()
        if current_count and current_count['custom_fields']:
            field_copy['value'] = current_count['custom_fields'].get(field['name'], "")
        else:
            field_copy['value'] = form_config['default_value'] if 'default_value' in form_config else ""
        custom_fields.append(field_copy)

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
    location_first = str(escape(location_first))
    location_second = str(escape(location_second))
    if location_first not in locations or location_second not in locations:
        abort(400, trans('Detection config not found'))

    # Init objects and threads for first location
    object_detector_init(location_first)
    with lock:
        if location_first not in threading_detectors and location_first in object_counters:
            threading_detectors[location_first] = Thread(target=object_counters[location_first].run_frames)
            threading_detectors[location_first].start()

    # Init objects and threads for second location
    object_detector_init(location_second)
    with lock:
        if location_second not in threading_detectors and location_second in object_counters:
            threading_detectors[location_second] = Thread(target=object_counters[location_second].run_frames)
            threading_detectors[location_second].start()

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
def save_count(location: str = None) -> dict:
    location = str(escape(location))
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

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

    # object_detectors[name].reset_count()
    return {
        'total_count': result['total'],
        'defect_count': result['defect'],
        'correct_count': result['correct']
    }


@app.route('/reset_count/<string:location>')
def reset_count(location: str = None) -> dict:
    location = str(escape(location))
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    object_counters[location].reset_count(location=location)

    return {'total_count': 0, 'defect_count': 0, 'correct_count': 0}


@app.route('/reset_count_current/<string:location>', methods=['POST'])
def reset_count_current(location: str = None) -> dict:
    location = str(escape(location))
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    correct_count = int(escape(request.form['correct_count']))
    defect_count = int(escape(request.form['defect_count']))
    object_counters[location].reset_count_current(
        location=location,
        correct_count=correct_count,
        defect_count=defect_count
    )

    return {'current_count': 0}


@app.route('/save_capture/<string:location>')
def save_capture(location: str = None) -> dict[str, str] | Response:
    location = str(escape(location))
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    object_counters[location].save_capture()

    if is_ajax() is True:
        return {'status': 'saved'}
    return redirect(url_for('index'))


# --------------------------------------------------------------------------------

@app.route('/start_count/<string:location>')
def start_count(location: str = None) -> dict[str, str] | Response:
    location = str(escape(location))
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    object_counters[location].start()

    if is_ajax() is True:
        return {'status': 'started'}
    return redirect(url_for('index'))


@app.route('/pause_count/<string:location>')
def pause_count(location: str = None) -> dict[str, str] | Response:
    location = str(escape(location))
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    object_counters[location].pause()

    if is_ajax() is True:
        return {'status': 'paused'}
    return redirect(url_for('index'))


@app.route('/stop_count/<string:location>')
def stop_count(location: str = None) -> dict[str, str] | Response:
    location = str(escape(location))
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    object_counters[location].stop()
    del object_counters[location]
    del threading_detectors[location]

    if is_ajax() is True:
        return {'status': 'stopped'}
    return redirect(url_for('index'))


# --------------------------------------------------------------------------------

@app.route('/settings')
@auth.login_required
def settings() -> str:
    return render_template('settings.html', _config=config.read_config())


@app.route('/settings_save', methods=['POST'])
@auth.login_required
def settings_save() -> Response:
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
    return render_template(
        'reports/index.html',
        object_counters=locations_dict
    )


@app.route('/reports/<string:location>')
def report_list(location: str = None) -> str:
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
    sys_info = get_system_info()
    return render_template('system_info.html', sys_info=sys_info)


# --------------------------------------------------------------------------------

@app.route('/page/<string:name>')
def page(name: str = None) -> str:
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
    socketio.run(
        app,
        host=config.get('server.host'),
        port=config.get('server.port', 80),
        debug=config.get('general.debug', False),
        log_output=config.get('server.log_output', True),
        use_reloader=config.get('server.use_reloader', False),
        allow_unsafe_werkzeug=config.get('general.allow_unsafe_werkzeug', config.get('general.debug', False))
    )
