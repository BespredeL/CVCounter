# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 03.12.2025
# Updated: 22.01.2026
# Website: https://bespredel.name

from functools import wraps

from flask import Blueprint, Response, abort, redirect, render_template, url_for
from flask import current_app, g
from markupsafe import escape

from system.core.object_counter import ObjectCounter
from system.utils.utils import is_ajax, trans as translate
from system.utils.validators import (ValidationError, validate_reset_count_current_request, validate_save_count_request)

counters_bp = Blueprint('counters', __name__)


def get_app_context():
    """Get application context from g or current_app."""
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
    thread_manager = context['thread_manager']

    location = str(escape(location))
    if location not in locations:
        abort(400, translate('Detection config not found'))

    object_detector_init(location)
    if location in object_counters:
        thread_manager.start_thread(location, object_counters[location].run_frames)

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
    thread_manager = context['thread_manager']

    location = str(escape(location))
    if location not in locations:
        abort(400, translate('Detection config not found'))

    object_detector_init(location)
    if location in object_counters:
        thread_manager.start_thread(location, object_counters[location].run_frames)

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


@counters_bp.route('/counter_dual/<string:location_first>/<string:location_second>')
@counters_bp.route('/counter_dual/text/<string:location_first>/<string:location_second>')
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
    context = get_app_context()
    locations = context['locations']
    locations_dict = context['locations_dict']
    object_counters = context['object_counters']
    thread_manager = context['thread_manager']

    location_first = str(escape(location_first))
    location_second = str(escape(location_second))
    if location_first not in locations or location_second not in locations:
        abort(400, translate('Detection config not found'))

    # Init objects and threads for first location
    object_detector_init(location_first)
    if location_first in object_counters:
        thread_manager.start_thread(location_first, object_counters[location_first].run_frames)

    # Init objects and threads for second location
    object_detector_init(location_second)
    if location_second in object_counters:
        thread_manager.start_thread(location_second, object_counters[location_second].run_frames)

    # Page title
    title = locations_dict.get(location_first, '') + ' - ' + locations_dict.get(location_second, '')

    return render_template(
        'counters/show_text_multi.html',
        title=title,
        location_in=location_first,
        location_out=location_second,
        location_in_label=locations_dict.get(location_first, ''),
        location_out_label=locations_dict.get(location_second, ''),
    )


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
        return {'status': 'started'}
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
        return {'status': 'paused'}
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
        return {'status': 'stopped'}
    return redirect(url_for('main.index'))
