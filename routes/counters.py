# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 03.12.2025
# Updated: 03.06.2026
# Website: https://bespredel.name

import time
from functools import wraps

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, send_file, url_for
from flask import current_app, g
from markupsafe import escape

from system.core.object_counter import ObjectCounter
from system.managers.video_stream_manager import VideoStreamManager
from system.utils.counter_preview import get_preview_path, save_counter_preview
from system.utils.frame_utils import FrameUtils
from system.utils.utils import is_ajax, slug, trans as translate
from system.utils.validators import (
    ValidationError,
    validate_counting_area_payload,
    validate_reset_count_current_request,
    validate_save_count_request,
)

counters_bp = Blueprint('counters', __name__)


def get_app_context():
    """
    Get application context from g or current_app.
    
    Returns:
        dict: Application context
    """
    if not hasattr(g, 'app_context'):
        g.app_context = current_app.config.get('APP_CONTEXT')
    return g.app_context


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
        context = get_app_context()
        object_counters = context['object_counters']

        location = str(escape(location))
        if location not in object_counters:
            abort(400, translate('Detection config not found'))
        return f(location, *args, **kwargs)

    return decorated_function


def object_detector_init(location: str):
    """
    Initialize an object detector for a specific location.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        dict: Dictionary containing initialized object counters
    
    Note:
        This function is thread-safe and uses a lock for synchronization
    """
    context = get_app_context()
    config = context['config']
    object_counters = context['object_counters']
    db_manager = context['db_manager']
    socketio = context['socketio']
    lock = context['lock']

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


def _require_detection_location(location: str) -> None:
    """
    Abort if location is not configured in detections.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        None
    """
    context = get_app_context()
    if location not in context['locations']:
        abort(400, translate('Detection config not found!'))


def _get_editor_snapshot_frame(location: str):
    """
    Return one BGR frame for the zone editor without loading the YOLO model.

    Reuses an already running counter stream when available.

    Args:
        location (str): The identifier for the detection location

    Returns:
        numpy.ndarray: The frame
    """
    context = get_app_context()
    config = context['config']
    object_counters = context['object_counters']

    if location in object_counters:
        frame = object_counters[location].get_source_frame()
        if frame is not None:
            return frame

    detector_config = config.get(f'detections.{location}', {})
    video_path = detector_config.get('video_path')
    video_fps = detector_config.get('video_fps', config.get('detection_default.video_fps', 0))

    vsm = VideoStreamManager(video_path, video_fps)
    try:
        vsm.start()
        return vsm.get_frame()
    finally:
        vsm.stop()


def _capture_counter_preview_on_start(location: str) -> int | None:
    """
    Grab one frame after thread start and store a dashboard thumbnail.

    Args:
        location: Detection location identifier.

    Returns:
        int | None: Unix timestamp when saved, else None.
    """
    context = get_app_context()
    object_counters = context['object_counters']
    counter = object_counters.get(location)
    frame = None

    if counter:
        for _ in range(40):
            frame = counter.get_source_frame()
            if frame is not None:
                break
            time.sleep(0.1)

    if frame is None:
        try:
            frame = _get_editor_snapshot_frame(location)
        except Exception:
            frame = None

    if save_counter_preview(location, frame):
        return int(time.time())
    return None


def _ensure_counter_running(location: str) -> dict:
    """
    Initialize ObjectCounter and start its thread when not already running.

    Dashboard preview is refreshed only on the first start (new thread).

    Args:
        location: Detection location identifier.

    Returns:
        dict: Keys started_new (bool), preview_ts (int | None).
    """
    context = get_app_context()
    thread_manager = context['thread_manager']
    started_new = not thread_manager.has_thread(location)

    object_counters = object_detector_init(location)
    if location in object_counters:
        thread_manager.start_thread(location, object_counters[location].run_frames)

    preview_ts = None
    if started_new:
        preview_ts = _capture_counter_preview_on_start(location)

    return {'started_new': started_new, 'preview_ts': preview_ts}


def _init_counter_for_location(location: str) -> ObjectCounter:
    """
    Ensure ObjectCounter exists and video source is open.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        ObjectCounter: The ObjectCounter instance
    """
    _require_detection_location(location)
    counters = object_detector_init(location)
    return counters[location]


def _counting_area_i18n() -> dict:
    """
    Strings for the counting-area editor (passed to template as JSON).
    
    Returns:
        dict: Dictionary containing the strings
    """
    return {
        'defaultHint': translate(
            'Click to add points. Drag vertices to adjust. Double-click a vertex to remove.'
        ),
        'rectHint': translate('Drag on the image to draw a rectangle.'),
        'points': translate('Points'),
        'minPoints': translate('need at least 3 points'),
        'minPointsToast': translate('At least 3 points required'),
        'saved': translate('Zone saved'),
    }


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


@counters_bp.route('/counter/<string:location>')
@counters_bp.route('/counter/<string:location>/video')
def counter_video(location: str = None):
    """
    Display the video counter interface for a specific location.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        str: Rendered HTML template with video counter interface
    
    Raises:
        HTTPException: If the location configuration is not found
    """
    context = get_app_context()
    config = context['config']
    locations = context['locations']
    locations_dict = context['locations_dict']
    object_counters = context['object_counters']

    location = str(escape(location))
    if location not in locations:
        abort(400, translate('Detection config not found'))

    _ensure_counter_running(location)

    # Get form config
    form_config = config.get('form', {})

    # Process custom fields
    custom_fields = process_custom_fields(form_config, object_counters[location].get_current_count())

    return render_template(
        'counters/show_video.html',
        title=locations_dict.get(location, ''),
        location=location,
        is_paused=object_counters[location].is_pause(),
        form_config=form_config,
        custom_fields=custom_fields,
        counter_on_sidebar=True
    )


@counters_bp.route('/counter/<string:location>/counting_area')
def counting_area_edit(location: str = None) -> str:
    """
    Visual editor for the counting zone polygon.

    Args:
        location: Detection location identifier.

    Returns:
        str: Rendered editor page.
    """
    context = get_app_context()
    locations_dict = context['locations_dict']

    location = str(escape(location))
    _require_detection_location(location)

    return render_template(
        'counters/counting_area_edit.html',
        title=locations_dict.get(location, location),
        location=location,
        ca_i18n=_counting_area_i18n(),
    )


@counters_bp.route('/counter/<string:location>/counting_area/data')
def counting_area_data(location: str = None):
    """
    Return current counting area configuration as JSON.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        dict: Dictionary containing the counting area configuration
    """
    context = get_app_context()
    config = context['config']

    location = str(escape(location))
    _require_detection_location(location)

    detector_config = config.get(f'detections.{location}', {})
    return jsonify({
        'counting_area': detector_config.get('counting_area', []),
        'counting_area_color': detector_config.get('counting_area_color', [67, 211, 255]),
    })


@counters_bp.route('/counter/<string:location>/preview')
def counter_preview_image(location: str = None) -> Response:
    """
    Serve the persisted dashboard camera thumbnail for a location.

    Preview files are written only when the counter thread is first started.
    """
    location = str(escape(location))
    _require_detection_location(location)

    path = get_preview_path(location)
    if not path.is_file():
        abort(404)

    return send_file(path, mimetype='image/jpeg', conditional=True)


@counters_bp.route('/counter/<string:location>/settings/form')
def counter_settings_form(location: str = None) -> str:
    """
    Return HTML form fields for one detection (dashboard settings modal).

    Args:
        location: Detection location identifier.

    Returns:
        str: Rendered form partial.
    """
    context = get_app_context()
    config = context['config']
    locations_dict = context['locations_dict']

    location = str(escape(location))
    _require_detection_location(location)

    detection = config.get(f'detections.{location}', {})

    return render_template(
        'partials/counter_settings_form.html',
        location=location,
        title=locations_dict.get(location, location),
        detection=detection,
    )


@counters_bp.route('/counter/<string:location>/settings', methods=['POST'])
def counter_settings_save(location: str = None):
    """
    Save detection settings from the dashboard modal.

    Args:
        location: Detection location identifier.

    Returns:
        JSON or redirect with save status.
    """
    context = get_app_context()
    config = context['config']
    object_counters = context['object_counters']

    location = str(escape(location))
    _require_detection_location(location)

    prefix = f'detections-{location}-'
    form_data = {key: value for key, value in request.form.items() if key.startswith(prefix)}

    if not form_data:
        abort(400, translate('No settings to save'))

    config.save_from_request(form_data)

    counter = object_counters.get(location)
    if counter is not None:
        counting_area = config.get(f'detections.{location}.counting_area')
        counting_area_color = config.get(f'detections.{location}.counting_area_color')
        if counting_area is not None:
            if counting_area_color is not None:
                counter.update_counting_area(counting_area, tuple(counting_area_color))
            else:
                counter.update_counting_area(counting_area)

    if is_ajax():
        return jsonify({
            'status': 'saved',
            'restart_recommended': location in object_counters,
        })

    return redirect(url_for('main.index'))


@counters_bp.route('/counter/<string:location>/counting_area/snapshot')
def counting_area_snapshot(location: str = None) -> Response:
    """
    Return a single raw JPEG frame for the zone editor background.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        Response: MIME type response containing the JPEG frame
    """
    location = str(escape(location))
    _require_detection_location(location)

    try:
        frame = _get_editor_snapshot_frame(location)
    except Exception as e:
        from system.utils.logger import Logger
        Logger().error(f'counting_area_snapshot({location}): {e}')
        abort(503, translate('No video frame available. Check camera or video_path.'))

    if frame is None:
        abort(503, translate('No video frame available. Check camera or video_path.'))

    try:
        encoded = FrameUtils.encoding_frame(frame, 90, 'jpeg')
        payload = encoded.tobytes() if hasattr(encoded, 'tobytes') else bytes(encoded)
    except Exception:
        abort(500, translate('Failed to encode video frame'))

    response = Response(payload, mimetype='image/jpeg')
    response.headers['X-Frame-Width'] = str(frame.shape[1])
    response.headers['X-Frame-Height'] = str(frame.shape[0])
    return response


@counters_bp.route('/counter/<string:location>/counting_area', methods=['POST'])
def counting_area_save(location: str = None):
    """Save counting area polygon to config and apply to a running counter.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        dict: Dictionary containing the status, counting area, and counting area color
    """
    context = get_app_context()
    config = context['config']
    object_counters = context['object_counters']

    location = str(escape(location))
    _require_detection_location(location)

    if not request.is_json:
        abort(400, translate('Request must be JSON'))

    try:
        payload = validate_counting_area_payload(request.get_json(silent=True) or {})
    except ValidationError as e:
        abort(400, str(e))

    counting_area = payload['counting_area']
    config.set(f'detections.{location}.counting_area', counting_area)
    if 'counting_area_color' in payload:
        config.set(f'detections.{location}.counting_area_color', payload['counting_area_color'])
    config.save_config()

    if location in object_counters:
        color = payload.get('counting_area_color')
        if color is not None:
            object_counters[location].update_counting_area(counting_area, tuple(color))
        else:
            object_counters[location].update_counting_area(counting_area)

    return jsonify({
        'status': 'saved',
        'counting_area': counting_area,
        'counting_area_color': payload.get(
            'counting_area_color',
            config.get(f'detections.{location}.counting_area_color'),
        ),
    })


@counters_bp.route('/counter_get_frames/<string:location>')
@require_location
def counter_get_frames(location: str = None) -> Response:
    """
    Stream video frames for a specific location.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        Response: MIME type response containing video frames
    """
    context = get_app_context()
    object_counters = context['object_counters']

    return Response(
        object_counters[location].get_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@counters_bp.route('/counter/<string:location>/text')
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
    context = get_app_context()
    config = context['config']
    locations = context['locations']
    locations_dict = context['locations_dict']
    object_counters = context['object_counters']

    location = str(escape(location))
    if location not in locations:
        abort(400, translate('Detection config not found'))

    _ensure_counter_running(location)

    # Get form config
    form_config = config.get('form', {})

    # Process custom fields
    custom_fields = process_custom_fields(form_config, object_counters[location].get_current_count())

    return render_template(
        'counters/show_text.html',
        title=locations_dict.get(location, ''),
        location=location,
        is_paused=object_counters[location].is_pause(),
        form_config=form_config,
        custom_fields=custom_fields,
    )


def _parse_multi_locations_param(raw: str | None) -> list[str]:
    """
    Parse a comma-separated list of detection location ids.

    Args:
        raw: Query string value.

    Returns:
        list[str]: Unique location ids in order.
    """
    if not raw:
        return []

    seen: set[str] = set()
    result: list[str] = []

    for part in raw.split(','):
        loc = str(escape(part.strip()))
        if loc and loc not in seen:
            seen.add(loc)
            result.append(loc)

    return result


def _start_counters_for_locations(locations_list: list[str]) -> None:
    """Initialize ObjectCounter instances and start threads for each location."""
    context = get_app_context()
    object_counters = context['object_counters']
    thread_manager = context['thread_manager']

    for location in locations_list:
        object_detector_init(location)
        if location in object_counters:
            thread_manager.start_thread(location, object_counters[location].run_frames)


@counters_bp.route('/counter_multi/text')
def counter_multi_text() -> str:
    """
    Display a fullscreen text view for one or more detection locations.

    Query:
        locations: Comma-separated detection ids, e.g. ?locations=Cam1,Cam2,Cam3

    Returns:
        str: Rendered multi-counter page.
    """
    context = get_app_context()
    locations = context['locations']
    locations_dict = context['locations_dict']

    locations_list = _parse_multi_locations_param(request.args.get('locations'))

    if not locations_list:
        abort(400, translate('Select at least one counter'))

    for location in locations_list:
        if location not in locations:
            abort(400, translate('Detection config not found'))

    _start_counters_for_locations(locations_list)

    counters = [
        {
            'location': loc,
            'slug': slug(loc),
            'label': locations_dict.get(loc, loc),
        }
        for loc in locations_list
    ]

    title = ' · '.join(c['label'] for c in counters)

    return render_template(
        'counters/show_text_multi.html',
        title=title,
        counters=counters,
    )


@counters_bp.route('/counter_dual/<string:location_first>/<string:location_second>')
@counters_bp.route('/counter_dual/text/<string:location_first>/<string:location_second>')
def counter_dual_text(location_first: str, location_second: str):
    """
    Legacy dual-counter URL — redirects to the multi-counter view.
    """
    location_first = str(escape(location_first))
    location_second = str(escape(location_second))
    locations_param = ','.join([location_first, location_second])

    return redirect(url_for('counters.counter_multi_text', locations=locations_param))


@counters_bp.route('/save_count/<string:location>', methods=['POST'])
@require_location
def save_count(location: str = None) -> dict:
    """
    Save the current count for a specific location.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        dict: Dictionary containing total, defect, and correct counts
    """
    context = get_app_context()
    locations = context['locations']
    object_counters = context['object_counters']

    try:
        # Validate request data
        validated_data = validate_save_count_request(location, locations)

        result = object_counters[location].save_count(
            location=validated_data['location'],
            correct_count=validated_data['correct_count'],
            defect_count=validated_data['defect_count'],
            custom_fields=validated_data['custom_fields'],
            active=1
        )

        return {
            'total_count': result['total'],
            'defect_count': result['defect'],
            'correct_count': result['correct']
        }
    except ValidationError as e:
        abort(400, str(e))
    except KeyError as e:
        abort(400, f"Missing required field: {str(e)}")
    except Exception as e:
        from system.utils.logger import Logger
        Logger().error(f"Error in save_count: {e}")
        abort(500, "Internal server error")


@counters_bp.route('/reset_count/<string:location>')
@require_location
def reset_count(location: str = None) -> dict:
    """
    Reset the counter for a specific location.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        dict: Dictionary with reset counts (all set to 0)
    """
    context = get_app_context()
    object_counters = context['object_counters']

    object_counters[location].reset_count(location=location)
    return {'total_count': 0, 'defect_count': 0, 'correct_count': 0}


@counters_bp.route('/reset_count_current/<string:location>', methods=['POST'])
@require_location
def reset_count_current(location: str = None) -> dict:
    """
    Reset the current count for a specific location.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        dict: Dictionary with current count set to 0
    """
    context = get_app_context()
    locations = context['locations']
    object_counters = context['object_counters']

    try:
        # Validate request data
        validated_data = validate_reset_count_current_request(location, locations)

        object_counters[location].reset_count_current(
            location=validated_data['location'],
            correct_count=validated_data['correct_count'],
            defect_count=validated_data['defect_count']
        )
        return {'current_count': 0}
    except ValidationError as e:
        abort(400, str(e))
    except KeyError as e:
        abort(400, f"Missing required field: {str(e)}")
    except Exception as e:
        from system.utils.logger import Logger
        Logger().error(f"Error in reset_count_current: {e}")
        abort(500, "Internal server error")


@counters_bp.route('/save_capture/<string:location>')
@require_location
def save_capture(location: str = None) -> dict[str, str] | Response:
    """
    Save a capture from the current video frame.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        dict[str, str] | Response: Status response or redirect
    """
    context = get_app_context()
    object_counters = context['object_counters']

    object_counters[location].save_capture()

    if is_ajax():
        return {'status': 'saved'}
    return redirect(url_for('main.index'))


@counters_bp.route('/counter/<string:location>/bootstrap')
def counter_bootstrap(location: str = None):
    """
    Start counter thread in the background without opening the UI.

    Args:
        location: Detection location identifier.

    Returns:
        JSON status response.
    """
    location = str(escape(location))
    _require_detection_location(location)

    result = _ensure_counter_running(location)

    return jsonify({
        'status': 'started',
        'location': location,
        'preview_ts': result['preview_ts'],
    })


@counters_bp.route('/start_count/<string:location>')
@require_location
def start_count(location: str = None) -> dict[str, str] | Response:
    """
    Start the counter for a specific location.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        dict[str, str] | Response: Status response or redirect
    """
    context = get_app_context()
    object_counters = context['object_counters']

    object_counters[location].start()

    if is_ajax():
        return jsonify({'status': 'started'})
    return redirect(url_for('main.index'))


@counters_bp.route('/pause_count/<string:location>')
@require_location
def pause_count(location: str = None) -> dict[str, str] | Response:
    """
    Pause the counter for a specific location.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        dict[str, str] | Response: Status response or redirect
    """
    context = get_app_context()
    object_counters = context['object_counters']

    object_counters[location].pause()

    if is_ajax():
        return jsonify({'status': 'paused'})
    return redirect(url_for('main.index'))


@counters_bp.route('/stop_count/<string:location>')
@require_location
def stop_count(location: str = None) -> dict[str, str] | Response:
    """
    Stop the counter for a specific location.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        dict[str, str] | Response: Status response or redirect
    """
    context = get_app_context()
    object_counters = context['object_counters']
    thread_manager = context['thread_manager']
    lock = context['lock']

    object_counter = object_counters.get(location)
    if object_counter:
        thread_manager.stop_thread(location, object_counter)

    with lock:
        if location in object_counters:
            del object_counters[location]

    if is_ajax():
        return jsonify({'status': 'stopped'})
    return redirect(url_for('main.index'))
