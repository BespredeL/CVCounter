# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 03.12.2025
# Updated: 29.07.2026
# Website: https://bespredel.name

from flask import Blueprint, Response, flash, jsonify, redirect, render_template, request, url_for

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



