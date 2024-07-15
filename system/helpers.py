# -*- coding: utf-8 -*-
# ! python3

# Developed by: Alexander Kireev
# Created: 22.03.2024
# Updated: 12.07.2024
# Website: https://bespredel.name

import json
import re

"""
Translates the given text to the specified language using the provided translations.

Parameters:
    text (str): The text to be translated.
    lang (str, optional): The language code to translate the text to. Defaults to 'ru'.
    **kwargs: Additional keyword arguments to be used for placeholder replacement in the translated text.

Returns:
    str: The translated text with any placeholder replacements made.

Raises:
    None

Examples:
    >>> trans('Hello', lang='ru')
    'Привет'

    >>> trans('The weather is {weather}', lang='ru', weather='sunny')
    'Погода солнечная'
"""


def trans(text, lang='ru', **kwargs):
    def load_translations(language_code):
        try:
            file_path = f"langs/{language_code}.json"
            with open(file_path, "r", encoding="utf-8") as file:
                translations = json.load(file)
            return translations
        except Exception:
            return {}

    lang_list = load_translations(lang)

    if text in lang_list:
        text = lang_list[text]

    if kwargs:
        for key, value in kwargs.items():
            text = text.replace('{' + key + '}', str(value))

    return text


"""
Create slug

Parameters:
    s (str): The text to be slug.

Returns:
    str: Slug string
"""


def slug(s):
    s = s.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_-]+', '-', s)
    s = re.sub(r'^-+|-+$', '', s)
    return s
