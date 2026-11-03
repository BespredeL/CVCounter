# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""The counting loop: pull a frame, detect, track, count, draw overlays, encode."""

from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING

import numpy as np

from system.core.count_kernel import direction_matches
from system.core.timer import Timer
from system.utils.i18n import trans
from system.utils.telemetry import get_telemetry

if TYPE_CHECKING:
    from system.core.object_counter import ObjectCounter


class CounterLoop:
    """
    Drives one counter from the camera frame to the encoded preview.

    The loop owns the iteration: pulling frames, the sleep timings, the inference latency
    shown on the FPS overlay and the pipeline stages between them. Settings, model,
    tracker and the renderer/stream/recorder/capture collaborators are read from the
    counter on each frame, so a zone change or a restart is picked up here.
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

        # The last frame taken from the source: the identity marker of the dedupe below
        # and the raw frame readers get through ObjectCounter.cached_source_frame().
        self.cached_frame: np.ndarray | None = None

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
                if frame is self.cached_frame:
                    sleep_time = 0.005
                else:
                    self.cached_frame = frame

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
                display_frame = self.work_frame(frame)
                if counter.stream.watching:
                    display_frame = counter.renderer.draw_zones(display_frame)
                    counter.renderer.draw_fps_hud(
                        display_frame, counter.stream.out_fps, self.hud_inference_ms)
                    counter.stream.maybe_encode(display_frame)
                return display_frame

            dataset_enabled = counter.capture.dataset_enabled
            last_total_count = counter.counts.total_count

            work_frame = self.work_frame(frame)
            inf_start = time.monotonic()
            boxes = self.detect(work_frame)
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

            display_frame = self.count_and_draw(display_frame, boxes)

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

    def work_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        One owned contiguous frame per iteration (safe for async recorder/encode).

        Args:
            frame (numpy.ndarray): The frame to process.

        Returns:
            numpy.ndarray: The processed frame.
        """
        return np.ascontiguousarray(frame).copy()

    def detect(self, image: np.ndarray) -> np.ndarray:
        """
        Detects objects in an image using a pre-trained model.

        Args:
            image (ndarray): The input image as a numpy array.

        Returns:
            ndarray: An array of updated results after tracking the detected objects.
                     Each row has the following structure:
                     [x1, y1, x2, y2, track_id, (optional) class_id]
        """
        counter = self.counter
        if counter.model is None or counter.preview_mode:
            return counter.tracker.update(np.empty((0, 6)))

        res = counter.model.detect(image=image)
        if hasattr(res, 'to_tracker_array'):
            detections_array = res.to_tracker_array()
        elif hasattr(res, 'to_legacy'):
            xyxy, conf, cls = res.to_legacy()
            if xyxy is None or len(xyxy) == 0:
                return counter.tracker.update(np.empty((0, 6), dtype=np.float32))
            detections_array = np.empty((len(xyxy), 6), dtype=np.float32)
            detections_array[:, :4] = xyxy
            detections_array[:, 4] = conf
            detections_array[:, 5] = cls
        else:
            xyxy, conf, cls = res
            if xyxy is None or len(xyxy) == 0:
                return counter.tracker.update(np.empty((0, 6), dtype=np.float32))
            detections_array = np.empty((len(xyxy), 6), dtype=np.float32)
            detections_array[:, :4] = xyxy
            detections_array[:, 4] = conf
            detections_array[:, 5] = cls

        return counter.tracker.update(detections_array)

    def count_and_draw(self, image: np.ndarray, boxes: list | np.ndarray) -> np.ndarray:
        """
        Counts objects in the given image and draws indicators on the image.

        Args:
            image (numpy.ndarray): The image on which the boxes will be drawn.
            boxes (List[Tuple[int]] | numpy.ndarray): A list of boxes, where each box is represented by a tuple of (x1, y1, x2, y2, rid),
                                      where x1, y1 are the top-left coordinates, x2, y2 are the bottom-right coordinates,
                                      and rid is the ID of the box.

        Returns:
            numpy.ndarray: The modified image with the boxes drawn on it.
        """
        counter = self.counter
        if counter.paused:
            return image

        # Ensure mask for fast point-in-polygon
        if boxes is not None and len(boxes) > 0:
            h, w = image.shape[:2]
            counter.renderer.ensure_mask((h, w))
        counting_mask = counter.renderer.mask
        counting_areas = counter.settings.counting_areas

        for result in boxes:
            values = list(map(int, result[:6]))
            x1, y1, x2, y2, rid = values[:5]
            class_id = values[5] if len(values) > 5 else -1
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            # Track trajectory history for motion direction validation
            if rid not in counter._track_history:
                counter._track_history[rid] = deque(maxlen=counter._max_track_history_len)
            counter._track_history[rid].append((cx, cy))

            # Draw indicator on the image
            counter.renderer.draw_indicator(
                image, (cx, cy), rid,
                counted=rid in counter.total_objects,
                box=(x1, y1, x2, y2),
                class_id=class_id,
            )

            # Check if the object is within the counting area using mask
            if (
                    counting_mask is not None
                    and 0 <= cy < counting_mask.shape[0]
                    and 0 <= cx < counting_mask.shape[1]
                    and rid not in counter.total_objects
            ):
                zone_code = int(counting_mask[cy, cx])
                if zone_code > 0:
                    zone_idx = zone_code - 1
                    zone = counting_areas[zone_idx] if zone_idx < len(counting_areas) else None
                    direction = zone.get('direction', 'any') if zone else 'any'

                    is_valid_direction = direction_matches(
                        (cx, cy), counter._track_history[rid], direction
                    )

                    if is_valid_direction:
                        counter.total_objects.add(rid)
                        counter._total_objects_queue.append(rid)
                        counter.counts.total_count += 1
                        counter.counts.current_count += 1
                        counter.counts.increment_class_count(class_id)
                        if len(counter._total_objects_queue) > counter._max_tracked_history:
                            old_id = counter._total_objects_queue.popleft()
                            counter.total_objects.discard(old_id)

        if len(counter._track_history) > 1000:
            active_rids = {int(b[4]) for b in boxes} if boxes is not None and len(boxes) > 0 else set()
            counter._track_history = {
                k: v for k, v in counter._track_history.items()
                if k in active_rids or k in counter.total_objects
            }

        counter.emit_live_counts()

        return image
