# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""The counting loop: pull a frame, detect, track, count, draw overlays, encode."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import numpy as np

from system.core.timer import Timer
from system.utils.i18n import trans
from system.utils.telemetry import get_telemetry

if TYPE_CHECKING:
    from system.core.object_counter import ObjectCounter


class CounterLoop:
    """
    Drives one counter from the camera frame to the encoded preview.

    The loop owns only what belongs to iterating: the sleep timings and the inference
    latency shown on the FPS overlay. Everything else — settings, model, tracker and the
    renderer/stream/recorder/capture collaborators — is read from the counter on each
    frame, so a zone change or a restart is picked up without touching this class.
    """

    DEFAULT_SLEEP_TIME: float = 0.01
    DEFAULT_PAUSED_SLEEP_TIME: float = 0.1

    def __init__(self, counter: ObjectCounter) -> None:
        """
        Args:
            counter (ObjectCounter): The counter whose source, model and collaborators
                this loop drives.
        """
        self.counter = counter

        # Smoothed inference latency shown by the FPS overlay
        self.hud_inference_ms: float = 0.0

    def run(self) -> None:
        """
        Run the generation of frames.

        Returns:
            None
        """
        counter = self.counter
        status_evt = 'collection' if counter.preview_mode else 'started'
        counter.events.status(status_evt)

        while counter.running:
            try:
                reconnect_count = counter.vsm.get_reconnect_count()
                iter_started = time.monotonic()
                frame = counter.vsm.get_frame()
                if frame is None:
                    if counter.vsm.reconnect_limit_reached():
                        counter.logger.error(
                            f"Camera connection failed after {counter.video_reconnect_attempts} attempts | {counter.location}"
                        )
                        get_telemetry().track('stream_lost',
                                              {'location': counter.location, 'reason': 'reconnect_limit'})
                        counter.events.notify(trans('Lost connection to camera!'), 'danger')
                        counter.events.status('error')
                        counter.stop()
                        break

                    get_telemetry().track('stream_lost', {'location': counter.location, 'reason': 'frame_none'})
                    counter.events.notify(trans('Lost connection to camera!'), 'danger')
                    counter.events.status('error')
                    time.sleep(self.DEFAULT_SLEEP_TIME)
                    continue  # Skip the iteration if the frame is not received

                if reconnect_count > 0:
                    counter.vsm.reset_reconnect_count()
                    get_telemetry().track('stream_reconnected', {'location': counter.location})
                    counter.events.notify(trans('Connection to camera restored!'), 'success')
                    counter.events.status('started')

                # The grabber keeps one buffer and replaces it only when a new
                # camera frame arrives. Re-running inference and JPEG on that same
                # object freezes the picture and starves the decoder.
                if frame is counter._cached_source_frame:
                    sleep_time = 0.005
                else:
                    counter._cached_source_frame = frame

                    if counter.stream.watching:
                        counter.frame = self.process(frame)
                    else:
                        counter.frame = None
                        self.process(frame)

                    # Live RTSP already returns the newest frame, so a fixed pause is
                    # unnecessary while a viewer is connected: JPEG encode keeps the
                    # loop near the output rate. With no viewer that encode is skipped
                    # and inference would run as fast as the GPU allows.
                    if counter.paused:
                        sleep_time = self.DEFAULT_PAUSED_SLEEP_TIME
                    elif counter.vsm.is_stream() and not counter.vsm.is_hls() and counter.video_fps <= 0:
                        if counter.stream.watching:
                            sleep_time = 0.0
                        else:
                            spent = time.monotonic() - iter_started
                            sleep_time = counter.stream.encode_interval() - spent
                            if sleep_time < 0.0:
                                sleep_time = 0.0
                    else:
                        sleep_time = self.DEFAULT_SLEEP_TIME
                if sleep_time > 0:
                    time.sleep(sleep_time)
            except Exception as e:
                counter.logger.error(f"Error processing frame | {counter.location}: {e}")
                counter.logger.log_exception()
                get_telemetry().track('stream_lost',
                                      {'location': counter.location, 'reason': 'exception', 'error': str(e)})
                counter.events.notify(trans(f"Counter processing error: {e}"), 'danger')
                counter.events.status('error')
                time.sleep(self.DEFAULT_PAUSED_SLEEP_TIME)

    def process(self, frame: np.ndarray) -> np.ndarray | None:
        """
        Process the frame.

        Args:
            frame (numpy.ndarray): The frame to process.

        Returns:
            numpy.ndarray: The processed frame.
        """
        if frame is None:
            return None

        counter = self.counter
        with Timer() as timer:
            if counter.paused:
                display_frame = counter._work_frame(frame)
                if counter.stream.watching:
                    display_frame = counter.renderer.draw_zones(display_frame)
                    counter.renderer.draw_fps_hud(
                        display_frame, counter.stream.out_fps, self.hud_inference_ms)
                    counter.stream.maybe_encode(display_frame)
                return display_frame

            dataset_enabled = counter.capture.dataset_enabled
            last_total_count = counter.counts.total_count

            work_frame = counter._work_frame(frame)
            inf_start = time.monotonic()
            boxes = counter._detect(work_frame)
            inf_duration = time.monotonic() - inf_start
            inf_ms = inf_duration * 1000.0
            self.hud_inference_ms = (
                inf_ms if self.hud_inference_ms <= 0 else (self.hud_inference_ms * 0.8 + inf_ms * 0.2)
            )

            if boxes is not None and len(boxes) > 0:
                counter.rec.note_detection()

            if counter.stream.watching:
                area_source = work_frame.copy() if dataset_enabled else work_frame
                display_frame = counter.renderer.draw_zones(area_source)
            else:
                display_frame = work_frame.copy() if dataset_enabled else work_frame

            display_frame = counter._detect_count(display_frame, boxes)

            if dataset_enabled and last_total_count != counter.counts.total_count:
                counter.capture.save_sample(work_frame, boxes)

            # Periodic interval capture
            counter.capture.maybe_capture_interval(work_frame)

            if counter.settings.show_fps:
                counter.renderer.draw_fps_hud(display_frame, counter.stream.out_fps, self.hud_inference_ms)
            elif counter.debug and timer.elapsed > 0:
                counter.renderer.draw_debug_fps(display_frame, int(round(1 / timer.elapsed)))

            # Sending a frame to an asynchronous recorder while an active session is running
            counter.rec.push_frame(display_frame)

            counter.rec.stop_if_idle()

            # Record performance metrics
            counter.perf.note_frame(timer.elapsed, inf_duration)

            if counter.stream.watching:
                counter.stream.maybe_encode(display_frame)

            return display_frame
