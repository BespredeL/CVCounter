# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Compatibility exports. Implementations live in the focused modules below."""

from system.utils.bytesize import format_bytes
from system.utils.http import is_ajax
from system.utils.nvidia import (
    _cuda_runtime_ok,
    _find_nvidia_smi,
    _get_torch,
    _nvidia_smi_query,
    _parse_nvidia_smi_text,
)
from system.utils.system_info import get_system_info, should_run_startup_system_check, system_check
from system.utils.text import colored_text, pr_color, slug

__all__ = [
    'colored_text',
    'format_bytes',
    'get_system_info',
    'is_ajax',
    'pr_color',
    'should_run_startup_system_check',
    'slug',
    'system_check',
    '_cuda_runtime_ok',
    '_find_nvidia_smi',
    '_get_torch',
    '_nvidia_smi_query',
    '_parse_nvidia_smi_text',
]
