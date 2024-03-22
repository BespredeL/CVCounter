# -*- coding: utf-8 -*-
# ! python3

# Developed by: Alexander Kireev
# Created: 22.03.2024
# Updated: 22.03.2024
# Website: https://bespredel.name

import json


# TODO: There are no ideas yet on how to select a language from the settings using already loaded settings
def trans(text, lang='ru', **kwargs):
    def load_translations(language_code):
        try:
            file_path = f"langs/{language_code}.json"
            with open(file_path, "r", encoding="utf-8") as file:
                translations = json.load(file)
            return translations
        except FileNotFoundError:
            return {}
        except Exception:
            return {}

    lang_list = load_translations(lang)

    if text in lang_list:
        text = lang_list[text]

    if kwargs:
        for key, value in kwargs.items():
            text = text.replace('{' + key + '}', str(value))

    return text
