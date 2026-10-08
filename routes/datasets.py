# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 28.07.2026
# Updated: 30.07.2026
# Website: https://bespredel.name

from __future__ import annotations
from pathlib import Path
from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from system.auth import login_required
from system.datasets.annotation_store import AnnotationStore
from system.datasets.dataset_service import DatasetService, VALID_TASKS
from system.managers.training_job_manager import training_job_manager
from system.training.yolo_trainer import DEFAULT_BASE_MODEL, DEFAULT_EPOCHS, DEFAULT_IMG_SIZE, list_base_models
from system.utils.app_context import get_app_context, refresh_app_context
from system.utils.i18n import trans as translate
from system.utils.paths import get_project_root, resolve_project_path
from system.utils.utils import is_ajax

_ultralytics_class = None
_ultralytics_import_error: Exception | None = None


def _get_ultralytics_yolo():
    global _ultralytics_class, _ultralytics_import_error
    if _ultralytics_class is not None:
        return _ultralytics_class
    try:
        from ultralytics import YOLO
        _ultralytics_class = YOLO
        return _ultralytics_class
    except Exception as exc:
        _ultralytics_import_error = exc
        return None


try:
    import cv2

    _cv2_import_error: Exception | None = None
except ImportError as exc:
    cv2 = None
    _cv2_import_error = exc

datasets_bp = Blueprint('datasets', __name__)


def _service() -> DatasetService:
    """
    Get the dataset service instance.
    
    Returns:
        DatasetService: The dataset service instance
    """
    return DatasetService(get_project_root())


def _json_error(message: str, status: int = 400):
    """
    Return a JSON error response.
    
    Args:
        message: The error message
        status: The HTTP status code

    Returns:
        tuple: (JSON response, status code)
    """
    return jsonify({'status': 'error', 'message': message}), status


def _list_detector_models() -> list[dict]:
    """
    Detectors and standalone model files for auto-label model picker.
    
    Returns:
        list: List of detector and model items
    """
    context = get_app_context()
    items = []
    seen_paths = set()

    for location, cfg in (context.get('config').get('detections') or {}).items():
        weights = (cfg or {}).get('weights_path')
        if not weights:
            continue
        resolved = resolve_project_path(weights)
        exists = bool(resolved and Path(resolved).is_file())
        if resolved:
            seen_paths.add(str(Path(resolved).resolve()))
        items.append({
            'location': location,
            'weights_path': weights,
            'label': f'{location} ({Path(str(weights)).name})',
            'exists': exists,
        })

    # Also list standalone model weights in models directories
    try:
        from system.training.yolo_trainer import MODELS_DIR
        model_dirs = [MODELS_DIR, Path(get_project_root()) / 'config' / 'models']
        for mdir in model_dirs:
            if not mdir or not mdir.is_dir():
                continue
            for ext in ('*.onnx', '*.pt', '*.xml', '*.engine', '*.trt'):
                for p in sorted(mdir.glob(ext)):
                    abs_p = str(p.resolve())
                    if abs_p in seen_paths:
                        continue
                    seen_paths.add(abs_p)
                    items.append({
                        'location': f'model:{p.name}',
                        'weights_path': str(p),
                        'label': f'File: {p.name}',
                        'exists': True,
                    })
    except Exception:
        pass

    return items


def _ordered_class_names(classes_map) -> list[str]:
    """
    Normalize dict/list class maps to an ordered name list (names only, dense).
    
    Args:
        classes_map: The class map
    
    Returns:
        list: Ordered list of class names
    """
    if not classes_map:
        return []
    if isinstance(classes_map, list):
        return [str(item).strip() for item in classes_map if str(item).strip()]
    if isinstance(classes_map, dict):
        items: list[tuple[int, str]] = []
        for key, value in classes_map.items():
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue
            name = str(value).strip() if value is not None else ''
            if name:
                items.append((idx, name))
        items.sort(key=lambda pair: pair[0])
        return [name for _, name in items]
    return []


def _class_id_map(classes_map) -> dict[int, str]:
    """
    Build sparse YOLO class-id → name map from config-style dict/list.
    
    Args:
        classes_map: The class map
    
    Returns:
        dict: Sparse YOLO class-id → name map
    """
    if not classes_map:
        return {}
    if isinstance(classes_map, list):
        return {i: str(name).strip() for i, name in enumerate(classes_map) if str(name).strip()}
    if isinstance(classes_map, dict):
        mapping: dict[int, str] = {}
        for key, value in classes_map.items():
            try:
                idx = int(key)
            except (TypeError, ValueError):
                continue
            name = str(value).strip() if value is not None else ''
            if name:
                mapping[idx] = name
        return mapping
    return {}


def _resolve_detector_cfg(detector: str | None = None) -> tuple[dict, str | None]:
    """
    Return (detector config dict, location key). Empty detector → first with weights.
    
    Args:
        detector: The detector key
    
    Returns:
        tuple: (detector config dict, location key)
    """
    context = get_app_context()
    detections = context.get('config').get('detections') or {}

    location = (detector or '').strip()
    if location.startswith('model:'):
        model_name = location[6:]
        from system.training.yolo_trainer import MODELS_DIR
        for mdir in [MODELS_DIR, Path(get_project_root()) / 'config' / 'models']:
            cand = mdir / model_name
            if cand.is_file():
                return {'weights_path': str(cand), 'model_type': 'auto'}, location

    if location and location in detections:
        return detections[location] or {}, location

    for loc, item in detections.items():
        if (item or {}).get('weights_path'):
            return item or {}, loc
    return {}, None


def _detector_class_names(detector: str | None = None) -> tuple[list[str], str | None, str | None]:
    """
    Resolve class names for a detector: config `classes` first, then YOLO `names`.

    Args:
        detector: Detection location key. Empty/None uses the first detector with weights.

    Returns:
        tuple: (class names, source `config`|`weights`, resolved detector location)
    """
    cfg, location = _resolve_detector_cfg(detector)
    if not cfg:
        return [], None, None

    from_config = _ordered_class_names(cfg.get('classes'))
    if from_config:
        return from_config, 'config', location

    weights = cfg.get('weights_path')
    path = resolve_project_path(weights) if weights else None
    if not path or not Path(path).is_file():
        return [], None, location

    try:
        from system.object_detection.metadata import extract_model_classes
        classes_dict, source = extract_model_classes(path)
        if classes_dict:
            return _ordered_class_names(classes_dict), source or 'weights', location
        return [], None, location
    except Exception:
        return [], None, location


def _autolabel_label_for_cls(
        cls_id: int,
        *,
        dataset_classes: list[str],
        detector_map: dict[int, str],
        model_names: dict,
) -> str | None:
    """
    Map a YOLO class id to a dataset label name.

    Uses the detector's sparse id→name map (or model.names). Never indexes a densified
    name list with a sparse YOLO id (that caused off-by-one / wrong-class labels).
    
    Args:
        cls_id: The class id
        dataset_classes: The dataset classes
        detector_map: The detector map
        model_names: The model names
    
    Returns:
        str | None: The label name
    """
    raw = detector_map.get(cls_id)
    if raw is None and model_names:
        raw = model_names.get(cls_id)
        if raw is None:
            raw = model_names.get(str(cls_id))
    if raw is None and not detector_map and dataset_classes and 0 <= cls_id < len(dataset_classes):
        # Custom-trained dense 0..n-1 vocab with no detector filter map.
        raw = dataset_classes[cls_id]
    if raw is None:
        return None

    name = str(raw).strip()
    if not name:
        return None
    if not dataset_classes:
        return name
    if name in dataset_classes:
        return name
    lower_map = {c.lower(): c for c in dataset_classes if isinstance(c, str)}
    matched = lower_map.get(name.lower())
    return matched  # None → class not in dataset vocabulary; skip box


def _resolve_autolabel_weights(
        meta: dict,
        explicit_weights: str | None = None,
        detector: str | None = None,
) -> Path | None:
    """
    Resolve YOLO weights: request override -> dataset setting -> first detector.
    
    Args:
        meta: The dataset metadata
        explicit_weights: The explicit weights path
        detector: The detector key
    
    Returns:
        Path | None: The weights path
    """
    if explicit_weights:
        path = resolve_project_path(explicit_weights)
        return Path(path) if path else None

    context = get_app_context()
    detections = context.get('config').get('detections') or {}
    location = (detector or meta.get('autolabel_detector') or '').strip()
    if location.startswith('model:'):
        model_name = location[6:]
        from system.training.yolo_trainer import MODELS_DIR
        for mdir in [MODELS_DIR, Path(get_project_root()) / 'config' / 'models']:
            cand = mdir / model_name
            if cand.is_file():
                return cand

    if location and location in detections:
        weights = (detections[location] or {}).get('weights_path')
        if weights:
            path = resolve_project_path(weights)
            return Path(path) if path else None

    for cfg in detections.values():
        weights = (cfg or {}).get('weights_path')
        if weights:
            path = resolve_project_path(weights)
            if path:
                return Path(path)
    return None


def _wire_training_emitter() -> None:
    """
    Wire the training progress emitter.
    
    Returns:
        None
    """
    context = get_app_context()
    socketio = context.get('socketio')
    if not socketio:
        return

    def _emit(payload: dict) -> None:
        socketio.emit('training_progress', payload)

    training_job_manager.set_progress_emitter(_emit)


@datasets_bp.route('/datasets')
@login_required
def datasets_index():
    """
    Render the datasets index page.
    
    Returns:
        str: The rendered template
    """
    svc = _service()
    datasets = svc.list_datasets()
    return render_template(
        'datasets/list.html',
        datasets=datasets,
        tasks=VALID_TASKS,
        saved_locations=svc.list_saved_image_locations(),
    )


@datasets_bp.route('/datasets/<name>')
@login_required
def dataset_detail(name: str):
    """
    Render the dataset detail page.
    
    Args:
        name: The dataset name
    
    Returns:
        str: The rendered template
    """
    svc = _service()
    try:
        svc.adopt_existing(name)
        summary = svc.get_summary(name)
    except FileNotFoundError:
        flash(translate('Dataset not found'))
        return redirect(url_for('datasets.datasets_index'))
    images = svc.list_images(name)
    context = get_app_context()
    locations = list((context.get('config').get('detections') or {}).keys())
    return render_template(
        'datasets/detail.html',
        dataset=summary,
        images=images,
        saved_locations=svc.list_saved_image_locations(),
        recordings=svc.list_recordings(),
        base_models=list_base_models(),
        counter_locations=locations,
        detector_models=_list_detector_models(),
        training_status=training_job_manager.status(),
        default_epochs=DEFAULT_EPOCHS,
        default_imgsz=DEFAULT_IMG_SIZE,
        default_base_model=DEFAULT_BASE_MODEL,
    )


@datasets_bp.route('/datasets/<name>/annotate')
@login_required
def dataset_annotate(name: str):
    """
    Render the dataset annotate page.
    
    Args:
        name: The dataset name
    
    Returns:
        str: The rendered template
    """
    svc = _service()
    try:
        summary = svc.get_summary(name)
    except FileNotFoundError:
        flash(translate('Dataset not found'))
        return redirect(url_for('datasets.datasets_index'))
    image = request.args.get('image')
    images = svc.list_images(name)
    if not image and images:
        unlabeled = next((i['name'] for i in images if not i['labeled']), None)
        image = unlabeled or images[0]['name']

    class_id_map: dict[str, str] = {}
    det_cfg, _ = _resolve_detector_cfg(summary.get('autolabel_detector') or None)
    for cls_id, cls_name in _class_id_map((det_cfg or {}).get('classes')).items():
        class_id_map[str(cls_id)] = cls_name

    return render_template(
        'datasets/annotate.html',
        dataset=summary,
        images=images,
        current_image=image,
        class_id_map=class_id_map,
    )


@datasets_bp.route('/datasets/<name>/train')
@login_required
def dataset_train_page(name: str):
    """
    Redirect to the dataset train page.
    
    Args:
        name: The dataset name
    
    Returns:
        str: The redirect URL
    """
    return redirect(url_for('datasets.dataset_detail', name=name) + '#train')


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
    if isinstance(classes_raw, str):
        parsed = [c.strip() for c in classes_raw.replace(';', ',').split(',') if c.strip()]
    else:
        parsed = [str(c).strip() for c in list(classes_raw) if str(c).strip()]
    seen = set()
    classes = [c for c in parsed if not (c in seen or seen.add(c))] or ['object']
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
        meta = _service().update_meta(
            name,
            classes=data.get('classes'),
            task=data.get('task'),
            display_name=data.get('display_name'),
            attributes=data.get('attributes'),
            keypoints_schema=data.get('keypoints_schema'),
            autolabel_detector=data.get('autolabel_detector'),
        )
    except (ValueError, FileNotFoundError) as exc:
        return _json_error(str(exc))
    return jsonify({'status': 'ok', 'meta': meta})


@datasets_bp.route('/datasets/api/detector-classes')
@login_required
def api_detector_classes():
    """
    Return class names for a counter detector (config or YOLO weights).
    
    Returns:
        JSON response
    """
    detector = (request.args.get('detector') or '').strip()
    classes, source, location = _detector_class_names(detector or None)
    if not classes:
        return _json_error(translate('No classes found for this model'), 404)
    return jsonify({
        'status': 'ok',
        'detector': location or detector,
        'classes': classes,
        'source': source,
    })


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
    max_mb = int(context['config'].get('datasets.max_upload_mb', 512) or 512)
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
    return send_file(path, mimetype=None, conditional=True, max_age=0)


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
    try:
        result = _service().export_for_training(name)
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


@datasets_bp.route('/datasets/api/training/status')
@login_required
def api_training_status():
    """
    Return the training status.
    
    Returns:
        JSON response
    """
    _wire_training_emitter()
    return jsonify({'status': 'ok', **training_job_manager.status()})


@datasets_bp.route('/datasets/api/<name>/train', methods=['POST'])
@login_required
def api_train(name: str):
    """
    Train the dataset.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    _wire_training_emitter()
    data = request.get_json(silent=True) or {}
    svc = _service()
    try:
        export_info = svc.export_for_training(name)
    except Exception as exc:
        return _json_error(str(exc))

    try:
        job = training_job_manager.start(
            config_name=name,
            base_model=data.get('base_model') or DEFAULT_BASE_MODEL,
            epochs=int(data.get('epochs') or DEFAULT_EPOCHS),
            imgsz=int(data.get('imgsz') or DEFAULT_IMG_SIZE),
            batch=int(data.get('batch') if data.get('batch') is not None else -1),
            device=data.get('device') or 'auto',
            task=data.get('task') or export_info.get('task') or 'detect',
            export_format=data.get('export_format') or '',
            dedupe_val=bool(data.get('dedupe_val')),
            dataset_name=name,
        )
    except RuntimeError as exc:
        return _json_error(str(exc), 409)
    except Exception as exc:
        return _json_error(str(exc))
    return jsonify({'status': 'ok', 'job': job, 'export': export_info})


@datasets_bp.route('/datasets/api/training/cancel', methods=['POST'])
@login_required
def api_training_cancel():
    """
    Cancel the training job.
    
    Returns:
        JSON response
    """
    ok = training_job_manager.cancel()
    return jsonify({'status': 'ok' if ok else 'idle'})


@datasets_bp.route('/datasets/api/training/runs')
@login_required
def api_training_runs():
    """
    Return the training runs.
    
    Returns:
        JSON response
    """
    task = request.args.get('task') or 'detect'
    return jsonify({'status': 'ok', 'runs': training_job_manager.list_runs(task)})


@datasets_bp.route('/datasets/api/training/apply-weights', methods=['POST'])
@login_required
def api_apply_weights():
    """
    Apply weights to a detector.
    
    Returns:
        JSON response
    """
    data = request.get_json(silent=True) or {}
    location = data.get('location')
    weights = data.get('weights')
    classes = data.get('classes')
    if not location or not weights:
        return _json_error('location and weights required')
    context = get_app_context()
    config = context['config']
    detections = config.get('detections') or {}
    if location not in detections:
        return _json_error(f'Unknown location: {location}', 404)

    root = Path(get_project_root())
    weights_path = Path(weights)
    try:
        rel = str(weights_path.resolve().relative_to(root.resolve())).replace('\\', '/')
    except ValueError:
        rel = str(weights_path).replace('\\', '/')

    from system.object_detection.registry import resolve_model_type
    config.set(f'detections.{location}.weights_path', rel)
    config.set(f'detections.{location}.model_type', resolve_model_type(weights=rel))
    if classes:
        if isinstance(classes, list):
            class_map = {str(i): c for i, c in enumerate(classes)}
        elif isinstance(classes, dict):
            class_map = classes
        else:
            class_map = None
        if class_map is not None:
            config.set(f'detections.{location}.classes', class_map)
    config.save_config()
    refresh_app_context(context)
    return jsonify({
        'status': 'ok',
        'weights_path': rel,
        'restart_recommended': True,
    })


@datasets_bp.route('/datasets/api/<name>/autolabel', methods=['POST'])
@login_required
def api_autolabel(name: str):
    """
    Run YOLO on unlabeled images and write pre-annotations.
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    data = request.get_json(silent=True) or {}
    weights = data.get('weights')
    detector = data.get('detector')
    confidence = float(data.get('confidence') or 0.25)
    limit = int(data.get('limit') or 100)
    only_unlabeled = data.get('only_unlabeled', True)
    image_filter = data.get('images') or data.get('image')
    if isinstance(image_filter, str):
        image_filter = [image_filter]
    elif image_filter is not None:
        image_filter = [str(x) for x in image_filter if x]

    svc = _service()
    meta = svc.load_meta(name)
    dataset_classes = [str(c) for c in (meta.get('classes') or []) if str(c).strip()]

    location = (detector or meta.get('autolabel_detector') or '').strip() or None
    det_cfg, resolved_location = _resolve_detector_cfg(location)
    detector_map = _class_id_map((det_cfg or {}).get('classes'))

    weights_path = _resolve_autolabel_weights(meta, explicit_weights=weights, detector=location)
    if not weights_path or not weights_path.is_file():
        return _json_error(translate('Model weights not found'))

    if cv2 is None:
        return _json_error(str(_cv2_import_error or 'cv2 not available'))

    from system.object_detection import extract_model_classes, load_detector
    predict_classes = sorted(detector_map.keys()) if detector_map else None

    try:
        model = load_detector(
            model_type=(det_cfg or {}).get('model_type', 'auto'),
            weights=str(weights_path),
            confidence=confidence,
            classes_list=predict_classes,
        )
    except Exception as exc:
        return _json_error(f"Failed to load detector: {exc}")

    model_names = model.get_classes()
    if not model_names:
        extracted_names, _ = extract_model_classes(weights_path)
        model_names = extracted_names or {}

    if image_filter:
        wanted = set(image_filter)
        images = [i for i in svc.list_images(name) if i['name'] in wanted]
        if not images:
            model.cleanup()
            return _json_error(translate('No images'))
    else:
        images = svc.list_images(name, labeled=False if only_unlabeled else None)
        images = images[:limit]
    store = svc.store(name)
    labeled_count = 0
    predictions = []

    try:
        for item in images:
            path = svc.image_path(name, item['name'], item['split'])
            img = cv2.imread(str(path))
            if img is None:
                predictions.append({'image': item['name'], 'max_conf': 0.0, 'num_boxes': 0})
                continue
            h, w = img.shape[:2]

            boxes_xyxy, confidences, classes_ids = model.detect(img)
            shapes = []
            max_conf = 0.0
            for idx in range(len(boxes_xyxy)):
                conf = float(confidences[idx])
                max_conf = max(max_conf, conf)
                cls_id = int(classes_ids[idx])
                label = _autolabel_label_for_cls(
                    cls_id,
                    dataset_classes=dataset_classes,
                    detector_map=detector_map,
                    model_names=model_names,
                )
                if not label:
                    continue
                xyxy = boxes_xyxy[idx]
                if w and h:
                    points = [float(xyxy[0]) / w, float(xyxy[1]) / h, float(xyxy[2]) / w, float(xyxy[3]) / h]
                else:
                    continue
                shapes.append({
                    'id': AnnotationStore.new_shape_id(),
                    'type': 'rectangle',
                    'label': label,
                    'points': points,
                    'track_id': None,
                    'attributes': {},
                    'confidence': conf,
                    'prelabeled': True,
                    'class_id': cls_id,
                })
            predictions.append({
                'image': item['name'],
                'max_conf': max_conf,
                'num_boxes': len(shapes),
            })
            if shapes:
                doc = store.load(item['name'])
                doc['width'] = w
                doc['height'] = h
                doc['shapes'] = shapes
                store.save(item['name'], doc)
                labeled_count += 1
    finally:
        model.cleanup()

    ranked = svc.uncertainty_rank(name, predictions)
    return jsonify({
        'status': 'ok',
        'labeled': labeled_count,
        'processed': len(images),
        'uncertainty': ranked[:50],
        'detector': resolved_location,
    })


@datasets_bp.route('/datasets/api/<name>/active-learning', methods=['POST'])
@login_required
def api_active_learning(name: str):
    """
    Run inference on unlabeled set and return uncertainty ranking (no write).
    
    Args:
        name: The dataset name
    
    Returns:
        JSON response
    """
    data = request.get_json(silent=True) or {}
    weights = data.get('weights')
    detector = data.get('detector')
    confidence = float(data.get('confidence') or 0.1)
    svc = _service()
    meta = svc.load_meta(name)
    location = (detector or meta.get('autolabel_detector') or '').strip() or None
    det_cfg, _ = _resolve_detector_cfg(location)
    detector_map = _class_id_map((det_cfg or {}).get('classes'))
    weights_path = _resolve_autolabel_weights(meta, explicit_weights=weights, detector=location)
    if not weights_path or not weights_path.is_file():
        return _json_error(translate('Model weights not found'))

    if cv2 is None:
        return _json_error(str(_cv2_import_error or 'cv2 not available'))

    from system.object_detection import load_detector
    predict_classes = sorted(detector_map.keys()) if detector_map else None

    try:
        model = load_detector(
            model_type=(det_cfg or {}).get('model_type', 'auto'),
            weights=str(weights_path),
            confidence=confidence,
            classes_list=predict_classes,
        )
    except Exception as exc:
        return _json_error(f"Failed to load detector: {exc}")

    predictions = []
    try:
        for item in svc.list_images(name, labeled=False):
            path = svc.image_path(name, item['name'], item['split'])
            img = cv2.imread(str(path))
            if img is None:
                predictions.append({'image': item['name'], 'max_conf': 0.0, 'num_boxes': 0})
                continue
            boxes_xyxy, confidences, _ = model.detect(img)
            num = len(boxes_xyxy)
            max_conf = float(max(confidences)) if num > 0 else 0.0
            predictions.append({'image': item['name'], 'max_conf': max_conf, 'num_boxes': num})
    finally:
        model.cleanup()

    ranked = svc.uncertainty_rank(name, predictions)
    return jsonify({'status': 'ok', 'uncertainty': ranked})
