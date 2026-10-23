# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

from __future__ import annotations

from collections import deque
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
LAST_SEND_FILE = 'storage/telemetry/last_send.json'
MAX_QUEUE_DISK_BYTES = 512 * 1024

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

__all__ = [name for name in globals() if not name.startswith('__')]
