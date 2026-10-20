# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

from flask import Blueprint, jsonify

api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')


@api_v1_bp.errorhandler(400)
def api_bad_request(error):
    msg = error.description if hasattr(error, 'description') else str(error)
    return jsonify({
        'success': False,
        'error': {
            'code': 'bad_request',
            'message': msg,
        }
    }), 400


@api_v1_bp.errorhandler(401)
def api_unauthorized(error):
    msg = error.description if hasattr(error, 'description') else "Unauthorized"
    return jsonify({
        'success': False,
        'error': {
            'code': 'unauthorized',
            'message': msg,
        }
    }), 401


@api_v1_bp.errorhandler(403)
def api_forbidden(error):
    msg = error.description if hasattr(error, 'description') else "Forbidden"
    return jsonify({
        'success': False,
        'error': {
            'code': 'forbidden',
            'message': msg,
        }
    }), 403


@api_v1_bp.errorhandler(404)
def api_not_found(error):
    msg = error.description if hasattr(error, 'description') else "Resource not found"
    return jsonify({
        'success': False,
        'error': {
            'code': 'not_found',
            'message': msg,
        }
    }), 404


@api_v1_bp.errorhandler(500)
def api_internal_error(error):
    msg = str(error) if hasattr(error, 'description') else "Internal server error"
    return jsonify({
        'success': False,
        'error': {
            'code': 'internal_server_error',
            'message': msg,
        }
    }), 500


# Register sub-routes
from .v1 import counters as _counters_routes  # noqa: E402
from .v1 import reports as _reports_routes    # noqa: E402
from .v1 import system as _system_routes      # noqa: E402

__all__ = ['api_v1_bp']
