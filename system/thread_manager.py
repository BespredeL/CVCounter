# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 31.03.2025
# Updated: 31.03.2025
# Website: https://bespredel.name

from threading import Lock, Thread
from typing import Callable


class ThreadManager:
    """
    Thread manager for managing threads in the application.
    
    This class provides safe thread management using locks
    and provides methods for starting and stopping threads.
    """

    def __init__(self):
        """
        Initialize the thread manager.
        
        Creates a dictionary for storing threads and a lock for ensuring
        thread safety when working with threads.
        """
        self.threads: dict[str, Thread] = {}
        self.lock: Lock = Lock()

    def start_thread(self, location: str, target: Callable) -> None:
        """
        Starts a new thread for the specified location.
        
        Args:
            location (str): Location identifier
            target (Callable): Target function to execute in the thread
            
        Note:
            If a thread for the specified location already exists, a new thread will not be created.
        """
        with self.lock:
            if location not in self.threads:
                self.threads[location] = Thread(target=target)
                self.threads[location].start()

    def stop_thread(self, location: str) -> None:
        """
        Stops and removes the thread for the specified location.
        
        Args:
            location (str): Location identifier
            
        Note:
            If a thread for the specified location does not exist, nothing happens.
        """
        with self.lock:
            if location in self.threads:
                del self.threads[location]

    def get_thread(self, location: str) -> Thread | None:
        """
        Returns the thread for the specified location.
        
        Args:
            location (str): Location identifier
            
        Returns:
            Thread | None: Thread for the specified location or None if the thread does not exist
        """
        with self.lock:
            return self.threads.get(location)

    def has_thread(self, location: str) -> bool:
        """
        Checks if a thread exists for the specified location.
        
        Args:
            location (str): Location identifier
            
        Returns:
            bool: True if the thread exists, False otherwise
        """
        with self.lock:
            return location in self.threads

    def stop_all_threads(self) -> None:
        """
        Stops and removes all threads.
        
        Note:
            This method should be called when the application is shutting down.
        """
        with self.lock:
            self.threads.clear()
