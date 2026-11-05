# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

from flask import flash, jsonify, redirect, request, send_file, url_for

from routes.datasets import datasets_bp
from routes.datasets.common import _json_error, _service
from system.auth import login_required
from system.detection.metadata import sanitize_classes_list
from system.utils.i18n import trans as translate
from system.utils.utils import is_ajax


@datasets_bp.route('/datasets/api/list')
@login_required
def api_list():
    """
    Return the list of datasets.
    
    Returns:
        JSON response
    """
    return jsonify({'status': 'ok', 'datasets': _service().list_datasets()})


@datasets_bp.route('/datasets/api/create', methods=['POST'])
@login_required
def api_create():
    """
    Create a new dataset.
    
    Returns:
        JSON response
    """
    data = request.get_json(silent=True) or request.form
    name = (data.get('name') or '').strip()
    classes_raw = data.get('classes') or 'object'
    classes = sanitize_classes_list(classes_raw) or ['object']
    task = (data.get('task') or 'detect').strip()
    try:
        summary = _service().create(name, classes=classes, task=task, display_name=data.get('display_name') or name)
    except (ValueError, FileExistsError) as exc:
        return _json_error(str(exc))
    if is_ajax() or request.is_json:
        return jsonify({'status': 'ok', 'dataset': summary})
    flash(translate('Dataset created'))
    return redirect(url_for('datasets.dataset_detail', name=summary['name']))


@datasets_bp.route('/datasets/api/<name>', methods=['DELETE'])
@login_required
def api_delete(name: str):
    """
    Delete a dataset.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    try:
        _service().delete(name)
    except Exception as exc:
        return _json_error(str(exc))
    return jsonify({'status': 'ok'})


@datasets_bp.route('/datasets/api/<name>/meta', methods=['POST'])
@login_required
def api_update_meta(name: str):
    """
    Update the dataset metadata.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    data = request.get_json(silent=True) or {}
    try:
        raw_classes = data.get('classes')
        clean_classes = sanitize_classes_list(raw_classes) if raw_classes is not None else None
        meta = _service().update_meta(
            name,
            classes=clean_classes,
            task=data.get('task'),
            display_name=data.get('display_name'),
            attributes=data.get('attributes'),
            keypoints_schema=data.get('keypoints_schema'),
            autolabel_detector=data.get('autolabel_detector'),
        )
    except (ValueError, FileNotFoundError) as exc:
        return _json_error(str(exc))
    return jsonify({'status': 'ok', 'meta': meta})


@datasets_bp.route('/datasets/api/<name>/summary')
@login_required
def api_summary(name: str):
    """
    Return the dataset summary.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    try:
        return jsonify({'status': 'ok', 'dataset': _service().get_summary(name)})
    except FileNotFoundError as exc:
        return _json_error(str(exc), 404)


@datasets_bp.route('/datasets/api/<name>/adopt', methods=['POST'])
@login_required
def api_adopt(name: str):
    """
    Adopt an existing dataset.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    try:
        result = _service().adopt_existing(name)
    except Exception as exc:
        return _json_error(str(exc))
    return jsonify({'status': 'ok', **result})


@datasets_bp.route('/datasets/api/<name>/qa')
@login_required
def api_qa(name: str):
    """
    Return the QA report for the dataset.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    try:
        report = _service().qa_report(name)
    except Exception as exc:
        return _json_error(str(exc))
    return jsonify({'status': 'ok', 'report': report})


@datasets_bp.route('/datasets/api/<name>/reassign-class', methods=['POST'])
@login_required
def api_reassign_class(name: str):
    """
    Reassign a class to a new class.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    data = request.get_json(silent=True) or {}
    try:
        changed = _service().reassign_class(name, data.get('from'), data.get('to'))
    except Exception as exc:
        return _json_error(str(exc))
    return jsonify({'status': 'ok', 'changed': changed})


@datasets_bp.route('/datasets/api/<name>/merge', methods=['POST'])
@login_required
def api_merge(name: str):
    """
    Merge a dataset into another dataset.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    data = request.get_json(silent=True) or {}
    source = data.get('source')
    try:
        result = _service().merge_into(name, source, split=data.get('split') or 'inbox')
    except Exception as exc:
        return _json_error(str(exc))
    return jsonify({'status': 'ok', **result})


@datasets_bp.route('/datasets/api/<name>/export', methods=['POST'])
@login_required
def api_export(name: str):
    """
    Export the dataset for training.

    Args:
        name: The dataset name

    Returns:
        JSON response
    """
    data = request.get_json(silent=True) or request.form or {}
    dataset_format = (data.get('dataset_format') or data.get('format') or 'yolo').strip().lower()
    try:
        result = _service().export_for_training(name, dataset_format=dataset_format)
    except Exception as exc:
        return _json_error(str(exc))
    return jsonify({'status': 'ok', **result})


@datasets_bp.route('/datasets/api/<name>/export-zip')
@login_required
def api_export_zip(name: str):
    """
    Download complete YOLO dataset as a ZIP archive.
    """
    try:
        zip_path = _service().export_zip(name)
        if not zip_path.is_file():
            return _json_error('Failed to create archive', 500)
        return send_file(
            zip_path,
            as_attachment=True,
            download_name=f'{name}_yolo.zip',
            mimetype='application/zip',
            max_age=0,
        )
    except Exception as exc:
        return _json_error(str(exc), 500)
