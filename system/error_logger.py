# -*- coding: utf-8 -*-
# ! python3

# Developed by: Alexander Kireev
# Created: 01.11.2023
# Updated: 19.04.2024
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
    Logs an error message with the current timestamp to a file.
    
    Parameters:
        error_message (str): The error message to be logged.
        
    Raises:
        Exception: If there is an error while writing to the file.
        
    Returns:
        None
    """

    def log_error(self, error_message):
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self._file_name, "a") as file:
                file.write(f"-----------------------------------------------------------\n")
                file.write(f"[{current_time}] Error: {error_message}\n")
        except Exception as e:
            print(f"Failed to log error: {str(e)}")

    """
    Logs the exception that occurred during the execution of the program.
    This function takes no parameters.
    
    Parameters:
        None
    
    Returns:
        None
    """

    def log_exception(self):
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self._file_name, "a") as file:
                file.write(f"-----------------------------------------------------------\n")
                file.write(f"[{current_time}] Exception:\n")
                traceback.print_exc(file=file)
                file.write("\n")
        except Exception as e:
            print(f"Failed to log exception: {str(e)}")
