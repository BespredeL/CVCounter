# -*- coding: utf-8 -*-
# ! python3

# Developed by: Alexander Kireev
# Created: 01.11.2023
# Updated: 21.07.2024
# Website: https://bespredel.name

import traceback
from datetime import datetime


class ErrorLogger:
    """
    Initializes a new instance of the class.

    Parameters:
        file_name (str): The name of the file.

    Returns:
        None
    """

    def __init__(self, file_name):
        self._file_name = file_name

    """
    Writes a log entry to the log file.

    Parameters:
        log_entry (str): The log entry to be written.
    """

    def _write_log(self, log_entry):
        try:
            with open(self._file_name, "a") as file:
                file.write("-----------------------------------------------------------\n")
                file.write(log_entry)
        except Exception as e:
            print(f"Failed to write log: {str(e)}")

    """
    Logs a message with the current timestamp to a file.

    Parameters:
        message_type (str): The type of the message (e.g., 'Error', 'Info', 'Warning').
        message (str): The message to be logged.
    """

    def log(self, message_type, message):

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{current_time}] {message_type}: {message}\n"
        self._write_log(log_entry)

    """
    Logs an error message with the current timestamp to a file.
    
    Parameters:
        error_message (str): The error message to be logged.
        
    Raises:
        Exception: If there is an error while writing to the file.
        
    Returns:
        None
    """

    def log_error(self, error_message):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{current_time}] Error: {error_message}\n"
        self._write_log(log_entry)

    """
    Logs the exception that occurred during the execution of the program.
    This function takes no parameters.
    
    Parameters:
        None
    
    Returns:
        None
    """

    def log_exception(self):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        exception_info = traceback.format_exc()
        log_entry = f"[{current_time}] Exception:\n{exception_info}\n"
        self._write_log(log_entry)
