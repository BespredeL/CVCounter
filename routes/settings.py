# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from flask import Blueprint, Response, flash, jsonify, redirect, render_template, request, send_file, url_for

from system.auth import login_required, generate_password_hash
from system.__version__ import APP_VERSION
from system.utils.app_context import get_app_context, refresh_app_context
from system.utils.i18n import trans as translate
from system.utils.telemetry import get_telemetry

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings')
@login_required
def settings() -> str:
    """
    Display the application settings page.
    
    Returns:
        str: Rendered HTML template with settings interface
    
    Note:
        This route requires authentication
    """
    context = get_app_context()
    config = context['config']
    return render_template(
        'settings.html',
        _config=config.read_config(),
        allow_web_control=config.get('server.allow_web_control', True)
    )


@settings_bp.route('/settings_save', methods=['POST'])
@login_required
def settings_save():
    """
    Save application settings.
    
    Returns:
        Response: Redirect to settings page with flash message
    
    Note:
        This route requires authentication
    """
    context = get_app_context()
    config = context['config']

    form_data = request.form.to_dict()
    active_tab = form_data.pop('_active_tab', None)

    # Retrieving users from a form and encrypting passwords
    for key, value in form_data.items():
        if key.startswith('users-'):
            if value == '':
                form_data[key] = config.get('users.' + key.replace('users-', ''))
            else:
                form_data[key] = generate_password_hash(value)

    # Saving updated form data to a configuration file
    config.save_from_request(form_data)
    refresh_app_context(context)

    # Re-apply telemetry settings after save
    get_telemetry().configure(config, runtime_context=context)
    get_telemetry().track('settings_saved')

    flash(translate('Settings saved'))
    if active_tab:
        return redirect(url_for('settings.settings', _anchor=f'pills-{active_tab}'))
    return redirect(url_for('settings.settings'))


@settings_bp.route('/system_info')
@login_required
def system_info() -> str:
    """
    Display system information page.
    
    Returns:
        str: Rendered HTML template with system information
    
    Note:
        This route requires authentication
    """
    from system.utils.utils import get_system_info

    telemetry = get_telemetry()
    sys_info = get_system_info()
    telemetry_status = telemetry.get_queue_status()
    context = get_app_context()
    config = context.get('config') if context else None
    allow_web_control = config.get('server.allow_web_control', True) if config else True
    return render_template(
        'system_info.html',
        sys_info=sys_info,
        app_version=APP_VERSION,
        telemetry_enabled=telemetry.enabled,
        telemetry_last_send=telemetry_status.get('last_send'),
        telemetry_status=telemetry_status,
        allow_web_control=allow_web_control,
    )


@settings_bp.route('/settings/telemetry/send', methods=['POST'])
@login_required
def telemetry_send():
    """
    Queue a manual telemetry diagnostic send.
    
    Returns:
        Redirect to the system info page
    """
    ok, message = get_telemetry().request_manual_send()
    if ok:
        flash(translate('Telemetry send queued'))
    else:
        flash(translate(message) if message else translate('Telemetry send failed'), 'error')
    return redirect(url_for('settings.system_info'))


@settings_bp.route('/settings/telemetry/download')
@login_required
def telemetry_download():
    """
    Download a local diagnostics JSON report.
    
    Returns:
        Response: JSON payload
    """
    payload = get_telemetry().export_json_bytes()
    return Response(
        payload,
        mimetype='application/json',
        headers={
            'Content-Disposition': 'attachment; filename=cvcounter-diagnostics.json',
        },
    )


@settings_bp.route('/settings/feedback', methods=['POST'])
@login_required
def feedback_send():
    """
    Handle user problem report or feedback submission.
    
    Returns:
        Response: Redirect to system info page with flash message
    """
    comment = request.form.get('comment', '').strip()
    email = request.form.get('email', '').strip()
    include_logs = bool(request.form.get('include_logs'))

    if not comment:
        flash(translate('Please enter a description of the problem or feedback.'), 'warning')
        return redirect(url_for('settings.system_info'))

    ok, message = get_telemetry().submit_feedback(
        comment=comment,
        email=email,
        include_logs=include_logs,
    )
    if ok:
        flash(translate('Thank you! Your feedback and diagnostics report have been sent.'), 'success')
    else:
        flash(translate(message) if message else translate('Feedback submission failed'), 'error')
    return redirect(url_for('settings.system_info'))


@settings_bp.route('/settings/system_doctor', methods=['GET'])
@login_required
def system_doctor():
    """
    Run comprehensive health and diagnostic checks and return JSON report.
    
    Returns:
        Response: JSON doctor report
    """
    context = get_app_context()
    report = get_telemetry().run_system_doctor(runtime_context=context)
    return jsonify(report)


@settings_bp.route('/api/telemetry/client-event', methods=['POST'])
def telemetry_client_event():
    """
    Ingest client-side errors and interaction events from browser frontend.
    
    Returns:
        Response: JSON status
    """
    try:
        data = request.get_json(silent=True) or {}
        event_type = data.get('type', 'usage')
        telemetry = get_telemetry()
        if event_type == 'error':
            error_data = data.get('error') or {}
            props = data.get('props') or {}
            telemetry.capture_client_error(
                message=str(error_data.get('message') or 'Client error'),
                url=str(props.get('url') or ''),
                line=int(props.get('line') or 0),
                col=int(props.get('col') or 0),
                stack=str(error_data.get('stack') or ''),
                breadcrumbs=props.get('breadcrumbs'),
            )
        else:
            name = str(data.get('name') or 'client_event')
            props = data.get('props') or {}
            telemetry.track(name, props)
        return jsonify({'ok': True}), 200
    except Exception:
        return jsonify({'ok': False}), 200


@settings_bp.route('/settings/api/model_classes', methods=['POST'])
@login_required
def api_model_classes():
    """
    Extract detection classes from the specified model weights file.

    Returns:
        Response: JSON payload with extracted classes and source
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    weights_path = (data.get('weights_path') or '').strip()

    if not weights_path:
        return jsonify({
            'ok': False,
            'success': False,
            'error': translate('Weights path is required')
        }), 400

    from system.utils.paths import resolve_project_path
    context = get_app_context()
    config = context.get('config') if context else None
    resolved_path = config.resolve_path(weights_path) if config else resolve_project_path(weights_path)
    if not resolved_path:
        resolved_path = weights_path

    from system.object_detection.metadata import extract_model_classes
    classes_dict, source = extract_model_classes(resolved_path)

    if not classes_dict:
        return jsonify({
            'ok': False,
            'success': False,
            'error': translate('Classes not found or model file does not exist')
        }), 404

    # Normalize to string keys for JSON transport
    formatted_classes = {str(k): str(v) for k, v in classes_dict.items()}

    return jsonify({
        'ok': True,
        'success': True,
        'classes': formatted_classes,
        'source': source or 'model',
        'count': len(formatted_classes)
    })


@settings_bp.route('/settings/api/restart', methods=['POST'])
@settings_bp.route('/api/server/restart', methods=['POST'])
@login_required
def api_server_restart():
    """
    Restart the application server process via web control.
    Requires authentication and server.allow_web_control to be enabled.

    Returns:
        Response: JSON status indicating restart was scheduled
    """
    from system.utils.server_control import is_web_control_allowed, schedule_server_restart

    context = get_app_context()
    if not is_web_control_allowed(context):
        return jsonify({
            'ok': False,
            'success': False,
            'error': translate('Server control via web interface is disabled in configuration')
        }), 403

    ok, message = schedule_server_restart(context=context, delay=0.8)
    if not ok:
        return jsonify({
            'ok': False,
            'success': False,
            'error': translate(message)
        }), 400

    return jsonify({
        'ok': True,
        'success': True,
        'message': translate('Server restart initiated. The page will reload shortly.'),
        'delay': 2
    })


@settings_bp.route('/settings/api/shutdown', methods=['POST'])
@settings_bp.route('/api/server/shutdown', methods=['POST'])
@login_required
def api_server_shutdown():
    """
    Shut down the application server process via web control.
    Requires authentication and server.allow_web_control to be enabled.

    Returns:
        Response: JSON status indicating shutdown was scheduled
    """
    from system.utils.server_control import is_web_control_allowed, schedule_server_shutdown

    context = get_app_context()
    if not is_web_control_allowed(context):
        return jsonify({
            'ok': False,
            'success': False,
            'error': translate('Server control via web interface is disabled in configuration')
        }), 403

    ok, message = schedule_server_shutdown(context=context, delay=0.8)
    if not ok:
        return jsonify({
            'ok': False,
            'success': False,
            'error': translate(message)
        }), 400

    return jsonify({
        'ok': True,
        'success': True,
        'message': translate('Server shutdown initiated. The application process will stop.'),
        'delay': 1
    })


# --------------------------------------------------------------------------------
# AI Runtimes & Model Export APIs
# --------------------------------------------------------------------------------

@settings_bp.route('/settings/api/runtimes/status', methods=['GET'])
@login_required
def api_runtimes_status():
    """
    Get current AI runtimes, installed packages, and GPU accelerator status.

    Returns:
        Response: JSON payload with runtime statuses
    """
    from system.utils.runtimes import get_runtime_status, runtime_manager

    status = get_runtime_status()
    install_job = runtime_manager.get_install_status()
    return jsonify({
        'ok': True,
        'runtimes': status,
        'install_job': install_job,
    })


@settings_bp.route('/settings/api/runtimes/install', methods=['POST'])
@login_required
def api_runtimes_install():
    """
    Launch background installation of an AI runtime package bundle.

    Returns:
        Response: JSON payload with job initiation status
    """
    from system.utils.runtimes import runtime_manager

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    bundle = (data.get('bundle') or '').strip()

    if not bundle:
        return jsonify({
            'ok': False,
            'error': translate('Bundle name is required')
        }), 400

    result = runtime_manager.start_install(bundle)
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code


@settings_bp.route('/settings/api/runtimes/install/status', methods=['GET'])
@login_required
def api_runtimes_install_status():
    """
    Get current status and live console logs of the runtime package installer.

    Returns:
        Response: JSON payload with installer status and logs
    """
    from system.utils.runtimes import runtime_manager

    return jsonify({
        'ok': True,
        'job': runtime_manager.get_install_status()
    })


@settings_bp.route('/settings/api/models/list', methods=['GET'])
@login_required
def api_models_list():
    """
    List exportable and available models in the project.

    Returns:
        Response: JSON payload with model files list
    """
    from system.utils.model_exporter import model_export_manager

    models = model_export_manager.list_exportable_models()
    return jsonify({
        'ok': True,
        'models': models,
    })


@settings_bp.route('/settings/api/models/export', methods=['POST'])
@login_required
def api_models_export():
    """
    Start background export of a YOLO model to ONNX or TensorRT Engine.

    Returns:
        Response: JSON payload with export job launch result
    """
    from system.utils.model_exporter import model_export_manager

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    weights_path = (data.get('weights') or data.get('weights_path') or '').strip()
    export_format = (data.get('format') or 'onnx').strip().lower()
    half = bool(data.get('half', False))
    imgsz = int(data.get('imgsz') or 640)
    device = data.get('device') or 'auto'
    dynamic = bool(data.get('dynamic', False))
    workspace = int(data.get('workspace') or 4)

    if not weights_path:
        return jsonify({
            'ok': False,
            'error': translate('Weights path is required')
        }), 400

    result = model_export_manager.start_export(
        weights_path=weights_path,
        export_format=export_format,
        half=half,
        imgsz=imgsz,
        device=device,
        dynamic=dynamic,
        workspace=workspace,
    )
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code


@settings_bp.route('/settings/api/models/export/status', methods=['GET'])
@login_required
def api_models_export_status():
    """
    Get current status and logs of the YOLO model exporter.

    Returns:
        Response: JSON payload with export status, progress logs, and result path
    """
    from system.utils.model_exporter import model_export_manager

    return jsonify({
        'ok': True,
        'export': model_export_manager.get_export_status()
    })


def _resolve_app_log_path() -> str:
    """
    Resolve the absolute path to the main application log file.

    Returns:
        str: Absolute path to the log file.
    """
    import os
    from system.utils.logger import Logger, DEFAULT_LOG_PATH
    from system.utils.paths import resolve_project_path

    log_logger = Logger()
    path = log_logger.log_path or resolve_project_path(DEFAULT_LOG_PATH) or DEFAULT_LOG_PATH
    if not os.path.isabs(path):
        resolved = resolve_project_path(path)
        if resolved:
            path = resolved
    return path


def _format_file_size(size_bytes: int) -> str:
    """
    Format a byte count into a human-readable size string.
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


@settings_bp.route('/settings/api/logs', methods=['GET'])
@login_required
def api_get_logs():
    """
    Retrieve application log entries with optional line limit, level filtering, and search query.

    Query parameters:
        lines: int (default 100, clamped to 10..2000)
        level: str (optional: INFO, WARNING, ERROR, DEBUG)
        q: str (optional substring search filter)

    Returns:
        Response: JSON payload containing log metadata and lines.
    """
    import os
    import datetime

    log_path = _resolve_app_log_path()
    lines_req = request.args.get('lines', 100, type=int)
    lines_limit = max(10, min(lines_req, 2000))
    level_filter = (request.args.get('level') or '').strip().upper()
    search_q = (request.args.get('q') or '').strip().lower()

    if not os.path.isfile(log_path):
        return jsonify({
            'ok': True,
            'path': os.path.basename(log_path),
            'full_path': log_path,
            'exists': False,
            'file_size': 0,
            'file_size_formatted': '0 B',
            'mtime': None,
            'total_lines': 0,
            'filtered_count': 0,
            'lines': []
        })

    try:
        file_size = os.path.getsize(log_path)
        mtime_str = datetime.datetime.fromtimestamp(os.path.getmtime(log_path)).strftime('%Y-%m-%d %H:%M:%S')

        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)

        filtered = all_lines
        if level_filter in ('INFO', 'WARNING', 'ERROR', 'DEBUG'):
            token = f" - {level_filter} - "
            filtered = [line for line in filtered if token in line]

        if search_q:
            filtered = [line for line in filtered if search_q in line.lower()]

        result_lines = [line.rstrip('\r\n') for line in filtered[-lines_limit:]]

        return jsonify({
            'ok': True,
            'path': os.path.basename(log_path),
            'full_path': log_path,
            'exists': True,
            'file_size': file_size,
            'file_size_formatted': _format_file_size(file_size),
            'mtime': mtime_str,
            'total_lines': total_lines,
            'filtered_count': len(filtered),
            'lines': result_lines
        })
    except Exception as exc:
        return jsonify({
            'ok': False,
            'error': str(exc)
        }), 500


@settings_bp.route('/settings/api/logs/download', methods=['GET'])
@login_required
def api_download_logs():
    """
    Download the main server log file as an attachment.
    """
    import os

    log_path = _resolve_app_log_path()
    if not os.path.isfile(log_path):
        return jsonify({'ok': False, 'error': translate('Log file not found')}), 404

    return send_file(
        log_path,
        as_attachment=True,
        download_name=os.path.basename(log_path),
        mimetype='text/plain'
    )


@settings_bp.route('/settings/api/logs/clear', methods=['POST'])
@login_required
def api_clear_logs():
    """
    Clear/truncate the application log file.
    """
    import datetime
    from system.utils.logger import Logger
    from system.utils.paths import ensure_parent_dir

    log_path = _resolve_app_log_path()
    try:
        ensure_parent_dir(log_path)
        with open(log_path, 'w', encoding='utf-8') as f:
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"{now_str} - INFO - Log file cleared by user\n")

        Logger().info("Application log cleared by user")
        return jsonify({
            'ok': True,
            'message': translate('Log file cleared successfully')
        })
    except Exception as exc:
        return jsonify({
            'ok': False,
            'error': str(exc)
        }), 500


@settings_bp.route('/settings/api/detections/add', methods=['POST'])
@login_required
def api_add_detection():
    """
    Add a new camera detection configuration.
    """
    import re
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
    import re

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






