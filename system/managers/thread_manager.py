# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 31.03.2025
# Updated: 03.12.2025
# Website: https://bespredel.name

import time
from threading import Lock, Thread
from typing import Callable, Optional

from system.utils.logger import Logger


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
        self.logger: Logger = Logger()
        self._shutdown_timeout: float = 10.0  # Timeout for thread shutdown in seconds

    def start_thread(self, location: str, target: Callable, daemon: bool = False) -> None:
        """
        Starts a new thread for the specified location.
        
        Args:
            location (str): Location identifier
            target (Callable): Target function to execute in the thread
            daemon (bool): Whether the thread should be a daemon thread. Defaults to False.
            
        Note:
            If a thread for the specified location already exists, a new thread will not be created.
        """
        with self.lock:
            if location not in self.threads:
                thread = Thread(target=target, daemon=daemon, name=f"CounterThread-{location}")
                self.threads[location] = thread
                thread.start()
                self.logger.info(f"Started thread for location: {location}")

    def stop_thread(self, location: str, object_counter: Optional[any] = None, timeout: Optional[float] = None) -> bool:
        """
        Stops and removes the thread for the specified location.
        
        This method properly stops the thread by:
        1. Stopping the associated object counter (if provided)
        2. Waiting for the thread to finish with a timeout
        3. Cleaning up resources
        4. Removing the thread from the dictionary
        
        Args:
            location (str): Location identifier
            object_counter (Optional[any]): ObjectCounter instance to stop and cleanup. Defaults to None.
            timeout (Optional[float]): Timeout in seconds to wait for thread to finish. 
                                     Defaults to self._shutdown_timeout.
        
        Returns:
            bool: True if thread was stopped successfully, False otherwise
            
        Note:
            If a thread for the specified location does not exist, returns False.
        """
        if timeout is None:
            timeout = self._shutdown_timeout

        with self.lock:
            if location not in self.threads:
                self.logger.warning(f"Thread for location '{location}' does not exist")
                return False

            thread = self.threads[location]

        # Stop the object counter if provided (this sets running=False)
        if object_counter is not None:
            try:
                self.logger.info(f"Stopping object counter for location: {location}")
                object_counter.stop()
            except Exception as e:
                self.logger.error(f"Error stopping object counter for {location}: {e}")

        # Wait for thread to finish
        if thread.is_alive():
            self.logger.info(f"Waiting for thread '{location}' to finish (timeout: {timeout}s)")
            thread.join(timeout=timeout)

            if thread.is_alive():
                self.logger.warning(f"Thread '{location}' did not finish within timeout {timeout}s")
                # Cleanup resources even if thread didn't finish
                if object_counter is not None:
                    try:
                        object_counter.cleanup()
                    except Exception as e:
                        self.logger.error(f"Error during cleanup for {location}: {e}")
                return False
            else:
                self.logger.info(f"Thread '{location}' finished successfully")

        # Cleanup resources
        if object_counter is not None:
            try:
                object_counter.cleanup()
            except Exception as e:
                self.logger.error(f"Error during cleanup for {location}: {e}")

        # Remove from dictionary
        with self.lock:
            if location in self.threads:
                del self.threads[location]
                self.logger.info(f"Removed thread for location: {location}")

        return True

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

    def stop_all_threads(self, object_counters: Optional[dict] = None, timeout: Optional[float] = None) -> dict[str, bool]:
        """
        Stops and removes all threads.
        
        Args:
            object_counters (Optional[dict]): Dictionary mapping location to ObjectCounter instances.
                                           If provided, will stop and cleanup each counter.
            timeout (Optional[float]): Timeout in seconds per thread. Defaults to self._shutdown_timeout.
        
        Returns:
            dict[str, bool]: Dictionary mapping location to success status
            
        Note:
            This method should be called when the application is shutting down.
            It will attempt to stop all threads gracefully.
        """
        if timeout is None:
            timeout = self._shutdown_timeout

        results: dict[str, bool] = {}

        # Get a copy of all locations to avoid modification during iteration
        with self.lock:
            locations = list(self.threads.keys())

        self.logger.info(f"Stopping {len(locations)} thread(s)...")

        for location in locations:
            object_counter = object_counters.get(location) if object_counters else None
            results[location] = self.stop_thread(location, object_counter, timeout)

        self.logger.info(f"Stopped all threads. Results: {sum(results.values())}/{len(results)} successful")
        return results

    def get_thread_count(self) -> int:
        """
        Returns the number of active threads.
        
        Returns:
            int: Number of active threads
        """
        with self.lock:
            return len(self.threads)

    def get_active_locations(self) -> list[str]:
        """
        Returns a list of all active location identifiers.
        
        Returns:
            list[str]: List of active location identifiers
        """
        with self.lock:
            return list(self.threads.keys())
