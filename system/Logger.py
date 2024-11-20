# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 20.11.2024
# Website: https://bespredel.name

import logging
import traceback
from config import config


class Logger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    """
    Initializes a new instance of the class.

    Returns:
        None
    """

    def _initialize(self):
        self._logger = logging.getLogger(__name__)
        self._logger.setLevel(logging.DEBUG)

        # Creating a handler for writing to a file
        file_handler = logging.FileHandler(config.get('general.log_path', 'errors.log'), encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        # Creating a handler for console output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Adding handlers to the logger
        self._logger.addHandler(file_handler)
        self._logger.addHandler(console_handler)

        self.print_logs = True

    """
    Logs a message with the specified level.
    
    Parameters:
        level (int): The logging level.
        msg (str): The message to log.
        *args: Variable length argument list.
        **kwargs: Arbitrary keyword arguments.
    
    Returns:
        None
    """

    def log(self, level, msg, *args, **kwargs):
        self._logger.log(level, msg, *args, **kwargs)

    """
    Logs an error message.
    
    Parameters:
        msg (str): The error message to log.
    
    Returns:
        None
    """

    def error(self, msg):
        self._logger.error(msg)

    """
    Logs a warning message.
    
    Parameters:
        msg (str): The warning message to log.
    
    Returns:
        None
    """

    def warning(self, msg):
        self._logger.warning(msg)

    """
    Logs an info message.
    
    Parameters:
        msg (str): The info message to log.
    
    Returns:
        None
    """

    def info(self, msg):
        self._logger.info(msg)

    """
    Logs a debug message.
    
    Parameters:
        msg (str): The debug message to log.
    
    Returns:
        None
    """

    def debug(self, msg):
        self._logger.debug(msg)

    """
    Logs the exception that occurred during the execution of the program.
    This function takes no parameters.
    
    Parameters:
        None
    
    Returns:
        None
    """

    def log_exception(self):
        exception_info = traceback.format_exc()
        self._logger.error("Exception occurred:\n%s", exception_info)
