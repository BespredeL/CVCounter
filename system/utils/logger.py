# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 09.06.2026
# Website: https://bespredel.name

import logging
import os
import traceback
from typing import Any, Optional

from system.utils.paths import ensure_parent_dir, resolve_project_path

DEFAULT_LOG_PATH = 'storage/logs/cvcounter.log'
DEFAULT_LOG_LEVEL = 'INFO'


class Logger:
    _instance: Optional['Logger'] = None
    _configured: bool = False
    _log_path: Optional[str] = None

    def __new__(cls) -> 'Logger':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not self._configured:
            self._apply_config(
                log_path=resolve_project_path(DEFAULT_LOG_PATH) or DEFAULT_LOG_PATH,
                log_level_name=DEFAULT_LOG_LEVEL,
                log_console=False,
            )

    @classmethod
    def configure_from_config(cls, config_manager: Any) -> None:
        """
        Apply logging settings from ConfigManager.

        Must be called after config is loaded so the file handler uses the correct path.
        """
        log_path = config_manager.get('general.log_path') or DEFAULT_LOG_PATH
        log_path = config_manager.resolve_path(log_path) or log_path
        log_level_name = config_manager.get('general.log_level', DEFAULT_LOG_LEVEL)
        log_console = bool(config_manager.get('general.log_console', False))
        cls._apply_config(log_path, log_level_name, log_console)

    @classmethod
    def _apply_config(cls, log_path: str, log_level_name: str, log_console: bool) -> None:
        if not log_path:
            log_path = resolve_project_path(DEFAULT_LOG_PATH) or DEFAULT_LOG_PATH
        elif not os.path.isabs(log_path):
            log_path = resolve_project_path(log_path) or log_path

        ensure_parent_dir(log_path)

        log_level = getattr(logging, str(log_level_name).upper(), logging.INFO)
        logger = logging.getLogger('cvcounter')
        logger.setLevel(log_level)
        logger.propagate = False

        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)

        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        if log_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        cls._instance._logger = logger
        cls._log_path = log_path
        cls._configured = True

    @property
    def log_path(self) -> Optional[str]:
        return self._log_path

    def log(self, level: int, msg: str, *args, **kwargs) -> None:
        self._logger.log(level, msg, *args, **kwargs)

    def error(self, msg: str | Exception) -> None:
        self._logger.error(msg)
        self._flush_handlers()

    def warning(self, msg: str) -> None:
        self._logger.warning(msg)

    def info(self, msg: str) -> None:
        self._logger.info(msg)

    def debug(self, msg: str) -> None:
        self._logger.debug(msg)

    def log_exception(self, exc_info=None) -> None:
        if exc_info is None:
            exception_info = traceback.format_exc()
        else:
            exception_info = ''.join(traceback.format_exception(*exc_info))
        self._logger.error("Exception occurred:\n%s", exception_info)
        self._flush_handlers()

    def exception(self, msg: str, exc_info=None) -> None:
        if exc_info is None:
            self._logger.error(msg, exc_info=True)
        else:
            self._logger.error(msg, exc_info=exc_info)
        self._flush_handlers()

    def _flush_handlers(self) -> None:
        for handler in self._logger.handlers:
            handler.flush()
