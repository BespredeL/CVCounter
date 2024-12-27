# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 22.03.2024
# Updated: 27.12.2024
# Website: https://bespredel.name

import json
import re

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


def system_check() -> None:
    """
    System check

    Returns:
        None
    """
    import subprocess
    import torch
    import re

    # Execute nvidia-smi in the console and capture the output
    result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
    output = result.stdout

    # Extract NVIDIA-SMI, Driver Version, and CUDA Version
    nvidia_smi_version = re.search(r'NVIDIA-SMI (\d+\.\d+)', output)
    driver_version = re.search(r'Driver Version: (\d+\.\d+)', output)
    cuda_version = re.search(r'CUDA Version: (\d+\.\d+)', output)

    def colored_value(value):
        if value == "N/A":
            return colored_text(value, 'red')
        else:
            return colored_text(value, 'green')

    # Print the extracted values
    pr_color(f' * NVIDIA-SMI Version: {colored_value(nvidia_smi_version.group(1) if nvidia_smi_version else "N/A")}',
             'yellow')
    pr_color(f' * Driver Version: {colored_value(driver_version.group(1) if driver_version else "N/A")}', 'yellow')
    pr_color(f' * CUDA Version: {colored_value(cuda_version.group(1) if cuda_version else "N/A")}', 'yellow')

    # Check CUDA availability using PyTorch
    cuda_available = torch.cuda.is_available()
    pr_color(f' * PyTorch CUDA Available: {colored_value("Yes" if cuda_available else "N/A")}', 'yellow')
    pr_color(f' * PyTorch CUDA Version: {colored_value(torch.version.cuda or "N/A")}', 'yellow')

    # Check PyTorch version
    pr_color(f' * PyTorch Version: {colored_value(torch.__version__ or "N/A")}', 'yellow')

    # Result of system check
    if not cuda_available or not nvidia_smi_version or not driver_version or not cuda_version or not torch.__version__:
        print(f'{colored_text(" * System Check Result:", "yellow")} {colored_text("FAILED", "red")}')
    else:
        print(f'{colored_text(" * System Check Result:", "yellow")} {colored_text("PASSED", "green")}')
