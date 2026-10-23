# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import time
from functools import wraps
from typing import Any

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, send_file, \
    stream_with_context, url_for
from markupsafe import escape

from system.auth import login_required
from system.services.counter_runtime import (
    ensure_counter_running,
    get_editor_snapshot_frame,
    live_counter_counts,
    process_custom_fields,
    require_detection_location,
    reset_counts,
    set_pause,
    start_counting,
    start_counters_for_locations,
    stop_counter,
)
from system.utils.app_context import get_app_context
from system.utils.counting_area import areas_for_config, normalize_counting_areas
from system.utils.counter_preview import get_preview_path
from system.utils.frame_utils import FrameUtils
from system.utils.i18n import trans as translate
from system.utils.logger import Logger
from system.utils.telemetry import get_telemetry
from system.utils.utils import is_ajax, slug
from system.utils.validators import (
    ValidationError,
    validate_counting_area_payload,
    validate_pending_counts_request,
    validate_reset_count_current_request,
    validate_save_count_request,
)

counters_bp = Blueprint('counters', __name__)


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
        locations = context['locations']

        location = str(location).strip() if location else ""
        if location not in locations:
            abort(400, translate('Detection config not found'))
        if location not in object_counters:
            abort(400, translate('Counter not running'))
        return f(location, *args, **kwargs)

    return decorated_function


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

    location = str(location).strip()
    if location not in locations:
        abort(400, translate('Detection config not found'))

    ensure_counter_running(location)

    # Get form and detection config
    form_config = config.get('form', {})
    detection_config = config.get(f'detections.{location}') or config.get('detections', {}).get(location, {})

    # Process custom fields (merged global and detection-specific)
    custom_fields = process_custom_fields(
        form_config,
        object_counters[location].get_current_count(),
        detection_config=detection_config
    )

    counter = object_counters[location]
    indicator_mode = getattr(counter, 'indicator_mode', 'circle')

    return render_template(
        'counters/show_video.html',
        title=locations_dict.get(location, ''),
        location=location,
        is_paused=counter.is_pause(),
        indicator_mode=indicator_mode,
        form_config=form_config,
        custom_fields=custom_fields,
        counter_on_sidebar=True,
        initial_counts=live_counter_counts(location),
    )


@counters_bp.route('/counter/<string:location>/counting_area')
@login_required
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

    location = str(location).strip()
    require_detection_location(location)

    return render_template(
        'counters/counting_area_edit.html',
        title=locations_dict.get(location, location),
        location=location,
    )


@counters_bp.route('/counter/<string:location>/counting_area/data')
@login_required
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

    location = str(location).strip()
    require_detection_location(location)

    detector_config = config.get(f'detections.{location}', {})
    areas = normalize_counting_areas(detector_config)
    legacy = areas_for_config(areas)
    return jsonify({
        'counting_areas': legacy['counting_areas'],
        'counting_area': legacy['counting_area'],
        'counting_area_color': legacy['counting_area_color'],
        'counting_area_direction': legacy.get('counting_area_direction', 'any'),
    })


@counters_bp.route('/counter/<string:location>/preview')
def counter_preview_image(location: str = None) -> Response:
    """
    Serve the persisted dashboard camera thumbnail for a location.

    Preview files are written only when the counter thread is first started.
    """
    location = str(location).strip()
    require_detection_location(location)

    path = get_preview_path(location)
    if not path.is_file():
        abort(404)

    return send_file(path, mimetype='image/jpeg', conditional=True)


@counters_bp.route('/counter/<string:location>/settings/form')
@login_required
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

    location = str(location).strip()
    require_detection_location(location)

    detection = config.get(f'detections.{location}', {})

    return render_template(
        'partials/counter_settings_form.html',
        location=location,
        title=locations_dict.get(location, location),
        detection=detection,
    )


@counters_bp.route('/counter/<string:location>/settings', methods=['POST'])
@login_required
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

    location = str(location).strip()
    require_detection_location(location)

    prefix = f'detections-{location}-'
    zone_field_suffixes = ('counting_area', 'counting_area_color', 'counting_areas')
    form_data = {
        key: value
        for key, value in request.form.items()
        if key.startswith(prefix) and not key.endswith(zone_field_suffixes)
    }

    if not form_data:
        abort(400, translate('No settings to save'))

    config.save_from_request(form_data)

    counter = object_counters.get(location)
    if counter is not None:
        detector_config = config.get(f'detections.{location}', {})
        areas = normalize_counting_areas(detector_config)
        if areas:
            counter.update_counting_areas(areas)

    if is_ajax():
        return jsonify({
            'status': 'saved',
            'restart_recommended': location in object_counters,
        })

    return redirect(url_for('main.index'))


@counters_bp.route('/counter/<string:location>/counting_area/snapshot')
@login_required
def counting_area_snapshot(location: str = None) -> Response:
    """
    Return a single raw JPEG frame for the zone editor background.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        Response: MIME type response containing the JPEG frame
    """
    location = str(location).strip()
    require_detection_location(location)

    try:
        frame = get_editor_snapshot_frame(location)
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
@login_required
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

    location = str(location).strip()
    require_detection_location(location)

    if not request.is_json:
        abort(400, translate('Request must be JSON'))

    try:
        payload = validate_counting_area_payload(request.get_json(silent=True) or {})
    except ValidationError as e:
        abort(400, str(e))

    counting_areas = payload['counting_areas']
    legacy = areas_for_config(counting_areas)
    config.set(f'detections.{location}.counting_areas', legacy['counting_areas'])
    config.set(f'detections.{location}.counting_area', legacy['counting_area'])
    config.set(f'detections.{location}.counting_area_color', legacy['counting_area_color'])
    config.set(f'detections.{location}.counting_area_direction', legacy.get('counting_area_direction', 'any'))
    config.save_config()

    if location in object_counters:
        object_counters[location].update_counting_areas(counting_areas)

    return jsonify({
        'status': 'saved',
        'counting_areas': legacy['counting_areas'],
        'counting_area': legacy['counting_area'],
        'counting_area_color': legacy['counting_area_color'],
        'counting_area_direction': legacy.get('counting_area_direction', 'any'),
    })


@counters_bp.route('/counter/<string:location>/indicator_mode', methods=['GET', 'POST'])
@login_required
def toggle_indicator_mode(location: str = None):
    """
    Toggle or update the detection indicator mode (circle vs box) for a counter.

    Args:
        location (str): The identifier for the detection location

    Returns:
        JSON response with current or updated indicator mode.
    """
    context = get_app_context()
    config = context['config']
    object_counters = context['object_counters']

    location = str(location).strip()
    require_detection_location(location)

    counter = object_counters.get(location)
    current_mode = getattr(counter, 'indicator_mode', 'circle') if counter else 'circle'

    if request.method == 'POST':
        req_data = request.get_json(silent=True) or request.form or {}
        new_mode = req_data.get('mode')
        if not new_mode:
            new_mode = 'box' if current_mode == 'circle' else 'circle'
        else:
            new_mode = str(new_mode).strip().lower()
            if new_mode not in ('circle', 'box'):
                new_mode = 'circle'

        if counter:
            counter.set_indicator_mode(new_mode)

        config.set(f'detections.{location}.indicator_mode', new_mode)
        config.save_config()

        message = (
            translate('Indicator mode switched to Bounding box')
            if new_mode == 'box'
            else translate('Indicator mode switched to Dot')
        )
        return jsonify({
            'status': 'success',
            'indicator_mode': new_mode,
            'message': message,
        })

    return jsonify({
        'status': 'success',
        'indicator_mode': current_mode,
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
    counter = object_counters[location]

    @stream_with_context
    def generate():
        yield from counter.get_frames()

    return Response(
        generate(),
        mimetype='multipart/x-mixed-replace; boundary=frame',
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

    location = str(location).strip()
    if location not in locations:
        abort(400, translate('Detection config not found'))

    ensure_counter_running(location)

    # Get form and detection config
    form_config = config.get('form', {})
    detection_config = config.get(f'detections.{location}') or config.get('detections', {}).get(location, {})

    # Process custom fields (merged global and detection-specific)
    custom_fields = process_custom_fields(
        form_config,
        object_counters[location].get_current_count(),
        detection_config=detection_config
    )

    return render_template(
        'counters/show_text.html',
        title=locations_dict.get(location, ''),
        location=location,
        is_paused=object_counters[location].is_pause(),
        form_config=form_config,
        custom_fields=custom_fields,
        initial_counts=live_counter_counts(location),
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
        loc = str(part).strip()
        if loc and loc not in seen:
            seen.add(loc)
            result.append(loc)

    return result


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

    start_counters_for_locations(locations_list)

    counters = [
        {
            'location': loc,
            'slug': slug(loc),
            'label': locations_dict.get(loc, loc),
            'counts': live_counter_counts(loc),
        }
        for loc in locations_list
    ]

    title = ' · '.join(c['label'] for c in counters)

    return render_template(
        'counters/show_text_multi.html',
        title=title,
        counters=counters,
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

        object_counters[location].save_count(
            location=validated_data['location'],
            correct_count=validated_data['correct_count'],
            defect_count=validated_data['defect_count'],
            custom_fields=validated_data['custom_fields'],
            active=1
        )
        get_telemetry().track('report_created', {'location': location})

        return object_counters[location].get_live_counts()
    except ValidationError as e:
        abort(400, str(e))
    except KeyError as e:
        abort(400, f"Missing required field: {str(e)}")
    except Exception as e:
        from system.utils.logger import Logger
        Logger().error(f"Error in save_count: {e}")
        abort(500, "Internal server error")


@counters_bp.route('/update_pending_counts/<string:location>', methods=['POST'])
@require_location
def update_pending_counts(location: str = None) -> dict:
    """
    Update unsaved defect / correct keyboard values for a counter.

    Args:
        location (str): The identifier for the detection location

    Returns:
        dict: Current live counts payload
    """
    context = get_app_context()
    locations = context['locations']
    object_counters = context['object_counters']

    try:
        validated_data = validate_pending_counts_request(location, locations)
        return object_counters[location].set_pending_counts(
            validated_data['defect_count'],
            validated_data['correct_count'],
        )
    except ValidationError as e:
        abort(400, str(e))
    except Exception as e:
        from system.utils.logger import Logger
        Logger().error(f"Error in update_pending_counts: {e}")
        abort(500, "Internal server error")


@counters_bp.route('/reset_count/<string:location>', methods=['GET', 'POST'])
@require_location
def reset_count(location: str = None) -> dict:
    """
    Reset the counter for a specific location.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        dict: Dictionary with reset counts (all set to 0)
    """
    return reset_counts(location)


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
        return object_counters[location].get_live_counts()
    except ValidationError as e:
        abort(400, str(e))
    except KeyError as e:
        abort(400, f"Missing required field: {str(e)}")
    except Exception as e:
        from system.utils.logger import Logger
        Logger().error(f"Error in reset_count_current: {e}")
        abort(500, "Internal server error")


@counters_bp.route('/save_capture/<string:location>', methods=['GET', 'POST'])
def save_capture(location: str = None) -> dict[str, Any] | Response:
    """
    Save a capture from the current video frame (optionally directly to a dataset).
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        dict[str, Any] | Response: Status response with saved path or redirect
    """
    import cv2
    from pathlib import Path
    import re
    from system.utils.paths import get_project_root

    location = str(location).strip() if location else ""
    require_detection_location(location)

    data = (request.get_json(silent=True) or request.values) if request else {}
    target_dataset = (data.get('dataset') or '').strip() or None
    split = (data.get('split') or 'inbox').strip()

    context = get_app_context()
    object_counters = context['object_counters']

    saved_path = None
    if location in object_counters:
        saved_path = object_counters[location].save_capture(target_dataset=target_dataset, split=split)
    else:
        # Fallback to direct snapshot if counter is not running
        frame = get_editor_snapshot_frame(location)
        if frame is not None:
            root = Path(get_project_root())
            if target_dataset:
                dest_dir = root / 'storage' / 'datasets' / target_dataset / 'images' / split
            else:
                dest_dir = root / 'storage' / 'saved_images' / location
            dest_dir.mkdir(parents=True, exist_ok=True)
            clean_loc = re.sub(r'[^A-Za-z0-9-_]+', '', location)
            ts = int(time.time() * 1000)
            target_file = dest_dir / f'{clean_loc}_{ts}.jpg'
            cv2.imwrite(str(target_file), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            saved_path = str(target_file)

    if not saved_path:
        if is_ajax() or request.is_json:
            return jsonify({'status': 'error', 'message': translate('Failed to capture frame')}), 500
        abort(500, translate('Failed to capture frame'))

    if is_ajax() or request.is_json:
        return jsonify({
            'status': 'saved',
            'location': location,
            'dataset': target_dataset,
            'split': split,
            'path': saved_path,
            'filename': Path(saved_path).name,
        })
    return redirect(url_for('main.index'))


@counters_bp.route('/counter/<string:location>/capture/interval', methods=['GET', 'POST'])
def counter_interval_capture(location: str = None):
    """
    Control or check periodic frame capture for a camera.
    """
    location = str(location).strip() if location else ""
    require_detection_location(location)

    context = get_app_context()
    object_counters = context['object_counters']

    if request.method == 'POST':
        data = request.get_json(silent=True) or request.values or {}
        action = (data.get('action') or 'start').strip().lower()

        ensure_counter_running(location)
        counter = object_counters.get(location)
        if not counter:
            return jsonify({'status': 'error', 'message': 'Counter could not be started'}), 500

        if action == 'stop':
            st = counter.stop_interval_capture()
            return jsonify({'status': 'ok', 'action': 'stopped', 'running': False, **st})
        elif action == 'status':
            st = counter.get_interval_capture_status()
            return jsonify({'status': 'ok', 'action': 'status', 'running': bool(st.get('active')), **st})
        else:
            interval_sec = float(data.get('interval') or 2.0)
            max_frames = int(data.get('max_frames') or 30)
            target_dataset = (data.get('dataset') or '').strip() or None
            split = (data.get('split') or 'inbox').strip()
            st = counter.start_interval_capture(
                interval_sec=interval_sec,
                max_frames=max_frames,
                target_dataset=target_dataset,
                split=split,
            )
            return jsonify({'status': 'ok', 'action': 'started', **st})

    # GET request
    counter = object_counters.get(location)
    if not counter:
        return jsonify({
            'status': 'ok',
            'active': False,
            'count': 0,
            'max_frames': 0,
            'interval': 0,
            'dataset': None,
            'split': 'inbox',
        })
    return jsonify({'status': 'ok', **counter.get_interval_capture_status()})


@counters_bp.route('/counter/<string:location>/bootstrap')
def counter_bootstrap(location: str = None):
    """
    Start counter thread in the background without opening the UI.

    Args:
        location: Detection location identifier.

    Returns:
        JSON status response.
    """
    location = str(location).strip()
    require_detection_location(location)

    try:
        result = ensure_counter_running(location)
    except Exception as e:
        Logger().error(f'counter_bootstrap({location}): {e}')
        Logger().log_exception()
        return jsonify({
            'status': 'error',
            'location': location,
            'message': translate('Lost connection to camera!'),
        }), 500

    context = get_app_context()
    object_counters = context.get('object_counters', {})
    counter = object_counters.get(location)
    is_coll = getattr(counter, 'preview_mode', False) if counter else False
    return jsonify({
        'status': 'collection' if is_coll else 'started',
        'location': location,
        'preview_ts': result['preview_ts'],
    })


@counters_bp.route('/start_count/<string:location>', methods=['GET', 'POST'])
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

    start_counting(location)

    if is_ajax():
        is_coll = getattr(object_counters[location], 'preview_mode', False)
        return jsonify({'status': 'collection' if is_coll else 'started'})
    return redirect(url_for('main.index'))


@counters_bp.route('/pause_count/<string:location>', methods=['GET', 'POST'])
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

    set_pause(object_counters[location])

    if is_ajax():
        return jsonify({'status': 'paused'})
    return redirect(url_for('main.index'))


@counters_bp.route('/stop_count/<string:location>', methods=['GET', 'POST'])
@require_location
def stop_count(location: str = None) -> dict[str, str] | Response:
    """
    Stop the counter for a specific location.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        dict[str, str] | Response: Status response or redirect
    """
    stop_counter(location)

    if is_ajax():
        return jsonify({'status': 'stopped'})
    return redirect(url_for('main.index'))
