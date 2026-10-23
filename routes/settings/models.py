# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from flask import jsonify, request

from routes.settings import settings_bp
from system.auth import login_required
from system.utils.app_context import get_app_context
from system.utils.i18n import trans as translate


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
