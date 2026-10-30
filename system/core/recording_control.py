# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Async video recording driven by detection activity: start, push, idle stop."""

from __future__ import annotations

import time

import numpy as np

from system.core.counter_config import CounterSettings
from system.managers.video_recorder_manager import VideoRecorderManager
from system.utils.logger import Logger


class RecordingControl:
    """
    Owns the recorder of one counter and the activity clock that decides when to use it.

    Recording never starts on its own: the first frame with detections opens the file,
    and an idle timeout longer than the configured one closes it again. A recorder that
    cannot be created or started disables recording instead of failing the count.
    """

    def __init__(self, settings: CounterSettings, logger: Logger) -> None:
        """
        Args:
            settings (CounterSettings): Live configuration for path, fps, scale, quality
                and the idle timeout.
            logger (Logger): Where recorder failures are reported.
        """
        self.settings = settings
        self.logger = logger
        self.enabled: bool = settings.recording_enabled
        self._last_activity: float = 0.0
        self._recorder: VideoRecorderManager | None = None

    def init_recorder(self) -> None:
        """
        Initializing the asynchronous recorder for current recognition.

        Returns:
            None
        """
        if not self.enabled:
            return

        settings = self.settings
        try:
            self._recorder = VideoRecorderManager(
                location=settings.location,
                base_path=settings.recording_base_path,
                fps=settings.video_fps,
                scale=settings.recording_scale,
                quality=settings.recording_quality,
            )
        except Exception as e:
            # If it was not possible to initialize the record, log it and continue the operation of the counter without recording
            self.logger.error(f"Error initializing VideoRecorderManager: {e}")
            self.enabled = False

    def start_if_needed(self) -> None:
        """
        Start recording if it is enabled and not yet started.
        This method is safe to call multiple times.

        Returns:
            None
        """
        if not self.enabled or self._recorder is None:
            return
        try:
            self._recorder.start()
        except Exception as e:
            self.logger.error(f"Error starting VideoRecorderManager: {e}")
            self.enabled = False

    def stop(self) -> None:
        """
        Stop the current recording session and clear idle activity tracking.

        Returns:
            None
        """
        self._last_activity = 0.0
        if self._recorder is None:
            return
        try:
            self._recorder.stop()
        except Exception as e:
            self.logger.error(f"Error stopping VideoRecorderManager: {e}")

    def note_detection(self) -> None:
        """
        Mark detection activity and start recording when objects are present in the frame.

        Returns:
            None
        """
        if not self.enabled or self._recorder is None:
            return
        self._last_activity = time.monotonic()
        self.start_if_needed()

    def stop_if_idle(self) -> None:
        """
        Stop recording when no objects were detected for recording_idle_timeout seconds.
        When idle_timeout is 0 or less, recording continues until reset/stop.

        Returns:
            None
        """
        idle_timeout = self.settings.recording_idle_timeout
        if (
                not self.enabled
                or self._recorder is None
                or idle_timeout <= 0
                or not self._recorder.is_recording()
                or self._last_activity <= 0
        ):
            return

        if time.monotonic() - self._last_activity >= idle_timeout:
            self.stop()

    def push_frame(self, frame: np.ndarray) -> None:
        """
        Hand a frame to the recorder while an active session is running.

        Args:
            frame (numpy.ndarray): Frame to append to the recording.

        Returns:
            None
        """
        if not self.enabled or self._recorder is None or not self._recorder.is_recording():
            return
        self._recorder.push_frame(frame)
