# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Aggregate FPS and inference latency sampled from the counting loop and sent to telemetry."""

from __future__ import annotations

import time

from system.core.counter_config import CounterSettings
from system.utils.telemetry import get_telemetry


class PerfReporter:
    """
    Accumulates per-frame timings and reports them as one telemetry event per window.

    A window closes when both the interval and a minimum frame count are reached, so a
    stalled stream stays silent; stopping a counter forces a report of whatever the last
    partial window collected, provided enough frames passed through it.
    """

    REPORT_INTERVAL: float = 300.0
    MIN_FRAMES: int = 20
    MIN_FORCED_FRAMES: int = 5

    def __init__(self, settings: CounterSettings) -> None:
        """
        Args:
            settings (CounterSettings): Live configuration; the model and backend labels
                are read when a window closes.
        """
        self.settings = settings
        self.frame_count: int = 0
        self.total_frame_time: float = 0.0
        self.total_inference_time: float = 0.0
        self._last_report_time: float = time.monotonic()

    def note_frame(self, frame_seconds: float, inference_seconds: float) -> None:
        """
        Add one processed frame to the current window and close the window if it is due.

        Args:
            frame_seconds (float): Wall time spent on the frame, excluding the wait for it.
            inference_seconds (float): Detector time for the same frame.

        Returns:
            None
        """
        self.frame_count += 1
        self.total_inference_time += inference_seconds
        self.total_frame_time += frame_seconds
        self.maybe_report()

    def maybe_report(self, force: bool = False) -> None:
        """
        Record and report aggregate FPS and inference performance metrics.

        Args:
            force: Force metric dispatch regardless of interval window.

        Returns:
            None
        """
        now = time.monotonic()
        elapsed = now - self._last_report_time
        if (elapsed >= self.REPORT_INTERVAL and self.frame_count >= self.MIN_FRAMES) or (
                force and self.frame_count >= self.MIN_FORCED_FRAMES):
            avg_fps = self.frame_count / max(0.001, elapsed)
            avg_inf_ms = (self.total_inference_time / max(1, self.frame_count)) * 1000.0
            avg_frame_ms = (self.total_frame_time / max(1, self.frame_count)) * 1000.0
            get_telemetry().track('stream_performance', {
                'location': self.settings.location,
                'model_type': str(self.settings.model_type),
                'backend': str(self.settings.backend),
                'fps': round(avg_fps, 1),
                'inference_ms': round(avg_inf_ms, 1),
                'frame_ms': round(avg_frame_ms, 1),
                'frames_count': self.frame_count,
            })
            self.frame_count = 0
            self.total_frame_time = 0.0
            self.total_inference_time = 0.0
            self._last_report_time = now
