# -*- coding: utf-8 -*-
# ! python3

# Developed by: Alexander Kireev
# Created: 01.11.2023
# Updated: 22.05.2024
# Website: https://bespredel.name

from threading import Thread, Lock
from flask import Flask, Response, abort, redirect, render_template, request, url_for
from flask_socketio import SocketIO
from markupsafe import escape
from system.object_counter import ObjectCounter
from system.config_manager import ConfigManager
from system.db_client import DBClient
from system.translate import trans

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
app.config['SECRET_KEY'] = config.get("socketio_key", False)
socketio = SocketIO(app)


# Context processor
@app.context_processor
def utility_processor():
    return dict(config=config, trans=trans)


# Start DB
db_client = DBClient(
    config.get('db.host'),
    config.get('db.user'),
    config.get('db.password'),
    config.get('db.database'),
    config.get('db.table_name')
)

# Init objects
object_counters = {}
threading_detectors = {}
lock = Lock()


# --------------------------------------------------------------------------------
# Functions
# --------------------------------------------------------------------------------

def object_detector_init(location):
    global object_counters, threading_detectors, config
    with lock:
        if location not in object_counters:
            detector_config = config.get("detections." + location)
            object_counters[location] = ObjectCounter(
                location=location,
                socketio=socketio,
                config=config,
                db_client=db_client,
                video_stream=detector_config['video_path'],
                weights=detector_config['weights_path'],
                counting_area=detector_config['counting_area'],
                counting_area_color=tuple(detector_config['counting_area_color'])
            )
    return object_counters


# --------------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html', object_counters=locations_dict)


@app.route('/settings')
def settings():
    _config = ConfigManager("config.json")
    return render_template('settings.html', config=_config.read_config())


@app.route('/settings_save', methods=['POST'])
def settings_save():
    _config = ConfigManager("config.json")
    _config.save_from_request(request.form)
    return redirect(url_for('settings'))


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
def counter_multi_t(location_first, location_second):
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

    # items = db_client.get_items()

    title = locations_dict.get(location_first, ) + ' - ' + locations_dict.get(location_second, )

    return render_template(
        'counter_text_multi.html',
        title=title,
        location_in=location_first,
        location_out=location_second,
        # items=items,
        is_paused=object_counters[location_first].is_pause() or object_counters[location_second].is_pause(),
        # counter_on_sidebar=False
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
    return {'result': 0}


@app.route('/stop_count/<string:location>')
def stop_count(location=None):
    location = escape(location)
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    object_counters[location].stop()
    return {'result': 0}


@app.route('/pause_count/<string:location>')
def pause_count(location=None):
    location = escape(location)
    if location not in object_counters:
        abort(400, trans('Detection config not found'))

    object_counters[location].pause()
    return {'result': 0}


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
        allow_unsafe_werkzeug=True
    )
