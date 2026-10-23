# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from flask import jsonify, request

from routes.settings import settings_bp
from system.auth import login_required
from system.utils.app_context import get_app_context, refresh_app_context
from system.utils.i18n import trans as translate


@settings_bp.route('/settings/api/keys/create', methods=['POST'])
@login_required
def api_create_key():
    """Create a new REST API key entry."""
    context = get_app_context()
    config = context['config']
    data = request.get_json(silent=True) or request.form.to_dict()
    name = (data.get('name') or '').strip() or 'New API Key'
    role = (data.get('role') or 'read').strip().lower()
    if role not in ('read', 'write', 'admin'):
        role = 'read'

    from system.auth.api_auth import generate_api_key
    new_key_entry = generate_api_key(name=name, role=role)

    keys = config.get('api.keys', [])
    if not isinstance(keys, list):
        keys = []
    keys.append(new_key_entry)
    config.set('api.keys', keys)
    config.save_config()
    refresh_app_context(context)

    return jsonify({
        'ok': True,
        'message': translate('API Key created successfully'),
        'key': new_key_entry
    })


@settings_bp.route('/settings/api/keys/delete', methods=['POST'])
@login_required
def api_delete_key():
    """Revoke and delete a REST API key by its unique ID."""
    context = get_app_context()
    config = context['config']
    data = request.get_json(silent=True) or request.form.to_dict()
    key_id = (data.get('key_id') or '').strip()
    if not key_id:
        return jsonify({'ok': False, 'error': translate('Key ID is required')}), 400

    keys = config.get('api.keys', [])
    if not isinstance(keys, list):
        keys = []
    updated_keys = [k for k in keys if isinstance(k, dict) and k.get('id') != key_id]
    if len(updated_keys) == len(keys):
        return jsonify({'ok': False, 'error': translate('Key not found')}), 404

    config.set('api.keys', updated_keys)
    config.save_config()
    refresh_app_context(context)

    return jsonify({
        'ok': True,
        'message': translate('API Key deleted successfully'),
        'key_id': key_id
    })


@settings_bp.route('/settings/api/toggle', methods=['POST'])
@login_required
def api_toggle():
    """Toggle global REST API enable state."""
    context = get_app_context()
    config = context['config']
    data = request.get_json(silent=True) or request.form.to_dict()
    enabled = bool(data.get('enabled', True))
    config.set('api.enabled', enabled)
    config.save_config()
    refresh_app_context(context)
    return jsonify({
        'ok': True,
        'enabled': enabled,
        'message': translate('REST API status updated')
    })
