# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

import re

from flask import jsonify, request

from routes.settings import settings_bp
from system.auth import login_required
from system.utils.app_context import get_app_context, refresh_app_context
from system.utils.i18n import trans as translate


@settings_bp.route('/settings/api/detections/add', methods=['POST'])
@login_required
def api_add_detection():
    """
    Add a new camera detection configuration.
    """
    from system.utils.camera_schema import align_camera_dict

    context = get_app_context()
    config = context['config']

    data = request.get_json(silent=True) or request.form.to_dict()
    location = (data.get('location') or '').strip()
    label = (data.get('label') or '').strip()
    video_path = (data.get('video_path') or '').strip()
    weights_path = (data.get('weights_path') or '').strip()
    model_type = (data.get('model_type') or '').strip()
    confidence_raw = data.get('confidence')
    video_fps_raw = data.get('video_fps')

    if not location:
        return jsonify({'ok': False, 'error': translate('Camera ID is required')}), 400

    if not re.match(r'^[a-zA-Z0-9_\-]+$', location):
        return jsonify({
            'ok': False,
            'error': translate('Invalid camera ID. Use Latin letters, digits, underscores, or hyphens.')
        }), 400

    detections = config.get('detections', {}) or {}
    if location in detections:
        return jsonify({
            'ok': False,
            'error': translate('Camera with this ID already exists')
        }), 400

    default_template = config.get('detection_default', {}) or {}
    new_cam = {
        'label': label or location,
        'video_path': video_path,
    }
    if weights_path:
        new_cam['weights_path'] = weights_path
    if model_type:
        new_cam['model_type'] = model_type
    if confidence_raw not in (None, ''):
        try:
            new_cam['confidence'] = float(confidence_raw)
        except (ValueError, TypeError):
            pass
    if video_fps_raw not in (None, ''):
        try:
            new_cam['video_fps'] = int(video_fps_raw)
        except (ValueError, TypeError):
            pass

    aligned = align_camera_dict(new_cam, default_template=default_template, location_id=location)
    config.set(f'detections.{location}', aligned)
    config.save_config()
    refresh_app_context(context)

    return jsonify({
        'ok': True,
        'message': translate('Camera added successfully'),
        'location': location
    })


@settings_bp.route('/settings/api/detections/<location>/delete', methods=['POST'])
@login_required
def api_delete_detection(location: str):
    """
    Delete a camera detection configuration and stop its running thread if active.
    """
    context = get_app_context()
    config = context['config']

    detections = config.get('detections', {}) or {}
    if location not in detections:
        return jsonify({'ok': False, 'error': translate('Camera not found')}), 404

    # Stop thread if active
    thread_manager = context.get('thread_manager')
    object_counters = context.get('object_counters', {})
    counter = object_counters.get(location)
    if thread_manager and thread_manager.has_thread(location):
        thread_manager.stop_thread(location, counter)
    if counter and location in object_counters:
        del object_counters[location]

    try:
        config.delete(f'detections.{location}')
        config.save_config()
        refresh_app_context(context)
        return jsonify({
            'ok': True,
            'message': translate('Camera deleted successfully'),
            'location': location
        })
    except Exception as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 500


@settings_bp.route('/settings/api/custom_fields/add', methods=['POST'])
@login_required
def api_add_custom_field():
    """
    Add a new custom field either globally (under form.custom_fields)
    or for a specific camera detection (under detections.<location>.custom_fields).
    """
    context = get_app_context()
    config = context['config']

    data = request.get_json(silent=True) or request.form.to_dict()
    scope = (data.get('scope') or 'global').strip().lower()
    location = (data.get('location') or '').strip()
    name = (data.get('name') or '').strip()
    label = (data.get('label') or '').strip()
    field_type = (data.get('type') or 'text').strip().lower()
    options_raw = data.get('options')
    default_value = data.get('default_value')

    if not name:
        return jsonify({'ok': False, 'error': translate('Field name (ID) is required')}), 400

    if not re.match(r'^[a-zA-Z0-9_]+$', name):
        return jsonify({
            'ok': False,
            'error': translate('Invalid field ID. Use Latin letters, digits, and underscores.')
        }), 400

    valid_types = ['text', 'number', 'textarea', 'date', 'datetime-local', 'select']
    if field_type not in valid_types:
        field_type = 'text'

    if scope == 'detection':
        if not location:
            return jsonify({'ok': False, 'error': translate('Camera ID is required')}), 400
        detections = config.get('detections', {}) or {}
        if location not in detections:
            return jsonify({'ok': False, 'error': translate('Camera not found')}), 404
        existing_fields = config.get(f'detections.{location}.custom_fields', {}) or {}
        target_path = f'detections.{location}.custom_fields.{name}'
    else:
        scope = 'global'
        existing_fields = config.get('form.custom_fields', {}) or {}
        target_path = f'form.custom_fields.{name}'

    if isinstance(existing_fields, dict) and name in existing_fields:
        return jsonify({'ok': False, 'error': translate('Field with this name already exists')}), 400

    field_dict = {
        'name': name,
        'label': label or name,
        'type': field_type,
    }

    if field_type == 'select':
        parsed_options = []
        if isinstance(options_raw, list):
            parsed_options = [str(x).strip() for x in options_raw if str(x).strip()]
        elif isinstance(options_raw, str):
            lines = [x.strip() for x in options_raw.replace('\r\n', '\n').split('\n') if x.strip()]
            if len(lines) == 1 and ',' in lines[0]:
                lines = [x.strip() for x in lines[0].split(',') if x.strip()]
            parsed_options = lines
        field_dict['options'] = parsed_options

    if default_value not in (None, ''):
        field_dict['default_value'] = default_value

    config.set(target_path, field_dict)
    config.save_config()
    refresh_app_context(context)

    return jsonify({
        'ok': True,
        'message': translate('Field added successfully'),
        'field': field_dict,
        'scope': scope,
        'location': location if scope == 'detection' else None
    })


@settings_bp.route('/settings/api/custom_fields/delete', methods=['POST'])
@login_required
def api_delete_custom_field():
    """
    Delete a custom field from global form or from a specific detection.
    """
    context = get_app_context()
    config = context['config']

    data = request.get_json(silent=True) or request.form.to_dict()
    scope = (data.get('scope') or 'global').strip().lower()
    location = (data.get('location') or '').strip()
    name = (data.get('name') or '').strip()

    if not name:
        return jsonify({'ok': False, 'error': translate('Field name (ID) is required')}), 400

    if scope == 'detection':
        if not location:
            return jsonify({'ok': False, 'error': translate('Camera ID is required')}), 400
        detections = config.get('detections', {}) or {}
        if location not in detections:
            return jsonify({'ok': False, 'error': translate('Camera not found')}), 404
        target_path = f'detections.{location}.custom_fields.{name}'
    else:
        scope = 'global'
        target_path = f'form.custom_fields.{name}'

    try:
        config.delete(target_path)
        config.save_config()
        refresh_app_context(context)
        return jsonify({
            'ok': True,
            'message': translate('Field deleted successfully'),
            'name': name,
            'scope': scope,
            'location': location if scope == 'detection' else None
        })
    except (KeyError, Exception) as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 500
