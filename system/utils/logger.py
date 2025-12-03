# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 03.12.2025
# Website: https://bespredel.name

import logging
import traceback
from typing import Optional

from system.managers.config_manager import config


class Logger:
    _instance: Optional['Logger'] = None
    _initialized: bool = False

    def __new__(cls) -> 'Logger':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """
        Initializes the logger.
        """
        if self._initialized:
            return

        log_path = 'errors.log'
        log_level_name = 'INFO'
        log_console = False

        if config is not None:
            log_path = config.get('general.log_path', log_path)
            log_level_name = config.get('general.log_level', log_level_name)
            log_console = bool(config.get('general.log_console', log_console))

        log_level = getattr(logging, str(log_level_name).upper(), logging.INFO)

        self._logger: logging.Logger = logging.getLogger("cvcounter")
        self._logger.setLevel(log_level)

        if not self._logger.handlers:
            formatter: logging.Formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

            # File handler
            file_handler: logging.FileHandler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)

            # Console handler (optional)
            if log_console:
                console_handler: logging.StreamHandler = logging.StreamHandler()
                console_handler.setLevel(log_level)
                console_handler.setFormatter(formatter)
                self._logger.addHandler(console_handler)

        self._initialized = True

    def log(self, level: int, msg: str, *args, **kwargs) -> None:
        """
        Logs a message with the specified level.

        Args:
            level (int): Logging level
            msg (str or Exception): Message to log
            *args: Variable number of positional arguments
            **kwargs: Arbitrary keyword arguments

        Returns:
            None
        """
        self._logger.log(level, msg, *args, **kwargs)

    def error(self, msg: str | Exception) -> None:
        """
        Logs an error message.

        Args:
            msg (str): The error message to log.

        Returns:
            None
        """
        self._logger.error(msg)

    def warning(self, msg: str) -> None:
        """
        Logs a warning message.

        Args:
            msg (str): The warning message to log.

        Returns:
            None
        """
        self._logger.warning(msg)

    def info(self, msg: str) -> None:
        """
        Logs an info message.

        Args:
            msg (str): The info message to log.

        Returns:
            None
        """
        self._logger.info(msg)

    def debug(self, msg: str) -> None:
        """
        Logs a debug message.

        Args:
            msg (str): The debug message to log.

        Returns:
            None
        """
        self._logger.debug(msg)

    def log_exception(self) -> None:
        """
        Logs the exception that occurred during the execution of the program.
        This function takes no parameters.

        Returns:
            None
        """
        exception_info: str = traceback.format_exc()
        self._logger.error("Exception occurred:\n%s", exception_info)
