# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

import datetime
import os

from flask import jsonify, request, send_file

from routes.settings import settings_bp
from system.auth import login_required
from system.utils.i18n import trans as translate


def _resolve_app_log_path() -> str:
    """
    Resolve the absolute path to the main application log file.

    Returns:
        str: Absolute path to the log file.
    """
    from system.utils.logger import Logger, DEFAULT_LOG_PATH
    from system.utils.paths import resolve_project_path

    log_logger = Logger()
    path = log_logger.log_path or resolve_project_path(DEFAULT_LOG_PATH) or DEFAULT_LOG_PATH
    if not os.path.isabs(path):
        resolved = resolve_project_path(path)
        if resolved:
            path = resolved
    return path


def _format_file_size(size_bytes: int) -> str:
    """
    Format a byte count into a human-readable size string.
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


@settings_bp.route('/settings/api/logs', methods=['GET'])
@login_required
def api_get_logs():
    """
    Retrieve application log entries with optional line limit, level filtering, and search query.

    Query parameters:
        lines: int (default 100, clamped to 10..2000)
        level: str (optional: INFO, WARNING, ERROR, DEBUG)
        q: str (optional substring search filter)

    Returns:
        Response: JSON payload containing log metadata and lines.
    """
    log_path = _resolve_app_log_path()
    lines_req = request.args.get('lines', 100, type=int)
    lines_limit = max(10, min(lines_req, 2000))
    level_filter = (request.args.get('level') or '').strip().upper()
    search_q = (request.args.get('q') or '').strip().lower()

    if not os.path.isfile(log_path):
        return jsonify({
            'ok': True,
            'path': os.path.basename(log_path),
            'full_path': log_path,
            'exists': False,
            'file_size': 0,
            'file_size_formatted': '0 B',
            'mtime': None,
            'total_lines': 0,
            'filtered_count': 0,
            'lines': []
        })

    try:
        file_size = os.path.getsize(log_path)
        mtime_str = datetime.datetime.fromtimestamp(os.path.getmtime(log_path)).strftime('%Y-%m-%d %H:%M:%S')

        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)

        filtered = all_lines
        if level_filter in ('INFO', 'WARNING', 'ERROR', 'DEBUG'):
            token = f" - {level_filter} - "
            filtered = [line for line in filtered if token in line]

        if search_q:
            filtered = [line for line in filtered if search_q in line.lower()]

        result_lines = [line.rstrip('\r\n') for line in filtered[-lines_limit:]]

        return jsonify({
            'ok': True,
            'path': os.path.basename(log_path),
            'full_path': log_path,
            'exists': True,
            'file_size': file_size,
            'file_size_formatted': _format_file_size(file_size),
            'mtime': mtime_str,
            'total_lines': total_lines,
            'filtered_count': len(filtered),
            'lines': result_lines
        })
    except Exception as exc:
        return jsonify({
            'ok': False,
            'error': str(exc)
        }), 500


@settings_bp.route('/settings/api/logs/download', methods=['GET'])
@login_required
def api_download_logs():
    """
    Download the main server log file as an attachment.
    """
    log_path = _resolve_app_log_path()
    if not os.path.isfile(log_path):
        return jsonify({'ok': False, 'error': translate('Log file not found')}), 404

    return send_file(
        log_path,
        as_attachment=True,
        download_name=os.path.basename(log_path),
        mimetype='text/plain'
    )


@settings_bp.route('/settings/api/logs/clear', methods=['POST'])
@login_required
def api_clear_logs():
    """
    Clear/truncate the application log file.
    """
    from system.utils.logger import Logger
    from system.utils.paths import ensure_parent_dir

    log_path = _resolve_app_log_path()
    try:
        ensure_parent_dir(log_path)
        with open(log_path, 'w', encoding='utf-8') as f:
            now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"{now_str} - INFO - Log file cleared by user\n")

        Logger().info("Application log cleared by user")
        return jsonify({
            'ok': True,
            'message': translate('Log file cleared successfully')
        })
    except Exception as exc:
        return jsonify({
            'ok': False,
            'error': str(exc)
        }), 500
