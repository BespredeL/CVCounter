# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for

from routes.datasets import datasets_bp
from routes.datasets.common import (
    _class_id_map,
    _list_available_weights_for_deploy,
    _list_detector_models,
    _resolve_detector_cfg,
    _service,
)
from system.auth import login_required
from system.datasets.dataset_service import VALID_TASKS
from system.managers.training_job_manager import (
    DEFAULT_EPOCHS,
    DEFAULT_IMG_SIZE,
    TrainingProviderUnavailableError,
    training_job_manager,
)
from system.utils.app_context import get_app_context
from system.utils.i18n import trans as translate
from system.utils.telemetry import get_telemetry


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
    get_telemetry().track('datasets_view')
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
    detections = (context.get('config') or {}).get('detections') or {}
    locations = list(detections.keys())
    locations_dict = context.get('locations_dict') or {
        loc: (detections.get(loc, {}) or {}).get('label', loc)
        for loc in locations
    }
    provider_id = training_job_manager.resolve_provider(request.args.get('provider'))
    provider_status = training_job_manager.provider_status(provider_id)
    try:
        model_catalog = training_job_manager.base_model_catalog(provider_id)
        catalog_error = None
        provider_default_model = training_job_manager.default_base_model(provider_id)
    except TrainingProviderUnavailableError as exc:
        model_catalog = {'installed': [], 'available': [], 'official': {}}
        catalog_error = str(exc)
        provider_default_model = ''
    return render_template(
        'datasets/detail.html',
        dataset=summary,
        images=images,
        saved_locations=svc.list_saved_image_locations(),
        recordings=svc.list_recordings(),
        base_models=model_catalog['installed'],
        available_base_models=model_catalog['available'],
        official_base_models=model_catalog['official'],
        training_provider=provider_status,
        training_provider_id=provider_id,
        training_providers=training_job_manager.provider_statuses(),
        training_catalog_error=catalog_error,
        counter_locations=locations,
        counter_cameras=locations_dict,
        detector_models=_list_detector_models(),
        available_weights=_list_available_weights_for_deploy(),
        training_status=training_job_manager.status(),
        default_epochs=DEFAULT_EPOCHS,
        default_imgsz=DEFAULT_IMG_SIZE,
        default_base_model=provider_default_model,
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
