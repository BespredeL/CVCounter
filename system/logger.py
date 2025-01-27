# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 27.01.2025
# Website: https://bespredel.name

import logging
import traceback

from config import config


class Logger:
    _instance: 'Logger' = None

    def __new__(cls) -> 'Logger':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """
        Initializes a new instance of the class.

        Returns:
            None
        """

        self._logger: logging.Logger = logging.getLogger(__name__)
        self._logger.setLevel(logging.DEBUG)

        # Creating a handler for writing to a file
        file_handler: logging.FileHandler = logging.FileHandler(config.get('general.log_path', 'errors.log'), encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        # Creating a handler for console output
        console_handler: logging.StreamHandler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        formatter: logging.Formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Adding handlers to the logger
        self._logger.addHandler(file_handler)
        self._logger.addHandler(console_handler)

        self.print_logs: bool = True

    def log(self, level: int, msg: str, *args, **kwargs) -> None:
        """
        Logs a message with the specified level.

        Args:
            level (int): The logging level.
            msg (str or Exception): The message to log.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

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
