# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from flask import Response, flash, jsonify, redirect, request, url_for

from routes.settings import settings_bp
from system.auth import login_required
from system.utils.app_context import get_app_context
from system.utils.i18n import trans as translate
from system.utils.telemetry import get_telemetry


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
