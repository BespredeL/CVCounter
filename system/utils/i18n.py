# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 08.06.2026
# Updated: 08.06.2026
# Website: https://bespredel.name

import json
import os
from typing import Any

_translations_cache: dict[str, tuple[float, dict]] = {}


def load_translations(language_code: str) -> dict:
    """
    Load translations from langs/{language_code}.json.

    Args:
        language_code: The language code to load translations for.

    Returns:
        A dictionary of translations for the specified language code.
    """
    file_path = f"langs/{language_code}.json"
    try:
        mtime = os.path.getmtime(file_path)
    except OSError:
        return {}

    cached = _translations_cache.get(language_code)
    if cached and cached[0] == mtime:
        return cached[1]

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            translations = json.load(file)
        _translations_cache[language_code] = (mtime, translations)
        return translations
    except Exception:
        return {}


def trans(text: str, **kwargs: Any) -> str:
    """
    Translate text using langs/*.json dictionaries.

    Args:
        text: The text to be translated (English key).
        **kwargs: Language code via 'lang' (default: 'ru') and placeholder replacements.

    Returns:
        Translated text with placeholders replaced.

    Examples:
        >>> trans('Hello')
        'Привет'

        >>> trans('The weather is {weather}', weather='sunny')
        'Погода солнечная'
    """
    lang = kwargs.pop('lang', 'ru')

    lang_list = load_translations(lang)
    if text in lang_list:
        text = lang_list[text]

    for key, value in kwargs.items():
        text = text.replace('{' + key + '}', str(value))

    return text
