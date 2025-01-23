# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 22.03.2024
# Updated: 23.01.2025
# Website: https://bespredel.name

import json
import re
import subprocess
from shutil import disk_usage
import platform
from typing import Any, Dict

import psutil
import torch
from flask import request


def is_ajax() -> bool:
    """Check if the request is an AJAX request."""
    return str(request.headers.get('X-Requested-With')).lower() == 'XMLHttpRequest'.lower()


def trans(text: str, **kwargs: dict) -> str:
    """
    Translates the given text to the specified language using the provided translations.

    Args:
        text (str): The text to be translated.
        kwargs (dict, optional): A dictionary of arguments including:
            - 'lang': Language code for translation (default: 'ru').
            - Other placeholder replacements.

    Returns:
        str: The translated text with any placeholder replacements made.

    Examples:
        >>> trans('Hello')
        'Привет'

        >>> trans('The weather is {weather}', weather='sunny')
        'Погода солнечная'
    """
    if kwargs is None:
        kwargs = {}

    # Extract the language or default to 'ru'
    lang = kwargs.pop('lang', 'ru')

    lang_list = load_translations(lang)
    if text in lang_list:
        text = lang_list[text]

    # Replace placeholders in the text
    for key, value in kwargs.items():
        text = text.replace('{' + key + '}', str(value))

    return text


def load_translations(language_code: str) -> dict:
    """
    Load translations

    Args:
        language_code (str): The language code to load translations for.

    Returns:
        dict: A dictionary of translations for the specified language code.

    Raises:
        None
    """
    try:
        file_path = f"langs/{language_code}.json"
        with open(file_path, "r", encoding="utf-8") as file:
            translations = json.load(file)
        return translations
    except Exception:
        return {}


def slug(s: str) -> str:
    """
    Create slug

    Args:
        s (str): The text to be slugged.

    Returns:
        str: Slug string
    """
    s = s.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_-]+', '-', s)
    s = re.sub(r'^-+|-+$', '', s)
    return s


def pr_color(text: str, color: str) -> None:
    """
    Print with color

    Args:
        text (str): The text to be printed.
        color (str): The color to print the text in.

    Returns:
        None
    """
    colors = {
        'red': "\033[91m",
        'green': "\033[92m",
        'yellow': "\033[93m",
        'cyan': "\033[96m",
        'light_gray': "\033[97m",
        'black': "\033[98m"
    }
    if color not in colors:
        raise ValueError(f"Invalid color '{color}'. Valid options are: {', '.join(colors.keys())}")
    color_code = colors[color]
    print(f"{color_code}{text}\033[00m")


def colored_text(text: str, color: str) -> str:
    """
    Colored text

    Args:
        text (str): The text to be printed.
        color (str): The color to print the text in.

    Returns:
        str: Colored text
    """
    colors = {
        'red': "\033[91m",
        'green': "\033[92m",
        'yellow': "\033[93m",
        'cyan': "\033[96m",
        'light_gray': "\033[97m",
        'black': "\033[98m"
    }
    if color not in colors:
        raise ValueError(f"Invalid color '{color}'. Valid options are: {', '.join(colors.keys())}")
    color_code = colors.get(color, "\033[97m")  # Default to light gray if color not found
    return "{}{}\033[00m".format(color_code, text)


def format_bytes(size: int) -> str:
    """
    Format bytes to a human-readable size

    Args:
        size (int): The size to be formatted.

    Returns:
        str: The formatted size.
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def get_system_info() -> dict[str | Any, str | int | Any]:
    """
    Get system information

    Returns:
        None
    """

    # Extract NVIDIA-SMI, Driver Version, and CUDA Version
    result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
    nvidia_smi_version = re.search(r'NVIDIA-SMI (\d+\.\d+)', result.stdout)
    driver_version = re.search(r'Driver Version: (\d+\.\d+)', result.stdout)
    cuda_version = re.search(r'CUDA Version: (\d+\.\d+)', result.stdout)
    cuda_available = torch.cuda.is_available()

    # Extract information from the output
    virtual_memory = psutil.virtual_memory()._asdict()
    swap_memory = psutil.swap_memory()._asdict()
    disk_usages = disk_usage('/')._asdict()

    sys_info = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": psutil.cpu_count(logical=False),
        "cpu_percent": f"{psutil.cpu_percent(interval=1)} %",

        "nvidia_smi_version": nvidia_smi_version.group(1) if nvidia_smi_version else None,
        "driver_version": driver_version.group(1) if driver_version else None,
        "cuda_version": cuda_version.group(1) if cuda_version else None,
        "py_torch_cuda_available": "Yes" if cuda_available else None,
        "py_torch_cuda_version": torch.version.cuda or None,
        "py_torch_version": torch.__version__,

        "virtual_memory": {
            "total": format_bytes(virtual_memory['total']),
            "available": format_bytes(virtual_memory['available']),
            "used": format_bytes(virtual_memory['used']),
            "free": format_bytes(virtual_memory['free']),
            "percent": f"{virtual_memory['percent']} %"
        },
        "swap_memory": {
            "total": format_bytes(swap_memory['total']),
            "used": format_bytes(swap_memory['used']),
            "free": format_bytes(swap_memory['free']),
            "percent": f"{swap_memory['percent']} %"
        },
        "disk_usage": {
            "total": format_bytes(disk_usages['total']),
            "used": format_bytes(disk_usages['used']),
            "free": format_bytes(disk_usages['free'])
        }
    }

    return sys_info


def system_check() -> None:
    """
    System check

    Returns:
        None
    """

    # Execute nvidia-smi in the console and capture the output
    sys_info = get_system_info()

    def colored_value(value):
        if value == "N/A":
            return colored_text(value, 'red')
        else:
            return colored_text(value, 'green')

    # Print the extracted values
    pr_color(f' * NVIDIA-SMI Version: {colored_value(sys_info["nvidia_smi_version"] or "N/A")}',
             'yellow')
    pr_color(f' * Driver Version: {colored_value(sys_info["driver_version"] or "N/A")}', 'yellow')
    pr_color(f' * CUDA Version: {colored_value(sys_info["cuda_version"] or "N/A")}', 'yellow')

    # Check CUDA availability using PyTorch
    pr_color(f' * PyTorch CUDA Available: {colored_value(sys_info["py_torch_cuda_available"] or "N/A")}', 'yellow')
    pr_color(f' * PyTorch CUDA Version: {colored_value(sys_info["py_torch_cuda_version"] or "N/A")}', 'yellow')

    # Check PyTorch version
    pr_color(f' * PyTorch Version: {colored_value(sys_info["py_torch_version"] or "N/A")}', 'yellow')

    # Result of system check
    if (not sys_info["py_torch_cuda_available"] or not sys_info["nvidia_smi_version"] or not sys_info["driver_version"]
            or not sys_info["cuda_version"] or not sys_info["py_torch_version"]):
        print(f'{colored_text(" * System Check Result:", "yellow")} {colored_text("FAILED", "red")}')
    else:
        print(f'{colored_text(" * System Check Result:", "yellow")} {colored_text("PASSED", "green")}')
