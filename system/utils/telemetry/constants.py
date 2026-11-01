# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

from collections import deque
import gzip
import hashlib
import hmac
import json
import os
import platform
import queue
import shutil
import socket
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from system.__version__ import APP_VERSION
from system.utils.paths import ensure_parent_dir, resolve_project_path
from system.utils.telemetry_sanitize import sanitize_props, sanitize_text

SCHEMA_VERSION = 1
DEFAULT_ENDPOINT = 'https://bespredel.name/api/cvcounter/telemetry'
DEFAULT_LOG_PATH = 'storage/logs/cvcounter.log'
TELEMETRY_DIR = 'storage/telemetry'
INSTALL_ID_FILE = 'storage/telemetry/install_id'
QUEUE_FILE = 'storage/telemetry/queue.jsonl'
QUARANTINE_FILE = 'storage/telemetry/quarantine.jsonl'
LAST_SEND_FILE = 'storage/telemetry/last_send.json'
MAX_QUEUE_DISK_BYTES = 512 * 1024
MAX_QUARANTINE_LINES = 200
MAX_SPILL_ATTEMPTS = 3
SPILL_KEEP_RATIO = 0.6

WORKER_RESTART_WINDOW_SEC = 60.0
WORKER_RESTART_LIMIT = 3
WORKER_RESTART_COOLDOWN_SEC = 60.0

_CMD_EVENT = 'event'
_CMD_FLUSH = 'flush'
_CMD_MANUAL = 'manual'
_CMD_SHUTDOWN = 'shutdown'


def _utc_now_iso() -> str:
    """
    Return the current UTC time in ISO format.
    
    Returns:
        str: The current UTC time in ISO format.
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _safe_int(value: Any, default: int) -> int:
    """
    Convert a value to an integer, returning the default value if the conversion fails.
    
    Args:
        value: The value to convert to an integer.
        default: The default value to return if the conversion fails.
        
    Returns:
        int: The integer value of the input, or the default value if the conversion fails.
    """
    try:
        parsed = int(value)
        return parsed if parsed >= 1 else default
    except (TypeError, ValueError):
        return default


def _message_hash(message: str) -> str:
    """
    Generate a SHA-256 hash of a message.
    
    Args:
        message: The message to hash.
        
    Returns:
        str: The SHA-256 hash of the message.
    """
    return hashlib.sha256(message.encode('utf-8', errors='replace')).hexdigest()[:16]


def _read_spill_record(raw: str) -> tuple[int, Optional[dict[str, Any]]]:
    """
    Parse one spilled queue line into its attempt counter and event.

    Args:
        raw: A single line from the queue file.

    Returns:
        tuple[int, Optional[dict[str, Any]]]: Attempts and event, or (0, None) when the line is unusable.
    """
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return 0, None
    if not isinstance(parsed, dict):
        return 0, None
    event = parsed.get('event')
    if isinstance(event, dict):
        return _safe_int(parsed.get('attempts'), 1), event
    # Queues written before the attempt counter stored bare events
    return 1, parsed


def _write_spill_record(attempts: int, event: dict[str, Any]) -> str:
    """
    Serialize one spilled queue line.

    Args:
        attempts: How many delivery attempts this event already made.
        event: The normalized event payload.

    Returns:
        str: JSON line content without the trailing newline.
    """
    return json.dumps({'attempts': int(attempts), 'event': event}, ensure_ascii=False)


def _classify_post_failure(status_code: Optional[int]) -> str:
    """
    Classify a failed batch delivery.

    Args:
        status_code: HTTP status, or None when the request never reached the server.

    Returns:
        str: 'retry' when resending can help, 'permfail' when the server keeps rejecting this batch.
    """
    if status_code is None:
        return 'retry'
    if status_code in (408, 425, 429) or status_code >= 500:
        return 'retry'
    if 400 <= status_code < 500:
        return 'permfail'
    return 'retry'


__all__ = [name for name in globals() if not name.startswith('__')]
