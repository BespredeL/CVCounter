# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 04.06.2026
# Updated: 04.06.2026
# Website: https://bespredel.name

from typing import Any

from system.utils.utils import trans as translate


def build_frontend_i18n(language_code: str | None = None) -> dict[str, Any]:
    """
    Build nested translation map for client-side scripts.

    Keys are stable identifiers (dot-path groups). Values are translated strings
    for the active UI language.

    Args:
        language_code: Language code (e.g. ru, en). Defaults to ru.

    Returns:
        dict: Nested i18n tree injected as window.APP_I18N.
    """
    lang = language_code or 'ru'

    def t(text: str, **kwargs: Any) -> str:
        return translate(text, lang=lang, **kwargs)

    return {
        'socket': {
            'connectionOk': t('Connection to server successful'),
            'connectionError': t('Error connecting to the server. Contact the IT department.'),
            'reloadPage': t('Reload page'),
        },
        'dashboard': {
            'running': t('Counter running'),
            'paused': t('Counter paused'),
            'stopped': t('Counter stopped'),
            'error': t('Counting has error!'),
            'toastStarted': t('Counting has started!'),
            'toastStopped': t('Counting has stopped!'),
            'toastPaused': t('Counting has paused!'),
            'toastError': t('Counting has error!'),
            'requestFailed': t('Request failed'),
            'confirmStop': t('Stop counter'),
            'startCounter': t('Start counter'),
            'resumeCounting': t('Resume counting'),
            'pauseCounting': t('Pause counting'),
            'openVideo': t('Open video'),
            'openText': t('Open text'),
            'selectAtLeastOne': t('Select at least one counter'),
            'multiSelectedTemplate': t('Multi counter selected count'),
            'filterEmpty': t('No counters match filter'),
            'statsTemplate': t('Counters stats'),
            'counterSettings': t('Counter settings'),
            'settingsSaved': t('Settings saved'),
            'loadingSettings': t('Loading settings'),
            'settingsRestartHint': t('Stop and start the counter to apply all changes'),
        },
        'countingArea': {
            'defaultHint': t('Click to add points. Drag vertices to adjust. Double-click a vertex to remove.'),
            'rectHint': t('Drag on the image to draw a rectangle.'),
            'points': t('Points'),
            'minPoints': t('need at least 3 points'),
            'minPointsToast': t('At least 3 points required'),
            'saved': t('Zone saved'),
        },
    }
