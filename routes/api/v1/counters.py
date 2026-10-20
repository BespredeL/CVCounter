# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import re
from typing import Any, Dict

import cv2
from flask import Response, abort, jsonify, request

from routes.api import api_v1_bp
from routes.counters import (
    _ensure_counter_running,
    _get_editor_snapshot_frame,
    _live_counter_counts,
    _require_detection_location,
)
from system.auth.api_auth import api_key_required
from system.utils.app_context import get_app_context
from system.utils.i18n import trans as translate
from system.utils.telemetry import get_telemetry


def _mask_source_url(url: str | None) -> str:
    """Mask credentials in RTSP or HTTP URLs for safe API output."""
    if not url:
        return ""
    return re.sub(r'://([^:]+):([^@]+)@', r'://\1:••••••••@', str(url))


def _get_counter_status(location: str) -> str:
    """Determine runtime status of counter."""
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


@api_v1_bp.route('/counters', methods=['GET'])
@api_key_required(role='read')
def list_counters():
    """
    List all configured counters with current statuses and live count metrics.
    """
    context = get_app_context()
    config = context['config']
    locations = context['locations']
    locations_dict = context['locations_dict']

    items = []
    for loc in locations:
        det_config = config.get(f'detections.{loc}', {}) or {}
        status = _get_counter_status(loc)
        counts = _live_counter_counts(loc)

        items.append({
            'id': loc,
            'name': locations_dict.get(loc, loc),
            'status': status,
            'video_source': _mask_source_url(det_config.get('video_path')),
            'weights': det_config.get('weights_path', ''),
            'counts': counts,
        })

    return jsonify({
        'success': True,
        'data': items,
    })


@api_v1_bp.route('/counters/<string:location>', methods=['GET'])
@api_key_required(role='read')
def get_counter_detail(location: str):
    """
    Get detailed runtime metrics and configuration for a specific counter.
    """
    location = str(location).strip()
    _require_detection_location(location)

    context = get_app_context()
    config = context['config']
    locations_dict = context['locations_dict']
    object_counters = context['object_counters']

    det_config = config.get(f'detections.{location}', {}) or {}
    status = _get_counter_status(location)
    counts = _live_counter_counts(location)
    counter = object_counters.get(location)

    perf_info = {}
    if counter and hasattr(counter, 'get_performance_stats'):
        perf_info = counter.get_performance_stats()

    return jsonify({
        'success': True,
        'data': {
            'id': location,
            'name': locations_dict.get(location, location),
            'status': status,
            'video_source': _mask_source_url(det_config.get('video_path')),
            'weights': det_config.get('weights_path', ''),
            'counting_areas': det_config.get('counting_areas') or det_config.get('counting_area'),
            'counts': counts,
            'performance': perf_info,
        }
    })


@api_v1_bp.route('/counters/<string:location>/start', methods=['POST'])
@api_key_required(role='write')
def start_counter(location: str):
    """
    Start the counter worker thread and inference loop.
    """
    location = str(location).strip()
    _require_detection_location(location)

    context = get_app_context()
    _ensure_counter_running(location)
    object_counters = context['object_counters']
    counter = object_counters.get(location)

    if not counter:
        return jsonify({
            'success': False,
            'error': {
                'code': 'start_failed',
                'message': 'Failed to initialize object counter',
            }
        }), 500

    counter.start()
    get_telemetry().track('counter_started', {'location': location})

    return jsonify({
        'success': True,
        'data': {
            'id': location,
            'status': _get_counter_status(location),
        }
    })


@api_v1_bp.route('/counters/<string:location>/stop', methods=['POST'])
@api_key_required(role='write')
def stop_counter(location: str):
    """
    Stop the counter worker thread and clean up resources.
    """
    location = str(location).strip()
    _require_detection_location(location)

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

    return jsonify({
        'success': True,
        'data': {
            'id': location,
            'status': 'stopped',
        }
    })


@api_v1_bp.route('/counters/<string:location>/pause', methods=['POST'])
@api_key_required(role='write')
def pause_counter(location: str):
    """
    Pause or resume the counter.
    Payload (optional): {"action": "pause" | "resume"}
    """
    location = str(location).strip()
    _require_detection_location(location)

    context = get_app_context()
    object_counters = context['object_counters']

    if location not in object_counters:
        return jsonify({
            'success': False,
            'error': {
                'code': 'counter_not_running',
                'message': 'Counter is not running. Start it first before pausing.',
            }
        }), 400

    counter = object_counters[location]
    body = request.get_json(silent=True) or {}
    action = (body.get('action') or '').strip().lower()

    if action == 'pause':
        if not counter.is_pause():
            counter.pause()
    elif action == 'resume':
        if counter.is_pause():
            counter.pause()
    else:
        counter.pause()

    return jsonify({
        'success': True,
        'data': {
            'id': location,
            'is_paused': counter.is_pause(),
            'status': _get_counter_status(location),
        }
    })


@api_v1_bp.route('/counters/<string:location>/reset', methods=['POST'])
@api_key_required(role='write')
def reset_counter(location: str):
    """
    Reset counts to 0 for a running counter.
    """
    location = str(location).strip()
    _require_detection_location(location)

    context = get_app_context()
    object_counters = context['object_counters']

    if location not in object_counters:
        return jsonify({
            'success': False,
            'error': {
                'code': 'counter_not_running',
                'message': 'Counter is not running.',
            }
        }), 400

    counter = object_counters[location]
    counter.reset_count(location=location)
    get_telemetry().track('counter_reset', {'location': location})

    return jsonify({
        'success': True,
        'data': {
            'id': location,
            'counts': counter.get_live_counts(),
        }
    })


@api_v1_bp.route('/counters/<string:location>/save', methods=['POST'])
@api_key_required(role='write')
def save_counter_report(location: str):
    """
    Commit current counts to a saved report in the database.
    Payload (optional):
    {
        "correct_count": int,
        "defect_count": int,
        "custom_fields": dict
    }
    """
    location = str(location).strip()
    _require_detection_location(location)

    context = get_app_context()
    object_counters = context['object_counters']

    if location not in object_counters:
        return jsonify({
            'success': False,
            'error': {
                'code': 'counter_not_running',
                'message': 'Counter is not running.',
            }
        }), 400

    counter = object_counters[location]
    body = request.get_json(silent=True) or {}

    defect_count = int(body.get('defect_count') or 0)
    correct_count = int(body.get('correct_count') or 0)
    custom_fields = body.get('custom_fields') or {}

    result = counter.save_count(
        location=location,
        correct_count=correct_count,
        defect_count=defect_count,
        custom_fields=custom_fields,
        active=1,
    )
    get_telemetry().track('report_created', {'location': location})

    return jsonify({
        'success': True,
        'data': {
            'id': location,
            'saved': result,
            'counts': counter.get_live_counts(),
        }
    })


@api_v1_bp.route('/counters/<string:location>/snapshot', methods=['GET'])
@api_key_required(role='read')
def get_counter_snapshot(location: str):
    """
    Get a snapshot frame (JPEG) from the camera or active counter.
    Query params:
        annotated: bool (default false; if true and counter running, returns frame with boxes)
    """
    location = str(location).strip()
    _require_detection_location(location)

    context = get_app_context()
    object_counters = context['object_counters']
    annotated = request.args.get('annotated', '').lower() in ('1', 'true', 'yes')

    frame = None
    if location in object_counters:
        counter = object_counters[location]
        if annotated and counter.frame is not None:
            frame = counter.frame.copy()
        elif counter._cached_source_frame is not None:
            frame = counter._cached_source_frame.copy()
        elif hasattr(counter, 'get_source_frame'):
            frame = counter.get_source_frame()

    if frame is None:
        try:
            frame = _get_editor_snapshot_frame(location)
        except Exception:
            frame = None

    if frame is None:
        return jsonify({
            'success': False,
            'error': {
                'code': 'frame_unavailable',
                'message': 'Unable to capture frame from video source',
            }
        }), 503

    success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        return jsonify({
            'success': False,
            'error': {
                'code': 'encode_failed',
                'message': 'Failed to encode frame as JPEG',
            }
        }), 500

    return Response(buffer.tobytes(), mimetype='image/jpeg')
