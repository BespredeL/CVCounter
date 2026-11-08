# -*- coding: utf-8 -*-
# ! python3

import re

from flask import jsonify, request

from routes.settings import settings_bp
from system.auth import is_admin_user, login_required
from system.services.counter_readiness import (
    build_onboarding_readiness,
    validate_counter_readiness,
)
from system.services.onboarding import (
    onboarding_payload,
    scenario_to_default_intent,
    set_onboarding_fields,
    set_onboarding_state,
)
from system.utils.app_context import get_app_context, refresh_app_context
from system.utils.i18n import trans as translate
from system.utils.runtimes import resolve_bundles_for_inference


@settings_bp.route('/setup')
@login_required
def setup_wizard_page():
    from flask import render_template

    from system.auth import auth_enabled, get_authenticated_username

    context = get_app_context()
    available_models = []
    try:
        from system.utils.model_exporter import model_export_manager
        available_models = model_export_manager.list_exportable_models() or []
    except Exception:
        available_models = []

    return render_template(
        'setup/wizard.html',
        onboarding=onboarding_payload(context['config']),
        available_models=available_models,
        is_admin=is_admin_user(),
        auth_enabled=auth_enabled(),
        auth_user=get_authenticated_username(),
        allow_web_control=bool(context['config'].get('server.allow_web_control', True)),
    )


@settings_bp.route('/settings/api/onboarding/state', methods=['GET'])
@login_required
def api_onboarding_state():
    context = get_app_context()
    payload = onboarding_payload(context['config'])
    payload['is_admin'] = is_admin_user()
    return jsonify({'ok': True, **payload})


@settings_bp.route('/settings/api/onboarding/scenario', methods=['POST'])
@login_required
def api_onboarding_scenario():
    context = get_app_context()
    config = context['config']
    data = request.get_json(silent=True) or {}
    scenario = (data.get('scenario_id') or data.get('scenario') or '').strip()
    if not scenario:
        return jsonify({'ok': False, 'error': translate('Scenario is required')}), 400

    block = dict(onboarding_payload(config))
    block['scenario'] = scenario
    config.set('general.onboarding', block)
    config.save_config()

    intent = scenario_to_default_intent(scenario)
    bundles = resolve_bundles_for_inference(inference_intent=intent, model_type=None, weights_path='')
    return jsonify({
        'ok': True,
        'scenario': scenario,
        'inference_intent': intent,
        'bundles_hint': bundles.get('required') or [],
        'bundles': bundles,
    })


@settings_bp.route('/settings/api/onboarding/readiness', methods=['GET'])
@login_required
def api_onboarding_readiness():
    context = get_app_context()
    scenario = (request.args.get('scenario') or '').strip() or None
    location = (request.args.get('location') or '').strip() or None
    report = build_onboarding_readiness(
        context['config'],
        scenario=scenario,
        location=location,
        runtime_context=context,
    )
    report['is_admin'] = is_admin_user()
    return jsonify({'ok': True, **report})


@settings_bp.route('/settings/api/onboarding/draft', methods=['POST'])
@login_required
def api_onboarding_draft():
    """Validate a draft counter configuration without persisting detections."""
    data = request.get_json(silent=True) or {}
    cam_cfg = {
        'video_path': (data.get('video_path') or '').strip(),
        'weights_path': (data.get('weights_path') or '').strip(),
        'model_type': (data.get('model_type') or 'auto').strip(),
        'inference_intent': (data.get('inference_intent') or '').strip(),
    }
    if not cam_cfg['inference_intent']:
        scenario = (data.get('scenario') or data.get('scenario_id') or '').strip()
        if scenario:
            cam_cfg['inference_intent'] = scenario_to_default_intent(scenario)
        else:
            cam_cfg['inference_intent'] = 'collection' if not cam_cfg['weights_path'] else 'inference'
    target_mode = 'collection' if cam_cfg['inference_intent'] in ('collection', 'video_test', 'collect_dataset', 'explore') else 'count'
    readiness = validate_counter_readiness(cam_cfg, target_mode=target_mode, inference_intent=cam_cfg['inference_intent'])
    return jsonify({'ok': True, 'readiness': readiness})


@settings_bp.route('/settings/api/onboarding/fields', methods=['POST'])
@login_required
def api_onboarding_fields():
    """Store the typed wizard values so a post-install restart does not lose the draft."""
    context = get_app_context()
    data = request.get_json(silent=True) or {}
    fields = set_onboarding_fields(context['config'], data)
    return jsonify({'ok': True, 'fields': fields})


def _slug_location(value: str) -> str:
    slug = re.sub(r'[^A-Za-z0-9_-]+', '-', (value or '').strip()).strip('-_')
    return slug[:40]


def _unique_location(detections: dict, preferred: str) -> str:
    base = _slug_location(preferred) or 'camera'
    if base not in detections:
        return base
    index = 2
    while f'{base}-{index}' in detections:
        index += 1
    return f'{base}-{index}'


def _create_counter_from_wizard(config, data: dict) -> dict:
    """Persist a counter when the wizard collected a video source."""
    from system.utils.camera_schema import align_camera_dict

    video_path = (data.get('video_path') or '').strip()
    if not video_path:
        return {'created': False}

    weights_path = (data.get('weights_path') or '').strip()
    label = (data.get('label') or '').strip() or translate('Camera')
    detections = config.get('detections', {}) or {}
    if not isinstance(detections, dict):
        detections = {}
    location = _unique_location(detections, data.get('location') or label)
    new_cam = {
        'label': label,
        'video_path': video_path,
        'inference_intent': 'inference' if weights_path else 'collection',
    }
    if weights_path:
        new_cam['weights_path'] = weights_path
        model_type = (data.get('model_type') or '').strip()
        if not model_type or model_type == 'auto':
            try:
                from system.detection.registry import resolve_architecture
                model_type = resolve_architecture(None, weights_path)
            except Exception:
                model_type = 'auto'
        if model_type:
            new_cam['model_type'] = model_type
    aligned = align_camera_dict(
        new_cam,
        default_template=config.get('detection_default', {}) or {},
        location_id=location,
    )
    config.set(f'detections.{location}', aligned)
    config.save_config()
    return {'created': True, 'location': location, 'label': label}


@settings_bp.route('/settings/api/onboarding/complete', methods=['POST'])
@login_required
def api_onboarding_complete():
    context = get_app_context()
    config = context['config']
    data = request.get_json(silent=True) or {}
    action = (data.get('action') or '').strip().lower()
    if action not in ('complete', 'skip', 'reopen'):
        return jsonify({'ok': False, 'error': translate('Invalid action')}), 400

    created = {'created': False}
    if action == 'reopen':
        set_onboarding_state(config, state='pending', provenance='user')
    elif action == 'skip':
        set_onboarding_state(config, state='skipped', provenance='user')
    else:
        created = _create_counter_from_wizard(config, data)
        set_onboarding_state(config, state='completed', provenance='user')

    refresh_app_context(context)
    return jsonify({'ok': True, 'counter': created, **onboarding_payload(config)})


@settings_bp.route('/settings/api/counters/<string:location>/readiness', methods=['GET'])
@login_required
def api_counter_readiness(location: str):
    context = get_app_context()
    if location not in (context.get('locations') or []):
        return jsonify({'ok': False, 'error': translate('Detection config not found')}), 404
    cam_cfg = (context['config'].get('detections') or {}).get(location) or {}
    mode = (request.args.get('mode') or 'count').strip().lower()
    readiness = validate_counter_readiness(cam_cfg, target_mode=mode)
    readiness['is_admin'] = is_admin_user()
    return jsonify({'ok': True, 'location': location, **readiness})
