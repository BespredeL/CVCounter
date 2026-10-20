# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

import json
from typing import Any, Dict

from flask import abort, jsonify, request

from routes.api import api_v1_bp
from system.auth.api_auth import api_key_required
from system.db.models.cvcounter import CVCounter
from system.utils.app_context import get_app_context


def _serialize_report(record: CVCounter) -> Dict[str, Any]:
    """Serialize a CVCounter SQLAlchemy instance to a clean JSON-friendly dictionary."""
    custom_fields = {}
    if record.custom_fields:
        try:
            custom_fields = json.loads(record.custom_fields)
        except Exception:
            custom_fields = record.custom_fields

    class_counts = []
    if record.class_counts:
        try:
            class_counts = json.loads(record.class_counts)
        except Exception:
            class_counts = record.class_counts

    def _safe_int(val, default=0):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    return {
        'id': record.id,
        'location': record.location,
        'total_count': _safe_int(record.total_count),
        'source_count': _safe_int(record.source_count),
        'defects_count': _safe_int(record.defects_count),
        'correct_count': _safe_int(record.correct_count),
        'custom_fields': custom_fields,
        'class_counts': class_counts,
        'active': bool(record.active),
        'created_at': record.created_at.isoformat() if record.created_at else None,
        'updated_at': record.updated_at.isoformat() if record.updated_at else None,
    }


@api_v1_bp.route('/reports', methods=['GET'])
@api_key_required(role='read')
def list_reports():
    """
    Query saved reports with optional filters and pagination.
    Query params:
        location: str (optional)
        active: bool (optional)
        limit: int (default 20, max 100)
        offset: int (default 0)
    """
    context = get_app_context()
    db_manager = context['db_manager']

    location = request.args.get('location', '').strip()
    active_param = request.args.get('active')
    
    try:
        limit = min(max(int(request.args.get('limit', 20)), 1), 100)
    except ValueError:
        limit = 20

    try:
        offset = max(int(request.args.get('offset', 0)), 0)
    except ValueError:
        offset = 0

    session = db_manager.create_session()
    try:
        query = session.query(CVCounter)
        if location:
            query = query.filter(CVCounter.location == location)
        if active_param is not None:
            active_bool = active_param.lower() in ('1', 'true', 'yes')
            query = query.filter(CVCounter.active == active_bool)

        total = query.count()
        records = (
            query.order_by(CVCounter.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = [_serialize_report(rec) for rec in records]

        return jsonify({
            'success': True,
            'data': {
                'total': total,
                'limit': limit,
                'offset': offset,
                'items': items,
            }
        })
    finally:
        session.close()


@api_v1_bp.route('/reports/<int:report_id>', methods=['GET'])
@api_key_required(role='read')
def get_report(report_id: int):
    """
    Get full details of a specific report by ID.
    """
    context = get_app_context()
    db_manager = context['db_manager']

    record = db_manager.get_count(report_id)
    if not record:
        return jsonify({
            'success': False,
            'error': {
                'code': 'not_found',
                'message': f"Report #{report_id} not found",
            }
        }), 404

    return jsonify({
        'success': True,
        'data': _serialize_report(record),
    })


@api_v1_bp.route('/reports/<int:report_id>', methods=['DELETE'])
@api_key_required(role='admin')
def delete_report(report_id: int):
    """
    Delete a report by ID (admin only).
    """
    context = get_app_context()
    db_manager = context['db_manager']

    record = db_manager.get_count(report_id)
    if not record:
        return jsonify({
            'success': False,
            'error': {
                'code': 'not_found',
                'message': f"Report #{report_id} not found",
            }
        }), 404

    location = record.location
    success = db_manager.delete_count(report_id)
    if not success:
        return jsonify({
            'success': False,
            'error': {
                'code': 'delete_failed',
                'message': f"Failed to delete report #{report_id}",
            }
        }), 500

    return jsonify({
        'success': True,
        'data': {
            'id': report_id,
            'location': location,
            'deleted': True,
        }
    })
