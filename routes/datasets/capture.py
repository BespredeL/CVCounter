# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import re
import time
from pathlib import Path

from flask import jsonify, request

from routes.datasets import datasets_bp
from routes.datasets.common import (
    _cv2_import_error,
    _get_detections_config,
    _json_error,
    _service,
    cv2,
)
from system.auth import login_required
from system.utils.app_context import get_app_context
from system.utils.i18n import trans as translate


@datasets_bp.route('/datasets/api/<name>/import/camera', methods=['POST'])
@login_required
def api_import_camera(name: str):
    """
    Import images from a camera.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    data = request.get_json(silent=True) or request.form
    location = (data.get('location') or '').strip() or None
    split = (data.get('split') or 'inbox').strip()
    try:
        result = _service().import_saved_images(name, location=location, split=split)
    except Exception as exc:
        return _json_error(str(exc))
    if not result.get('imported') and not result.get('skipped'):
        return _json_error(translate('No images found to import'))
    return jsonify({'status': 'ok', **result})


@datasets_bp.route('/datasets/api/cameras')
@login_required
def api_cameras():
    """
    List configured cameras with status and preview information.
    """
    context = get_app_context()
    detections = _get_detections_config(context)
    object_counters = context.get('object_counters') or {}
    thread_manager = context.get('thread_manager')

    cameras = []
    for location, item in detections.items():
        weights = (item or {}).get('weights_path')
        is_running = bool(thread_manager and thread_manager.has_thread(location) and location in object_counters)
        counter = object_counters.get(location)
        is_preview = bool(counter and getattr(counter, 'preview_mode', False))
        cameras.append({
            'location': location,
            'label': (item or {}).get('label') or location,
            'video_path': (item or {}).get('video_path') or '',
            'running': is_running,
            'preview_mode': is_preview,
            'has_weights': bool(weights),
            'weights_path': weights or '',
        })
    return jsonify({'status': 'ok', 'cameras': cameras})


@datasets_bp.route('/datasets/api/<name>/capture-camera', methods=['POST'])
@login_required
def api_capture_camera(name: str):
    """
    Capture a single frame from a camera directly into dataset inbox.
    """
    from system.services.counter_runtime import get_editor_snapshot_frame

    data = request.get_json(silent=True) or request.form or {}
    location = (data.get('location') or '').strip()
    split = (data.get('split') or 'inbox').strip()
    if not location:
        return _json_error(translate('Camera location is required'))

    svc = _service()
    try:
        svc.ensure_layout(name)
    except Exception as exc:
        return _json_error(str(exc))

    context = get_app_context()
    object_counters = context.get('object_counters') or {}

    saved_path = None
    if location in object_counters:
        saved_path = object_counters[location].save_capture(target_dataset=name, split=split)
    else:
        if cv2 is None:
            return _json_error(str(_cv2_import_error or 'cv2 not available'))
        frame = get_editor_snapshot_frame(location)
        if frame is not None:
            dest_dir = svc.root(name) / 'images' / split
            dest_dir.mkdir(parents=True, exist_ok=True)
            clean_loc = re.sub(r'[^A-Za-z0-9-_]+', '', location)
            ts = int(time.time() * 1000)
            target_file = dest_dir / f'{clean_loc}_{ts}.jpg'
            cv2.imwrite(str(target_file), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            saved_path = str(target_file)

    if not saved_path:
        return _json_error(translate('Failed to capture frame from camera'))

    return jsonify({
        'status': 'ok',
        'saved': True,
        'location': location,
        'dataset': name,
        'split': split,
        'filename': Path(saved_path).name,
    })


@datasets_bp.route('/datasets/api/<name>/interval-camera', methods=['POST'])
@login_required
def api_interval_camera(name: str):
    """
    Control periodic interval frame capturing from camera into dataset inbox.
    """
    from system.services.counter_runtime import ensure_counter_running

    data = request.get_json(silent=True) or request.form or {}
    location = (data.get('location') or '').strip()
    action = (data.get('action') or 'start').strip().lower()
    split = (data.get('split') or 'inbox').strip()
    interval_sec = float(data.get('interval') or 2.0)
    max_frames = int(data.get('max_frames') or 30)

    if not location:
        return _json_error(translate('Camera location is required'))

    context = get_app_context()
    object_counters = context.get('object_counters') or {}

    if action == 'status':
        counter = object_counters.get(location)
        if counter:
            st = counter.get_interval_capture_status()
            return jsonify({
                'ok': True,
                'status': 'ok',
                'action': 'status',
                'running': bool(st.get('active')),
                'captured': st.get('count', 0),
                'max_frames': st.get('max_frames', 0),
                **st,
            })
        return jsonify({
            'ok': True,
            'status': 'ok',
            'action': 'status',
            'running': False,
            'captured': 0,
            'max_frames': 0,
            'active': False,
        })

    if action == 'stop':
        counter = object_counters.get(location)
        if counter:
            st = counter.stop_interval_capture()
            return jsonify({
                'ok': True,
                'status': 'ok',
                'action': 'stopped',
                'running': False,
                'captured': st.get('count', 0),
                'max_frames': st.get('max_frames', 0),
                **st,
            })
        return jsonify({
            'ok': True,
            'status': 'ok',
            'action': 'stopped',
            'running': False,
            'active': False,
        })

    # Start action: ensure counter is running
    try:
        ensure_counter_running(location)
    except Exception as exc:
        return _json_error(f"Cannot start camera stream: {exc}")

    counter = object_counters.get(location)
    if not counter:
        return _json_error("Counter could not be started")

    svc = _service()
    svc.ensure_layout(name)

    st = counter.start_interval_capture(
        interval_sec=interval_sec,
        max_frames=max_frames,
        target_dataset=name,
        split=split,
    )
    return jsonify({
        'ok': True,
        'status': 'ok',
        'action': 'started',
        'running': True,
        'captured': st.get('count', 0),
        'max_frames': st.get('max_frames', max_frames),
        **st,
    })


@datasets_bp.route('/datasets/api/<name>/import/upload', methods=['POST'])
@login_required
def api_import_upload(name: str):
    """
    Import images from a file upload.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    split = (request.form.get('split') or 'inbox').strip()
    files = request.files.getlist('files') or request.files.getlist('file')
    if not files:
        return _json_error(translate('No files uploaded'))
    context = get_app_context()
    cfg = context.get('config') if context else None
    if isinstance(cfg, dict):
        max_mb = int(cfg.get('datasets.max_upload_mb') or 512)
    elif hasattr(cfg, 'get'):
        max_mb = int(cfg.get('datasets.max_upload_mb', 512) or 512)
    else:
        max_mb = 512
    total = 0
    for f in files:
        f.stream.seek(0, 2)
        total += f.stream.tell()
        f.stream.seek(0)
    if total > max_mb * 1024 * 1024:
        return _json_error(translate('Upload too large'))
    try:
        result = _service().import_uploads(name, files, split=split)
    except Exception as exc:
        return _json_error(str(exc))
    if not result.get('imported') and not result.get('skipped'):
        return _json_error(translate('No images found to import'))
    return jsonify({'status': 'ok', **result})


@datasets_bp.route('/datasets/api/<name>/import/recording', methods=['POST'])
@login_required
def api_import_recording(name: str):
    """
    Import images from a recording.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    data = request.get_json(silent=True) or {}
    path = (data.get('path') or '').strip()
    clean_path = path.replace('\\', '/')
    if not clean_path or '..' in clean_path or clean_path.startswith('/'):
        return _json_error(translate('Invalid recording path'))
    every_n = int(data.get('every_n') or 10)
    max_frames = int(data.get('max_frames') or 500)
    split = (data.get('split') or 'inbox').strip()
    try:
        result = _service().import_recording_frames(name, clean_path, every_n=every_n, max_frames=max_frames, split=split)
    except Exception as exc:
        return _json_error(str(exc))
    if not result.get('imported') and not result.get('skipped'):
        return _json_error(translate('No images found to import'))
    return jsonify({'status': 'ok', **result})
