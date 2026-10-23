# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Runtime lifecycle of object counters, shared by web routes and the API."""

from __future__ import annotations

import time
from threading import Thread

from flask import abort, current_app

from system.core.object_counter import ObjectCounter
from system.managers.video_stream_manager import VideoStreamManager
from system.utils.app_context import get_app_context
from system.utils.counting_area import DEFAULT_COUNTING_AREA_COLOR
from system.utils.counter_preview import save_counter_preview
from system.utils.i18n import trans as translate
from system.utils.logger import Logger
from system.utils.telemetry import get_telemetry


def require_detection_location(location: str) -> None:
    """
    Abort if location is not configured in detections.

    Args:
        location (str): The identifier for the detection location

    Returns:
        None
    """
    context = get_app_context()
    if location not in context['locations']:
        abort(400, translate('Detection config not found'))


def init_object_detector(location: str):
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

    if location in object_counters:
        return object_counters

    detector_config = config.get("detections." + location)
    counter = None
    try:
        counter = ObjectCounter(
            location=location,
            config_manager=config,
            socketio=socketio,
            video_path=detector_config['video_path'],
            db_manager=db_manager,
            weights=detector_config.get('weights_path'),
            counting_areas=detector_config.get('counting_areas'),
            counting_area=detector_config.get('counting_area'),
            counting_area_color=tuple(
                detector_config.get('counting_area_color', DEFAULT_COUNTING_AREA_COLOR)
            ),
        )
    except Exception:
        if counter is not None:
            counter.cleanup()
        raise

    with lock:
        if location not in object_counters:
            object_counters[location] = counter
        else:
            counter.cleanup()

    return object_counters


def get_editor_snapshot_frame(location: str):
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
    detection_default = config.get('detection_default', {})
    video_path = detector_config.get('video_path')
    video_fps = detector_config.get('video_fps', detection_default.get('video_fps', 0))
    max_reconnect_attempts = detector_config.get(
        'video_reconnect_attempts',
        detection_default.get('video_reconnect_attempts', VideoStreamManager.DEFAULT_MAX_RECONNECT_ATTEMPTS),
    )

    vsm = VideoStreamManager(video_path, video_fps, max_reconnect_attempts=max_reconnect_attempts)
    try:
        if not vsm.connect_with_retries():
            return None
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
            cached = counter._cached_source_frame
            if cached is not None:
                frame = cached.copy()
                break
            time.sleep(0.1)

    if frame is None:
        try:
            frame = get_editor_snapshot_frame(location)
        except Exception:
            frame = None

    if save_counter_preview(location, frame):
        return int(time.time())
    return None


def _schedule_counter_preview_capture(location: str) -> None:
    """Capture dashboard preview in the background (must not block HTTP)."""
    app = current_app._get_current_object()

    def _worker() -> None:
        try:
            with app.app_context():
                _capture_counter_preview_on_start(location)
        except Exception as e:
            Logger().error(f'Preview capture failed for {location}: {e}')
            Logger().log_exception()

    Thread(
        target=_worker,
        daemon=True,
        name=f'PreviewCapture-{location}',
    ).start()


def ensure_counter_running(location: str) -> dict:
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

    object_counters = init_object_detector(location)
    if location in object_counters:
        thread_manager.start_thread(location, object_counters[location].run_frames)

    preview_ts = None
    if started_new:
        _schedule_counter_preview_capture(location)

    return {'started_new': started_new, 'preview_ts': preview_ts}


def init_counter_for_location(location: str) -> ObjectCounter:
    """
    Ensure ObjectCounter exists and video source is open.

    Args:
        location (str): The identifier for the detection location

    Returns:
        ObjectCounter: The ObjectCounter instance
    """
    require_detection_location(location)
    counters = init_object_detector(location)
    return counters[location]


def process_custom_fields(form_config: dict, current_count: dict, detection_config: dict = None) -> list:
    """
    Process custom fields for a specific location, combining global fields
    from form_config with detection-specific fields.

    Args:
        form_config (dict): The global form configuration
        current_count (dict): The current count data
        detection_config (dict, optional): The detection configuration for this specific camera

    Returns:
        list: List of processed custom fields
    """
    merged_fields: dict[str, dict] = {}

    for field in (form_config.get('custom_fields') or {}).values():
        if isinstance(field, dict) and field.get('name'):
            field_copy = field.copy()
            field_copy['is_global'] = True
            merged_fields[field['name']] = field_copy

    if detection_config and isinstance(detection_config.get('custom_fields'), dict):
        for field in detection_config['custom_fields'].values():
            if isinstance(field, dict) and field.get('name'):
                field_copy = field.copy()
                field_copy['is_detection_specific'] = True
                merged_fields[field['name']] = field_copy

    result = []
    current_values = current_count.get('custom_fields', {}) if (current_count and isinstance(current_count.get('custom_fields'), dict)) else {}

    for field in merged_fields.values():
        field_name = field['name']
        if field_name in current_values:
            field['value'] = current_values[field_name]
        else:
            field['value'] = field.get('default_value', form_config.get('default_value', ""))
        result.append(field)

    return result


def live_counter_counts(location: str) -> dict:
    """
    Counts for the counter UI: running in-memory state, else last DB record.

    Args:
        location: Detection location identifier.

    Returns:
        dict: Keys total, current, defect, correct, by_class.
    """
    context = get_app_context()
    counter = context['object_counters'].get(location)
    if counter is not None:
        return counter.get_live_counts()

    zeros = {
        'total': 0,
        'current': 0,
        'defect': 0,
        'correct': 0,
        'pending_defect': 0,
        'pending_correct': 0,
        'by_class': [],
    }
    row = context['db_manager'].get_current_count(location)
    if row is None:
        return zeros

    def _as_int(value, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    return {
        'total': _as_int(row.total_count),
        'current': 0,
        'defect': _as_int(row.defects_count),
        'correct': _as_int(row.correct_count),
        'pending_defect': 0,
        'pending_correct': 0,
        'by_class': [],
    }


def start_counters_for_locations(locations_list: list[str]) -> None:
    """Initialize ObjectCounter instances and start threads for each location."""
    context = get_app_context()
    object_counters = context['object_counters']
    thread_manager = context['thread_manager']

    for location in locations_list:
        init_object_detector(location)
        if location in object_counters:
            thread_manager.start_thread(location, object_counters[location].run_frames)


def counter_status(location: str) -> str:
    """
    Runtime status of a counter: stopped, collection, paused, or running.

    Args:
        location: Detection location identifier.

    Returns:
        str: Status name.
    """
    context = get_app_context()
    thread_manager = context['thread_manager']
    object_counters = context['object_counters']

    if location not in thread_manager.threads or location not in object_counters:
        return 'stopped'
    counter = object_counters[location]
    if getattr(counter, 'preview_mode', False):
        return 'collection'
    if counter.is_pause():
        return 'paused'
    return 'running'


def start_counting(location: str) -> None:
    """Resume inference on an already initialized counter and record telemetry."""
    context = get_app_context()
    context['object_counters'][location].start()
    get_telemetry().track('counter_started', {'location': location})


def set_pause(counter, action: str | None = None) -> bool:
    """
    Pause, resume, or toggle a running counter.

    An empty action toggles the current pause state, matching the web control.

    Args:
        counter: Running ObjectCounter.
        action: ``pause``, ``resume``, or empty to toggle.

    Returns:
        bool: Whether the counter is paused after the call.
    """
    action = (action or '').strip().lower()
    if action == 'pause':
        if not counter.is_pause():
            counter.pause()
    elif action == 'resume':
        if counter.is_pause():
            counter.pause()
    else:
        counter.pause()
    return counter.is_pause()


def reset_counts(location: str) -> dict:
    """Reset in-memory counts for a running counter and return the live payload."""
    context = get_app_context()
    counter = context['object_counters'][location]
    counter.reset_count(location=location)
    get_telemetry().track('counter_reset', {'location': location})
    return counter.get_live_counts()


def stop_counter(location: str) -> None:
    """Stop the worker thread, drop the counter, and record telemetry."""
    context = get_app_context()
    object_counters = context['object_counters']
    thread_manager = context['thread_manager']
    lock = context['lock']

    counter = object_counters.get(location)
    if counter:
        thread_manager.stop_thread(location, counter)

    with lock:
        if location in object_counters:
            del object_counters[location]

    get_telemetry().track('counter_stopped', {'location': location})
