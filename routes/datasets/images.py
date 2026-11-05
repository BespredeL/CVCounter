# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

from pathlib import Path

from flask import jsonify, request, send_file

from routes.datasets import datasets_bp
from routes.datasets.common import _json_error, _service
from system.auth import login_required


@datasets_bp.route('/datasets/api/<name>/split', methods=['POST'])
@login_required
def api_split(name: str):
    """
    Split the dataset into train and validation sets.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    data = request.get_json(silent=True) or {}
    ratio = float(data.get('val_ratio') or 0.2)
    try:
        result = _service().auto_split(name, val_ratio=ratio)
    except Exception as exc:
        return _json_error(str(exc))
    return jsonify({'status': 'ok', **result})


@datasets_bp.route('/datasets/api/<name>/images/move', methods=['POST'])
@login_required
def api_move_images(name: str):
    """
    Move images between splits.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    data = request.get_json(silent=True) or {}
    images = data.get('images') or []
    split = data.get('split') or 'train'
    try:
        moved = _service().move_images(name, images, split)
    except Exception as exc:
        return _json_error(str(exc))
    return jsonify({'status': 'ok', 'moved': moved})


@datasets_bp.route('/datasets/api/<name>/images/delete', methods=['POST'])
@login_required
def api_delete_images(name: str):
    """
    Delete images from the dataset.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    data = request.get_json(silent=True) or {}
    images = data.get('images') or []
    removed = _service().delete_images(name, images)
    return jsonify({'status': 'ok', 'removed': removed})


@datasets_bp.route('/datasets/api/<name>/images/<path:image_name>')
@login_required
def api_image_file(name: str, image_name: str):
    """
    Return the image file.
    
    Args:
        name: The dataset name
        image_name: The image name
    
    Returns:
        JSON response
    """
    # Reject path traversal; allow original filenames with underscores/timestamps.
    if '..' in image_name or image_name.startswith('/') or '\\' in image_name:
        return _json_error('Invalid image name', 400)
    try:
        path = _service().image_path(name, Path(image_name).name)
    except FileNotFoundError:
        return _json_error('Not found', 404)
    return send_file(path, mimetype=None, conditional=True, max_age=300)


@datasets_bp.route('/datasets/api/<name>/images')
@login_required
def api_list_images(name: str):
    """
    Return the list of images in the dataset.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    split = request.args.get('split')
    labeled = request.args.get('labeled')
    labeled_bool = None
    if labeled == '1':
        labeled_bool = True
    elif labeled == '0':
        labeled_bool = False
    class_filter = request.args.get('class') or None

    try:
        page = int(request.args.get('page', 0) or 0)
        per_page = int(request.args.get('per_page', 0) or 0)
    except (ValueError, TypeError):
        page, per_page = 0, 0

    svc = _service()
    images = svc.list_images(name, split=split, labeled=labeled_bool, class_filter=class_filter)
    total = len(images)

    if per_page > 0:
        offset = max(0, (page - 1) * per_page) if page > 0 else 0
        paged = images[offset:offset + per_page]
        return jsonify({
            'status': 'ok',
            'images': paged,
            'total': total,
            'page': max(1, page),
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page if per_page else 1,
        })

    return jsonify({'status': 'ok', 'images': images, 'total': total})


@datasets_bp.route('/datasets/api/<name>/annotations/<path:image_name>', methods=['GET', 'POST'])
@login_required
def api_annotation(name: str, image_name: str):
    """
    Return the annotation for an image.
    
    Args:
        name: The dataset name
        image_name: The image name
    
    Returns:
        JSON response
    """
    svc = _service()
    if request.method == 'GET':
        try:
            doc = svc.get_annotation(name, image_name)
        except FileNotFoundError as exc:
            return _json_error(str(exc), 404)
        return jsonify({'status': 'ok', 'annotation': doc})

    data = request.get_json(silent=True) or {}
    try:
        result = svc.save_annotation(name, image_name, data)
    except Exception as exc:
        return _json_error(str(exc))
    return jsonify({'status': 'ok', **result})


@datasets_bp.route('/datasets/api/<name>/annotations/<path:image_name>/copy-prev', methods=['POST'])
@login_required
def api_copy_prev(name: str, image_name: str):
    """
    Copy shapes from the previous image.
    
    Args:
        name: The dataset name
        image_name: The image name
    
    Returns:
        JSON response
    """
    try:
        doc = _service().copy_shapes_from_previous(name, image_name)
    except Exception as exc:
        return _json_error(str(exc))
    return jsonify({'status': 'ok', 'annotation': doc})


@datasets_bp.route('/datasets/api/<name>/tracks/interpolate', methods=['POST'])
@login_required
def api_interpolate(name: str):
    """
    Interpolate tracks between images.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    data = request.get_json(silent=True) or {}
    try:
        filled = _service().interpolate_track(
            name,
            int(data['track_id']),
            data['start_image'],
            data['end_image'],
        )
    except Exception as exc:
        return _json_error(str(exc))
    return jsonify({'status': 'ok', 'filled': filled})
