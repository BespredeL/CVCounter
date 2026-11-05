# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import threading
from pathlib import Path

from flask import jsonify, request

from routes.datasets import datasets_bp
from routes.datasets.common import (
    _autolabel_label_for_cls,
    _class_id_map,
    _cv2_import_error,
    _detector_class_names,
    _json_error,
    _list_available_weights_for_deploy,
    _resolve_autolabel_weights,
    _resolve_detector_cfg,
    _service,
    _wire_training_emitter,
    cv2,
    invalidate_available_weights_cache,
    invalidate_detector_models_cache,
)
from system.auth import login_required
from system.datasets.annotation_store import AnnotationStore
from system.managers.training_job_manager import (
    DEFAULT_EPOCHS,
    DEFAULT_IMG_SIZE,
    TrainingNotSupportedError,
    TrainingProviderUnavailableError,
    training_job_manager,
)
from system.utils.app_context import get_app_context, refresh_app_context
from system.utils.i18n import trans as translate
from system.utils.paths import get_project_root


@datasets_bp.route('/datasets/api/available-weights')
@login_required
def api_available_weights():
    """
    List available trained runs and detector model weights for deployment.
    """
    return jsonify({'status': 'ok', 'weights': _list_available_weights_for_deploy()})


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


@datasets_bp.route('/datasets/api/models/base')
@login_required
def api_models_base():
    """
    Return all available base models (installed and available to download).
    """
    provider_id = training_job_manager.resolve_provider(request.args.get('provider'))
    try:
        catalog = training_job_manager.base_model_catalog(provider_id)
        default_model = training_job_manager.default_base_model(provider_id)
    except TrainingNotSupportedError as exc:
        return _json_error(str(exc), 400)
    except TrainingProviderUnavailableError as exc:
        return _json_error(str(exc), 503)
    return jsonify({
        'status': 'ok',
        'provider': provider_id,
        'models': catalog['available'],
        'default': default_model,
    })


@datasets_bp.route('/datasets/api/models/base/download', methods=['POST'])
@login_required
def api_models_base_download():
    """
    Download a base model in a background thread with socket updates.
    """
    data = request.get_json(silent=True) or request.form or {}
    model_name = (data.get('model_name') or data.get('model') or '').strip()
    if not model_name:
        return _json_error('Model name is required')

    clean_name = Path(model_name).name
    provider_id = training_job_manager.resolve_provider(data.get('provider'))
    try:
        supported = training_job_manager.supports_base_model(clean_name, provider=provider_id)
    except TrainingNotSupportedError as exc:
        return _json_error(str(exc), 400)
    except TrainingProviderUnavailableError as exc:
        return _json_error(str(exc), 503)
    if not supported:
        return _json_error(f"Provider '{provider_id}' does not offer the model {clean_name}")

    context = get_app_context()
    socketio = context.get('socketio') if context else None

    def _emitter(payload: dict) -> None:
        if socketio:
            socketio.emit('base_model_download', payload)

    def _worker():
        try:
            training_job_manager.download_base_model(
                clean_name, progress_callback=_emitter, provider=provider_id
            )
            invalidate_available_weights_cache()
            invalidate_detector_models_cache()
        except Exception as exc:
            _emitter({
                'status': 'error',
                'model': clean_name,
                'model_name': clean_name,
                'message': str(exc),
            })

    th = threading.Thread(target=_worker, daemon=True, name=f'BaseModelDownload-{clean_name}')
    th.start()

    return jsonify({
        'status': 'ok',
        'message': f'Download started for {clean_name}',
        'model': clean_name,
        'model_name': clean_name,
        'provider': provider_id,
    })


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
    provider_id = training_job_manager.resolve_provider(data.get('provider'))
    try:
        training_job_manager.ensure_provider_available(provider_id)
    except TrainingNotSupportedError as exc:
        return _json_error(str(exc), 400)
    except TrainingProviderUnavailableError as exc:
        return _json_error(str(exc), 503)

    try:
        export_info = svc.export_for_training(
            name, dataset_format=training_job_manager.dataset_format(provider_id)
        )
    except Exception as exc:
        return _json_error(str(exc))

    try:
        from system.utils.telemetry import get_telemetry
        get_telemetry().track('training_started', {'dataset': name, 'provider': provider_id})
        job = training_job_manager.start(
            config_name=name,
            provider=provider_id,
            base_model=data.get('base_model') or '',
            epochs=int(data.get('epochs') or DEFAULT_EPOCHS),
            imgsz=int(data.get('imgsz') or DEFAULT_IMG_SIZE),
            batch=int(data.get('batch') if data.get('batch') is not None else -1),
            device=data.get('device') or 'auto',
            task=data.get('task') or export_info.get('task') or 'detect',
            export_format=data.get('export_format') or '',
            dedupe_val=bool(data.get('dedupe_val')),
            dataset_name=name,
            dataset_export=export_info,
        )
    except TrainingNotSupportedError as exc:
        return _json_error(str(exc), 400)
    except TrainingProviderUnavailableError as exc:
        return _json_error(str(exc), 503)
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
    provider_id = training_job_manager.resolve_provider(request.args.get('provider'))
    return jsonify({
        'status': 'ok',
        'provider': provider_id,
        'runs': training_job_manager.list_runs(task, provider_id),
    })


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
    config = context.get('config') if context else None
    if not config:
        return _json_error('Configuration not available', 500)
    detections = config.get('detections') or {}
    if location not in detections:
        return _json_error(f'Unknown location: {location}', 404)

    root = Path(get_project_root())
    weights_path = Path(weights)
    if not weights_path.is_absolute():
        weights_path = (root / weights_path).resolve()
    else:
        weights_path = weights_path.resolve()
    try:
        rel = str(weights_path.relative_to(root.resolve())).replace('\\', '/')
    except ValueError:
        rel = str(weights_path).replace('\\', '/')

    from system.detection.registry import resolve_architecture
    config.set(f'detections.{location}.weights_path', rel)
    config.set(f'detections.{location}.model_type', resolve_architecture(weights=rel))
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
    invalidate_available_weights_cache()
    invalidate_detector_models_cache()
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
    dataset_classes_lower = {c.lower(): c for c in dataset_classes}

    location = (detector or meta.get('autolabel_detector') or '').strip() or None
    det_cfg, resolved_location = _resolve_detector_cfg(location)
    detector_map = _class_id_map((det_cfg or {}).get('classes'))

    weights_path = _resolve_autolabel_weights(meta, explicit_weights=weights, detector=location)
    if not weights_path or not weights_path.is_file():
        return _json_error(translate('Model weights not found'))

    if cv2 is None:
        return _json_error(str(_cv2_import_error or 'cv2 not available'))

    from system.detection import extract_model_classes, load_detector
    predict_classes = sorted(detector_map.keys()) if detector_map else None

    try:
        model = load_detector(
            architecture=(det_cfg or {}).get('model_type', 'auto'),
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

            res = model.detect(img)
            shapes = []
            max_conf = 0.0
            for det in res.detections:
                conf = float(det.confidence)
                max_conf = max(max_conf, conf)
                cls_id = int(det.class_id)
                label = _autolabel_label_for_cls(
                    cls_id,
                    dataset_classes=dataset_classes,
                    detector_map=detector_map,
                    model_names=model_names,
                    dataset_classes_lower=dataset_classes_lower,
                )
                if not label:
                    continue
                if w and h:
                    points = [float(det.x1) / w, float(det.y1) / h, float(det.x2) / w, float(det.y2) / h]
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
    limit = int(data.get('limit') or 200)
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

    from system.detection import load_detector
    predict_classes = sorted(detector_map.keys()) if detector_map else None

    try:
        model = load_detector(
            architecture=(det_cfg or {}).get('model_type', 'auto'),
            weights=str(weights_path),
            confidence=confidence,
            classes_list=predict_classes,
        )
    except Exception as exc:
        return _json_error(f"Failed to load detector: {exc}")

    predictions = []
    try:
        unlabeled = svc.list_images(name, labeled=False)
        if limit > 0:
            unlabeled = unlabeled[:limit]
        for item in unlabeled:
            path = svc.image_path(name, item['name'], item['split'])
            img = cv2.imread(str(path))
            if img is None:
                predictions.append({'image': item['name'], 'max_conf': 0.0, 'num_boxes': 0})
                continue
            res = model.detect(img)
            num = len(res)
            max_conf = max((float(d.confidence) for d in res.detections), default=0.0)
            predictions.append({'image': item['name'], 'max_conf': max_conf, 'num_boxes': num})
    finally:
        model.cleanup()

    ranked = svc.uncertainty_rank(name, predictions)
    return jsonify({'status': 'ok', 'uncertainty': ranked})
