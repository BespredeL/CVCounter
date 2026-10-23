# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

import os

try:
    import colorama
    colorama.init()
except Exception:
    if os.name == 'nt':
        os.system('')

_ANSI = {
    'red': "\033[91m",
    'green': "\033[92m",
    'yellow': "\033[93m",
    'cyan': "\033[96m",
    'light_gray': "\033[97m",
    'black': "\033[98m",
}


def _ansi(color: str) -> str:
    """Return the ANSI code for a named color."""
    if color not in _ANSI:
        raise ValueError(f"Invalid color '{color}'. Valid options are: {', '.join(_ANSI.keys())}")
    return _ANSI[color]


def pr_color(text: str, color: str) -> None:
    """
    Print with color

    Args:
        text (str): The text to be printed.
        color (str): The color to print the text in.

    Returns:
        None
    """
    print(f"{_ansi(color)}{text}\033[00m")


def colored_text(text: str, color: str) -> str:
    """
    Colored text

    Args:
        text (str): The text to be printed.
        color (str): The color to print the text in.

    Returns:
        str: Colored text
    """
    return f"{_ansi(color)}{text}\033[00m"


def slug(s: str) -> str:
    """
    Create slug

    Args:
        s (str): The text to be slugged.

    Returns:
        str: Slug string
    """
    import re
    s = s.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_-]+', '-', s)
    s = re.sub(r'^-+|-+$', '', s)
    return s
