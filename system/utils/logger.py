# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 26.07.2026
# Website: https://bespredel.name

import logging
from logging.handlers import RotatingFileHandler
import os
import sys
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

        Args:
            config_manager: ConfigManager - The config manager to apply the logging settings from.

        Returns:
            None
        """
        log_path = config_manager.get('general.log_path') or DEFAULT_LOG_PATH
        log_path = config_manager.resolve_path(log_path) or log_path
        log_level_name = config_manager.get('general.log_level', DEFAULT_LOG_LEVEL)
        log_console = bool(config_manager.get('general.log_console', False))
        cls._apply_config(log_path, log_level_name, log_console)

    @classmethod
    def _apply_config(cls, log_path: str, log_level_name: str, log_console: bool) -> None:
        """
        Apply logging settings from config.
        
        Args:
            log_path: str - The path to the log file.
            log_level_name: str - The name of the log level.
            log_console: bool - Whether to log to the console.
        
        Returns:
            None
        """
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

        file_handler = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding='utf-8')
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
        """
        Get the path to the log file.
        
        Args:
            None

        Returns:
            Optional[str]: The path to the log file.
        """
        return self._log_path

    def log(self, level: int, msg: str, *args, **kwargs) -> None:
        """
        Log a message.
        
        Args:
            level: int - The level of the message.
            msg: str - The message to log.
            *args: Any - The arguments to log.
            **kwargs: Any - The keyword arguments to log.

        Returns:
            None
        """
        self._logger.log(level, msg, *args, **kwargs)

    def error(self, msg: str | Exception) -> None:
        """
        Log an error message.
        
        Args:
            msg: str | Exception - The message to log.

        Returns:
            None
        """
        self._logger.error(msg)
        self._flush_handlers()
        if isinstance(msg, Exception):
            self._notify_telemetry(exc=msg)
        else:
            cur_exc = sys.exc_info()
            if cur_exc[0] is not None:
                self._notify_telemetry(exc_info=cur_exc)
            else:
                self._notify_telemetry_error(str(msg))

    def warning(self, msg: str) -> None:
        """
        Log a warning message.
        
        Args:
            msg: str - The message to log.
        
        Returns:
            None
        """
        self._logger.warning(msg)

    def info(self, msg: str) -> None:
        """
        Log an info message.
        
        Args:
            msg: str - The message to log.
        
        Returns:
            None
        """
        self._logger.info(msg)

    def debug(self, msg: str) -> None:
        """
        Log a debug message.
        
        Args:
            msg: str - The message to log.
        
        Returns:
            None
        """
        self._logger.debug(msg)

    def log_exception(self, exc_info=None) -> None:
        """
        Log an exception.
        
        Args:
            exc_info: Optional[Tuple[Type[BaseException], BaseException, TracebackType]] - The exception to log.
        
        Returns:
            None
        """
        resolved_exc_info = exc_info if exc_info is not None else sys.exc_info()
        if resolved_exc_info and resolved_exc_info[0] is not None:
            exception_info = ''.join(traceback.format_exception(*resolved_exc_info))
        else:
            exception_info = traceback.format_exc()
        self._logger.error("Exception occurred:\n%s", exception_info)
        self._flush_handlers()
        self._notify_telemetry(exc_info=resolved_exc_info)

    def exception(self, msg: str, exc_info=None) -> None:
        """
        Log an exception.
        
        Args:
            msg: str - The message to log.
            exc_info: Optional[Tuple[Type[BaseException], BaseException, TracebackType]] - The exception to log.
        
        Returns:
            None
        """
        resolved_exc_info = exc_info if exc_info is not None else sys.exc_info()
        if exc_info is None:
            self._logger.error(msg, exc_info=True)
        else:
            self._logger.error(msg, exc_info=exc_info)
        self._flush_handlers()
        self._notify_telemetry(exc_info=resolved_exc_info)

    def _notify_telemetry(self, exc: Optional[BaseException] = None, exc_info=None) -> None:
        """
        Notify telemetry of an exception.
        
        Args:
            exc: Optional[BaseException] - The exception to log.
            exc_info: Optional exception tuple from sys.exc_info().
        
        Returns:
            None
        """
        try:
            from system.utils.telemetry import get_telemetry
            get_telemetry().capture_exception(exc=exc, exc_info=exc_info)
        except Exception:
            pass

    def _notify_telemetry_error(self, message: str) -> None:
        """
        Notify telemetry of a logged error message.
        
        Args:
            message: str - The error message to log.
            
        Returns:
            None
        """
        try:
            from system.utils.telemetry import get_telemetry
            get_telemetry().capture_error_message(message=message)
        except Exception:
            pass

    def _flush_handlers(self) -> None:
        """
        Flush the handlers.
        
        Args:
            None
        
        Returns:
            None
        """
        for handler in self._logger.handlers:
            handler.flush()
