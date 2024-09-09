# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 09.09.2024
# Website: https://bespredel.name

import os
import re
from threading import Lock, Thread

import gpustat
import psutil
from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for
from flask_httpauth import HTTPBasicAuth
from flask_socketio import SocketIO
from markupsafe import escape
from werkzeug.security import check_password_hash, generate_password_hash

from system.ConfigManager import ConfigManager
from system.DatabaseManager import DatabaseManager
from system.ObjectCounter import ObjectCounter
from system.helpers import slug, trans as translate

# --------------------------------------------------------------------------------
# Init
# --------------------------------------------------------------------------------

# Read config
config = ConfigManager("config.json")
config.read_config()

# Default settings
debug = config.get("debug", False)
locations = list(config.get("detections", {}).keys())
locations_dict = dict([(k, v['label']) for k, v in config.get("detections", {}).items()])

# Start Flask
app = Flask(__name__)

# Auth
auth = HTTPBasicAuth()
users = config.get("users", {})

app.config['SECRET_KEY'] = config.get("server.secret_key", False)
app.config['DATABASE'] = config.get("db", False)
app.config["TEMPLATES_AUTO_RELOAD"] = True
socketio = SocketIO(app)

# Start DB
db_manager = DatabaseManager(
    config.get('db.host'),
    config.get('db.user'),
    config.get('db.password'),
    config.get('db.database'),
    config.get('db.prefix')
)

# Init objects
object_counters = {}
threading_detectors = {}
lock = Lock()


# --------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------

# Template filter
@app.template_filter('slug')
def _slug(string):
    if not string:
        return ""
    return slug(string)


@app.template_global()
def trans(string):
    return translate(string)


@app.template_global()
def counter_status(key):
    if key not in threading_detectors:
        return 'stopped'
    if object_counters[key].is_pause():
        return 'paused'
    return 'running'


@app.template_global()
def counter_status_class(key):
    if key not in threading_detectors:
        return 'secondary'
    if object_counters[key].is_pause():
        return 'warning'
    return 'success'


# Context processor
@app.context_processor
def utility_processor():
    return dict(config=config)


# Auth handlers
@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None


# --------------------------------------------------------------------------------
# Functions
# --------------------------------------------------------------------------------

def object_detector_init(location):
    global object_counters, config, db_manager, socketio
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


def is_ajax():
    return str(request.headers.get('X-Requested-With')).lower() == 'XMLHttpRequest'.lower()


# --------------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template(
        'index.html',
        object_counters=locations_dict,
        running_counters=threading_detectors)


@app.route('/counter/<string:location>')
def counter(location=None):
    location = escape(location)
    if location not in locations:
        abort(400, trans('Detection config not found'))

    object_detector_init(location)
    with lock:
        if location not in threading_detectors and location in object_counters:
            threading_detectors[location] = Thread(target=object_counters[location].run_frames)
            threading_detectors[location].start()

    # items = db_client.get_items()

    return render_template(
        'counter.html',
        title=locations_dict.get(location, ),
        location=location,
        # items=items,
        is_paused=object_counters[location].is_pause(),
        counter_on_sidebar=True
    )


@app.route('/get_frames/<string:location>')
def get_frames(location=None):
    location = escape(location)
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    return Response(
        object_counters[location].get_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/counter_t/<string:location>')
def counter_t(location=None):
    location = escape(location)
    if location not in locations:
        abort(400, trans('Detection config not found'))

    object_detector_init(location)
    with lock:
        if location not in threading_detectors and location in object_counters:
            threading_detectors[location] = Thread(target=object_counters[location].count_run)
            threading_detectors[location].start()

    # items = db_client.get_items()

    return render_template(
        'counter_text.html',
        title=locations_dict.get(location, ),
        location=location,
        # items=items,
        is_paused=object_counters[location].is_pause(),
        # counter_on_sidebar=False
    )


@app.route('/counter_t_multi/<string:location_first>/<string:location_second>')
def counter_t_multi(location_first, location_second):
    location_first = escape(location_first)
    location_second = escape(location_second)
    if location_first not in locations or location_second not in locations:
        abort(400, trans('Detection config not found'))

    # Init objects and threads for first location
    object_detector_init(location_first)
    with lock:
        if location_first not in threading_detectors and location_first in object_counters:
            threading_detectors[location_first] = Thread(target=object_counters[location_first].count_run)
            threading_detectors[location_first].start()

    # Init objects and threads for second location
    object_detector_init(location_second)
    with lock:
        if location_second not in threading_detectors and location_second in object_counters:
            threading_detectors[location_second] = Thread(target=object_counters[location_second].count_run)
            threading_detectors[location_second].start()

    # Page title
    title = locations_dict.get(location_first, ) + ' - ' + locations_dict.get(location_second, )

    return render_template(
        'counter_text_multi.html',
        title=title,
        location_in=location_first,
        location_out=location_second,
        location_in_label=locations_dict.get(location_first, ),
        location_out_label=locations_dict.get(location_second, ),
    )


# --------------------------------------------------------------------------------

@app.route('/save_count/<string:location>', methods=['POST'])
def save_count(location=None):
    location = escape(location)
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    item_no = ""  # request.form['item_no']
    correct_count = request.form['correct_count']
    defect_count = request.form['defect_count']
    result = object_counters[location].save_count(
        location=location,
        name=item_no,
        correct_count=correct_count,
        defect_count=defect_count,
        active=1
    )

    # object_detectors[name].reset_count()
    return {'total_count': result['total'], 'defect_count': result['defect'], 'correct_count': result['correct']}


@app.route('/reset_count/<string:location>')
def reset_count(location=None):
    location = escape(location)
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    object_counters[location].reset_count(location=location)

    return {'total_count': 0, 'defect_count': 0, 'correct_count': 0}


@app.route('/reset_count_current/<string:location>', methods=['POST'])
def reset_count_current(location=None):
    location = escape(location)
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    item_no = request.form['item_no']
    correct_count = request.form['correct_count']
    defect_count = request.form['defect_count']
    object_counters[location].reset_count_current(
        location=location,
        name=item_no,
        correct_count=correct_count,
        defect_count=defect_count
    )

    return {'current_count': 0}


# --------------------------------------------------------------------------------

@app.route('/start_count/<string:location>')
def start_count(location=None):
    location = escape(location)
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    object_counters[location].start()

    if is_ajax() is True:
        return {'status': 'started'}
    return redirect(url_for('index'))


@app.route('/pause_count/<string:location>')
def pause_count(location=None):
    location = escape(location)
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    object_counters[location].pause()

    if is_ajax() is True:
        return {'status': 'paused'}
    return redirect(url_for('index'))


@app.route('/stop_count/<string:location>')
def stop_count(location=None):
    location = escape(location)
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
def settings():
    _config = ConfigManager("config.json")
    return render_template('settings.html', config=_config.read_config())


@app.route('/settings_save', methods=['POST'])
@auth.login_required
def settings_save():
    form_data = request.form.to_dict()

    # Retrieving users from a form and encrypting passwords
    for key, value in form_data.items():
        if key.startswith('users-'):
            form_data[key] = generate_password_hash(value)

    # Saving updated form data to a configuration file
    _config = ConfigManager("config.json")
    _config.save_from_request(form_data)

    flash(trans('Settings saved'))
    return redirect(url_for('settings'))


@app.route('/page/<string:name>')
def page(name):
    page_name = escape(name)
    page_name = re.sub('[^A-Za-z0-9-_]+', '', page_name)

    if page_name == '':
        abort(404, trans('Page not found'))

    path = os.path.join(app.root_path, 'templates', 'pages', page_name + '.html')
    if os.path.exists(path) is False or os.path.isfile(path) is False:
        abort(404, trans('Page not found'))

    return render_template('pages/' + page_name + '.html')


@app.route('/get_system_load')
def get_system_load():
    kb = float(1024)
    mb = float(kb ** 2)
    gb = float(kb ** 3)

    cpu_percent = round(float(psutil.cpu_percent(interval=5)), 1)
    mem_total = round(float(psutil.virtual_memory()[0] / gb), 1)
    mem_free = round(float(psutil.virtual_memory()[1] / gb), 1)
    mem_used = round(float(psutil.virtual_memory()[3] / gb), 1)
    mem_percent = round(float(mem_used / mem_total * 100), 1)
    gpu_stats = gpustat.GPUStatCollection.new_query()

    gpu_usage = ''
    for gpu in gpu_stats.gpus:
        gpu_usage = f"GPU: {gpu.utilization}% ({gpu.name})"

    return {"cpu_percent": cpu_percent,
            "memory_percent": mem_percent,
            "memory_used": mem_used,
            "gpu_percent": gpu_usage}


# --------------------------------------------------------------------------------
# Server run
# --------------------------------------------------------------------------------

if __name__ == '__main__':
    socketio.run(
        app,
        host=config.get('server.host'),
        port=config.get('server.port'),
        debug=config.get('general.debug'),
        # threaded=config.get('server.threaded'),
        log_output=config.get('server.log_output'),
        use_reloader=config.get('server.use_reloader'),
        allow_unsafe_werkzeug=config.get('general.debug')
    )
