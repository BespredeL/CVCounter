# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 31.03.2025
# Updated: 31.03.2025
# Website: https://bespredel.name

import time


class Timer:
    """A class for measuring code execution time.
    
    This class implements a context manager for convenient measurement
    of code block execution time using the with statement.
    
    Attributes:
        elapsed (float): Elapsed time in seconds
        _start (float): Start time of measurement
    """

    def __init__(self):
        """Initialize a new timer."""
        self.elapsed = 0
        self._start = 0

    def __enter__(self):
        """Start time measurement.
        
        Returns:
            Timer: Returns the timer instance for use in with block
        """
        self._start = time.time()
        return self

    def __exit__(self, *args):
        """End time measurement and save the result.
        
        Args:
            *args: Ignored arguments for context manager protocol compatibility
        """
        self.elapsed = time.time() - self._start
