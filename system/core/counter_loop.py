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
        self.frame_count: int = 0

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
                    with counter._lock:
                        self.cached_frame = frame

                    if counter.stream.watching:
                        proc_frame = self.process(frame)
                        counter.set_frame(proc_frame, copy=False)
                    else:
                        counter.set_frame(None, copy=False)
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
            with counter._lock:
                last_total_count = counter.counts.total_count
                current_generation = counter._generation

            work_frame = self.work_frame(frame)
            inf_start = time.monotonic()
            boxes = self.detect(work_frame, generation=current_generation)
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

            display_frame = self.count_and_draw(display_frame, boxes, generation=current_generation)

            with counter._lock:
                current_total_count = counter.counts.total_count
            if dataset_enabled and last_total_count != current_total_count:
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

    def detect(self, image: np.ndarray, generation: int | None = None) -> np.ndarray:
        """
        Detects objects in an image using a pre-trained model.

        Args:
            image (ndarray): The input image as a numpy array.
            generation (int, optional): Generation counter captured before inference.
                                        If counter was reset while detect() was running,
                                        the stale detections are NOT passed to tracker.update().

        Returns:
            ndarray: An array of updated results after tracking the detected objects.
                     Each row has the following structure:
                     [x1, y1, x2, y2, track_id, (optional) class_id]
        """
        counter = self.counter
        if counter.model is None or counter.preview_mode:
            with counter._lock:
                if generation is not None and generation != counter._generation:
                    return np.empty((0, 6), dtype=np.float32)
                return counter.tracker.update(np.empty((0, 6), dtype=np.float32))

        res = counter.model.detect(image=image)
        if hasattr(res, 'to_tracker_array'):
            detections_array = res.to_tracker_array()
        elif hasattr(res, 'to_legacy'):
            xyxy, conf, cls = res.to_legacy()
            if xyxy is None or len(xyxy) == 0:
                with counter._lock:
                    if generation is not None and generation != counter._generation:
                        return np.empty((0, 6), dtype=np.float32)
                    return counter.tracker.update(np.empty((0, 6), dtype=np.float32))
            detections_array = np.empty((len(xyxy), 6), dtype=np.float32)
            detections_array[:, :4] = xyxy
            detections_array[:, 4] = conf
            detections_array[:, 5] = cls
        else:
            xyxy, conf, cls = res
            if xyxy is None or len(xyxy) == 0:
                with counter._lock:
                    if generation is not None and generation != counter._generation:
                        return np.empty((0, 6), dtype=np.float32)
                    return counter.tracker.update(np.empty((0, 6), dtype=np.float32))
            detections_array = np.empty((len(xyxy), 6), dtype=np.float32)
            detections_array[:, :4] = xyxy
            detections_array[:, 4] = conf
            detections_array[:, 5] = cls

        with counter._lock:
            if generation is not None and generation != counter._generation:
                return np.empty((0, 6), dtype=np.float32)
            return counter.tracker.update(detections_array)

    @staticmethod
    def _evict_inactive_queue(counter: ObjectCounter, active_rids: set[int]) -> None:
        """
        Bounded queue eviction protecting active objects in frame and debounce window.
        """
        excess = len(counter._total_objects_queue) - counter._max_tracked_history
        if excess > 0:
            for _ in range(len(counter._total_objects_queue)):
                if len(counter._total_objects_queue) <= counter._max_tracked_history:
                    break
                old_id = counter._total_objects_queue.popleft()
                if old_id not in active_rids and old_id not in counter._counted_tracks:
                    counter.total_objects.discard(old_id)
                else:
                    counter._total_objects_queue.append(old_id)

    @staticmethod
    def _extract_motion_state(history: deque | None) -> tuple[bool, tuple[float, float]]:
        """
        Extract motion state from track history.

        Returns:
            (is_moving, (norm_dx, norm_dy)): True if displacement >= 10.0 px, and normalized unit direction vector.
        """
        if not history or len(history) < 2:
            return False, (0.0, 0.0)
        start_x, start_y = history[0]
        end_x, end_y = history[-1]
        dx = float(end_x - start_x)
        dy = float(end_y - start_y)
        dist = (dx * dx + dy * dy) ** 0.5
        if dist >= 10.0:
            return True, (dx / dist, dy / dist)
        return False, (0.0, 0.0)

    @staticmethod
    def _compute_spatial_similarity(
            box1: tuple[int, int, int, int],
            center1: tuple[int, int],
            box2: tuple[int, int, int, int],
            center2: tuple[int, int],
            is_moving: bool = False,
            motion_vec: tuple[float, float] = (0.0, 0.0),
            dt: int = 0,
            max_moving_dt: int = 10,
    ) -> float:
        """
        Compute spatial similarity score between a newly observed track and a
        previously counted track to detect track re-identification and prevent
        double counting across track dropouts / ID switches.

        Prevents false-merging of sequential objects (e.g. cars following in a lane,
        conveyor items) by rejecting upstream followers and age-exceeded moving tracks.

        Returns:
            float: Score in range [0.0, 1.0], where > 0.0 indicates a spatial match.
        """
        # If the old object was actively moving and elapsed frames exceed the physical
        # movement window (~0.35s), it has already moved on; any new detection is a follower / new object.
        if is_moving and dt > max_moving_dt:
            return 0.0

        cx1, cy1 = center1
        cx2, cy2 = center2
        dx = float(cx1 - cx2)
        dy = float(cy1 - cy2)

        # Upstream follower rejection: if old object was moving, a new object
        # appearing behind it along its trajectory is a follower, NOT the same object!
        if is_moving and (motion_vec[0] != 0.0 or motion_vec[1] != 0.0):
            proj = dx * motion_vec[0] + dy * motion_vec[1]
            if proj < -15.0:
                return 0.0

        # Compute Bounding Box IoU
        ix1 = max(box1[0], box2[0])
        iy1 = max(box1[1], box2[1])
        ix2 = min(box1[2], box2[2])
        iy2 = min(box1[3], box2[3])
        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        inter = iw * ih
        if inter > 0:
            area1 = max(1, (box1[2] - box1[0]) * (box1[3] - box1[1]))
            area2 = max(1, (box2[2] - box2[0]) * (box2[3] - box2[1]))
            union = area1 + area2 - inter
            iou = float(inter) / float(max(1, union))
            if iou >= 0.35:
                return iou

        # Stationary object jitter check
        if not is_moving:
            dist = (dx * dx + dy * dy) ** 0.5
            if dist <= 15.0:
                return 0.30
            in_box2 = (box2[0] <= cx1 <= box2[2]) and (box2[1] <= cy1 <= box2[3])
            in_box1 = (box1[0] <= cx2 <= box1[2]) and (box1[1] <= cy2 <= box1[3])
            if (in_box2 or in_box1) and dist <= 25.0:
                return 0.25

        return 0.0

    def count_and_draw(
            self,
            image: np.ndarray,
            boxes: list | np.ndarray,
            generation: int | None = None,
    ) -> np.ndarray:
        """
        Counts objects in the given image and draws indicators on the image.

        Args:
            image (numpy.ndarray): The image on which the boxes will be drawn.
            boxes (List[Tuple[int]] | numpy.ndarray): A list of boxes, where each box is represented by a tuple of (x1, y1, x2, y2, rid),
                                      where x1, y1 are the top-left coordinates, x2, y2 are the bottom-right coordinates,
                                      and rid is the ID of the box.
            generation (int, optional): Generation counter at detection time. If counter was reset
                                        while detect() was running, stale boxes are discarded.

        Returns:
            numpy.ndarray: The modified image with the boxes drawn on it.
        """
        counter = self.counter
        with counter._lock:
            if counter.paused:
                return image

            if generation is not None and generation != counter._generation:
                # Counter was reset between detection and count_and_draw.
                # Discard stale detections to prevent ghost counts immediately after reset.
                return image

            self.frame_count += 1

            # Compute effective FPS for physically consistent temporal windows
            effective_fps = 30.0
            if getattr(counter, 'video_fps', None) and counter.video_fps > 0:
                effective_fps = float(counter.video_fps)
            elif hasattr(counter, 'vsm') and counter.vsm:
                try:
                    actual_fps = counter.vsm.get_actual_fps()
                    if actual_fps is not None and float(actual_fps) > 0 and not np.isnan(float(actual_fps)):
                        effective_fps = float(actual_fps)
                except (TypeError, ValueError):
                    pass
            effective_fps = max(5.0, min(60.0, effective_fps))

            # The debounce window represents the upper envelope of:
            # 1) Physical retention window (approx 1.5s of video time: effective_fps * 1.5);
            # 2) Tracker's internal retention lifetime (tracker_max_age);
            # 3) Minimum floor of 15 frames.
            debounce_window = max(int(effective_fps * 1.5), int(getattr(counter, 'tracker_max_age', 30)), 15)
            # Physical moving object dropout window (~0.35s in frames, e.g. 4 frames at 10fps, 11 frames at 30fps)
            max_moving_dt = max(2, int(round(effective_fps * 0.35)))

            if boxes is None or len(boxes) == 0:
                if counter._counted_tracks:
                    counter._counted_tracks = {
                        k: v for k, v in counter._counted_tracks.items()
                        if self.frame_count - v['last_frame'] <= debounce_window
                    }
                if len(counter._track_history) > 100:
                    counter._track_history = {
                        k: v for k, v in counter._track_history.items()
                        if k in counter._counted_tracks
                    }
                self._evict_inactive_queue(counter, set())
                return image

            # Ensure mask for fast point-in-polygon
            h, w = image.shape[:2]
            counter.renderer.ensure_mask((h, w))
            counting_mask = counter.renderer.mask
            counting_areas = counter.settings.counting_areas

            active_rids = {int(b[4]) for b in boxes} if boxes is not None and len(boxes) > 0 else set()

            for result in boxes:
                values = list(map(int, result[:6]))
                x1, y1, x2, y2, rid = values[:5]
                class_id = values[5] if len(values) > 5 else -1
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                # Track trajectory history for motion direction validation
                if rid not in counter._track_history:
                    counter._track_history[rid] = deque(maxlen=counter._max_track_history_len)
                counter._track_history[rid].append((cx, cy))

                # Update spatial state for already-counted tracks
                if rid in counter.total_objects:
                    is_moving, motion_vec = self._extract_motion_state(counter._track_history.get(rid))
                    counter._counted_tracks[rid] = {
                        'last_bbox': (x1, y1, x2, y2),
                        'last_center': (cx, cy),
                        'last_frame': self.frame_count,
                        'class_id': class_id,
                        'is_moving': is_moving,
                        'motion_vec': motion_vec,
                    }
                else:
                    # Candidate new track: check if it matches an already-counted object
                    # that experienced a tracker dropout / ID switch.
                    best_match_id = None
                    best_score = 0.0
                    for cid, cinfo in list(counter._counted_tracks.items()):
                        if cid in active_rids:
                            continue
                        dt = self.frame_count - cinfo['last_frame']
                        if dt > debounce_window:
                            continue
                        if class_id >= 0 and cinfo['class_id'] >= 0 and class_id != cinfo['class_id']:
                            continue
                        score = self._compute_spatial_similarity(
                            (x1, y1, x2, y2), (cx, cy),
                            cinfo['last_bbox'], cinfo['last_center'],
                            is_moving=cinfo.get('is_moving', False),
                            motion_vec=cinfo.get('motion_vec', (0.0, 0.0)),
                            dt=dt,
                            max_moving_dt=max_moving_dt,
                        )
                        if score > 0.0 and score > best_score:
                            best_score = score
                            best_match_id = cid

                    if best_match_id is not None:
                        # Re-identified as an already-counted object!
                        counter.total_objects.add(rid)
                        counter._total_objects_queue.append(rid)
                        # Inherit trajectory history only if physically contiguous (no teleportation)
                        if best_match_id in counter._track_history and len(counter._track_history[rid]) <= 1:
                            prior = list(counter._track_history[best_match_id])
                            if prior:
                                last_px, last_py = prior[-1]
                                dist_jump = ((cx - last_px) ** 2 + (cy - last_py) ** 2) ** 0.5
                                max_jump = max(x2 - x1, y2 - y1, 50) * 1.5
                                if dist_jump <= max_jump:
                                    if (cx, cy) not in prior:
                                        prior.append((cx, cy))
                                    counter._track_history[rid] = deque(prior, maxlen=counter._max_track_history_len)

                        is_moving, motion_vec = self._extract_motion_state(counter._track_history.get(rid))
                        counter._counted_tracks[rid] = {
                            'last_bbox': (x1, y1, x2, y2),
                            'last_center': (cx, cy),
                            'last_frame': self.frame_count,
                            'class_id': class_id,
                            'is_moving': is_moving,
                            'motion_vec': motion_vec,
                        }
                        if best_match_id != rid:
                            counter._counted_tracks.pop(best_match_id, None)

                # Draw indicator on the image (reflects live counted status)
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
                            is_moving, motion_vec = self._extract_motion_state(counter._track_history.get(rid))
                            counter._counted_tracks[rid] = {
                                'last_bbox': (x1, y1, x2, y2),
                                'last_center': (cx, cy),
                                'last_frame': self.frame_count,
                                'class_id': class_id,
                                'is_moving': is_moving,
                                'motion_vec': motion_vec,
                            }

            # Periodic pruning of expired debounce records
            counter._counted_tracks = {
                k: v for k, v in counter._counted_tracks.items()
                if self.frame_count - v['last_frame'] <= debounce_window
            }

            # Clean trajectory history for dead objects to avoid memory bloat
            if len(counter._track_history) > 100:
                counter._track_history = {
                    k: v for k, v in counter._track_history.items()
                    if k in active_rids or k in counter._counted_tracks
                }

            # Bounded queue eviction protecting active objects in frame and debounce window
            self._evict_inactive_queue(counter, active_rids)

        counter.emit_live_counts()

        return image
