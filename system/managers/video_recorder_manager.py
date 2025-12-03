# -*- coding: utf-8 -*-
# ! python3
# Developed by: Aleksandr Kireev
# Created: 03.12.2025
# Updated: 03.12.2025
# Website: https://bespredel.name

import os
import re
import time
from queue import Queue, Full, Empty
from threading import Thread, Event
from typing import Optional
from datetime import datetime

import cv2
import numpy as np

from system.utils.logger import Logger


class VideoRecorderManager:
    """
    Asynchronous video recording manager so as not to block the counting thread.

    Using:
        recorder = VideoRecorderManager(location="location_1", base_path="yolo_cfg/saved_recordings")
        recorder.start()
        recorder.push_frame(frame)  # in the work cycle
        ...
        recorder.stop()  # on completion/reset
    """

    DEFAULT_RECORDING_PATH: str = "yolo_cfg/saved_recordings"
    DEFAULT_FPS: float = 25.0
    DEFAULT_QUEUE_SIZE: int = 100

    def __init__(
            self,
            location: str,
            base_path: Optional[str] = None,
            fps: float = 0,
            scale: int = 100,
            quality: int = 80,
    ) -> None:
        self.location: str = location
        self.base_path: str = base_path or self.DEFAULT_RECORDING_PATH
        self.requested_fps: float = fps if fps and fps > 0 else 0
        self.scale_percent: int = max(1, int(scale)) if scale and scale > 0 else 100
        self.quality: int = max(1, min(int(quality), 100)) if quality else 80

        self._logger: Logger = Logger()
        self._queue: "Queue[np.ndarray]" = Queue(maxsize=self.DEFAULT_QUEUE_SIZE)
        self._thread: Optional[Thread] = None
        self._stop_event: Event = Event()

        self._writer: Optional[cv2.VideoWriter] = None
        self._file_path: Optional[str] = None
        self._frame_size: Optional[tuple[int, int]] = None
        self._fps: float = self.DEFAULT_FPS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Start a background recording thread.
        """
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """
        Stop recording and save the current file.
        """
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

        # Freeing up resources
        self._release_writer()

    def push_frame(self, frame: np.ndarray) -> None:
        """
        Non-blocking sending of a frame to the queue.
        If the queue is full, the frame is quietly discarded so as not to slow down the counting.
        """
        if frame is None:
            return
        try:
            self._queue.put_nowait(frame)
        except Full:
            # The queue is full - we skip the frame, do not block the counting flow
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """
        The main loop of the background write thread.
        """
        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                frame = self._queue.get(timeout=0.1)
            except Empty:
                continue

            if frame is None:
                continue

            try:
                frame_to_write = self._prepare_frame(frame)

                self._ensure_writer(frame_to_write)
                if self._writer is not None:
                    self._writer.write(frame_to_write)
            except Exception as e:
                self._logger.error(f"Error writing frame in VideoRecorderManager: {e}")

    def _prepare_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Preparing a frame for recording (changing the resolution by scale).
        """
        if frame is None:
            return frame

        if self.scale_percent and self.scale_percent != 100:
            try:
                height, width = frame.shape[:2]
                new_width = int(width * self.scale_percent / 100)
                new_height = int(height * self.scale_percent / 100)
                if new_width > 0 and new_height > 0:
                    frame = cv2.resize(frame, (new_width, new_height))
            except Exception as e:
                self._logger.error(f"Error resizing frame in VideoRecorderManager: {e}")

        return frame

    def _ensure_writer(self, frame: np.ndarray) -> None:
        """
        Initialize VideoWriter on the first frame.
        """
        if self._writer is not None:
            return

        try:
            height, width = frame.shape[:2]
            self._frame_size = (width, height)

            fps = self.requested_fps or self.DEFAULT_FPS
            self._fps = float(fps) if fps > 0 else self.DEFAULT_FPS

            directory = self._ensure_recording_dir()
            timestamp = int(time.time())
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            safe_location = re.sub('[^A-Za-z0-9-_]+', '', self.location)
            filename = f"{safe_location}_{timestamp}.mp4"
            file_path = os.path.join(directory, filename)

            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(file_path, fourcc, self._fps, self._frame_size)

            if not writer.isOpened():
                self._logger.error(f"Failed to open VideoWriter for {file_path}")
                return

            self._writer = writer
            self._file_path = file_path
        except Exception as e:
            self._logger.error(f"Error creating VideoWriter: {e}")

    def _ensure_recording_dir(self) -> str:
        base_dir = self.base_path or self.DEFAULT_RECORDING_PATH
        safe_location = re.sub('[^A-Za-z0-9-_]+', '', self.location)
        full_dir = os.path.join(base_dir, safe_location)
        os.makedirs(full_dir, exist_ok=True)
        return full_dir

    def _release_writer(self) -> None:
        if self._writer is not None:
            try:
                self._writer.release()
            except Exception as e:
                self._logger.error(f"Error releasing VideoWriter: {e}")
            finally:
                self._writer = None
                self._file_path = None
