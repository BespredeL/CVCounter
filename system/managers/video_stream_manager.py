# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.03.2024
# Updated: 25.06.2026
# Website: https://bespredel.name

import os
import threading
import time
from collections import deque

import cv2
from imutils.video import VideoStream

from system.utils.exception_handler import StreamConnectionError, StreamSourceError
from system.utils.logger import Logger


class _HlsFrameGrabber:
    """Read a live HLS playlist ahead of playback and release frames at the stream rate.

    The playlist starts with several ready segments. Reading them as fast as they
    decode dumps that buffer at once, then the next read waits for a new segment.
    """

    def __init__(
            self,
            capture: cv2.VideoCapture,
            frame: cv2.Mat | None,
            open_capture,
            fps: float,
    ) -> None:
        self._cap: cv2.VideoCapture | None = capture
        self._open_capture = open_capture
        self.frame = frame
        self.stopped: bool = False
        if fps < 1 or fps > 120:
            fps = 25.0
        self._fps = fps
        self._interval = 1.0 / fps
        self._next_emit = 0.0
        self._queue: deque = deque()
        self._max_queue = max(15, min(60, int(fps * 2)))
        self._space = threading.Condition()
        self._thread = threading.Thread(target=self._update, name="hls-grab", daemon=True)
        self._thread.start()

    def _update(self) -> None:
        empty_run = 0
        while not self.stopped:
            cap = self._cap
            if cap is None:
                time.sleep(0.2)
                self._reopen()
                continue
            try:
                grabbed, frame = cap.read()
            except Exception:
                grabbed, frame = False, None
            if self.stopped:
                return
            if grabbed and frame is not None:
                with self._space:
                    while not self.stopped and len(self._queue) >= self._max_queue:
                        self._space.wait(0.05)
                    if self.stopped:
                        return
                    self._queue.append(frame)
                empty_run = 0
                continue
            empty_run += 1
            self._reopen()
            if empty_run >= 3:
                time.sleep(1.0)

    def _reopen(self) -> None:
        old = self._cap
        self._cap = None
        if old is not None:
            try:
                old.release()
            except Exception:
                pass
        if self.stopped:
            return
        cap = None
        try:
            cap = self._open_capture()
        except Exception:
            cap = None
        opened = cap is not None and cap.isOpened()
        if not opened:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            return
        self._cap = cap

    def read(self):
        now = time.monotonic()
        with self._space:
            if self._queue and now >= self._next_emit:
                self.frame = self._queue.popleft()
                self._next_emit = now + self._interval
                self._space.notify()
        return self.frame

    def isOpened(self) -> bool:
        cap = self._cap
        return cap is not None and cap.isOpened()

    def release(self) -> None:
        self.stopped = True
        with self._space:
            self._space.notify_all()
        cap = self._cap
        self._cap = None
        if cap is not None:
            cap.release()

    def stop(self) -> None:
        self.release()


class VideoStreamManager:
    DEFAULT_MAX_RECONNECT_ATTEMPTS: int = 10
    DEFAULT_RECONNECT_DELAY_SEC: float = 1.0
    _HLS_FFMPEG_OPTIONS: str = 'reconnect;1|reconnect_streamed;1|reconnect_delay_max;5'
    _HLS_OPEN_TIMEOUT_MSEC: int = 15000
    # read() blocks 0.5–1.2s inside FFmpeg while the next call starts within 1ms.
    # HTTPS source: do not force rtsp_transport or a 1-frame queue (that combo stalled longer).
    _LIVE_FFMPEG_OPTIONS: str = 'fflags;nobuffer|flags;low_delay|max_delay;0'
    _HLS_WARMUP_TIMEOUT_SEC: float = 15.0
    _HLS_READ_RETRIES: int = 5
    _HLS_READ_RETRY_DELAY_SEC: float = 0.2

    def __init__(
            self,
            video_stream: str,
            video_fps: float,
            max_reconnect_attempts: int | None = None,
    ) -> None:
        # Init logger
        self.__logger: Logger = Logger()

        if not video_stream:
            self.__logger.error("A video stream source is required")
            raise StreamSourceError("A video stream source is required")

        self.__video_stream: str = video_stream
        self.__is_hls: bool = self._detect_hls(video_stream)
        self.__cap: cv2.VideoCapture | VideoStream = None
        self.__fps: float = video_fps  # Default FPS
        self.__actual_fps: float = 0  # Calculated FPS based on frame intervals
        self.__last_frame_time: float = time.monotonic()
        self.__fps_frame = None
        self.__fps_count: int = 0
        self.__frame_interval: float = 1 / self.__fps if video_fps > 0 else 0
        self.__reconnect_count: int = 0
        self.__max_reconnect_attempts: int = max(
            1,
            int(max_reconnect_attempts or self.DEFAULT_MAX_RECONNECT_ATTEMPTS),
        )

    @property
    def video_stream(self) -> str:
        """
        Get the video stream source.

        Returns:
            str: The video stream source
        """
        return self.__video_stream

    @property
    def cap(self) -> cv2.VideoCapture:
        """
        Get the video capture object.

        Returns:
            cv2.VideoCapture: The video capture object
        """
        return self.__cap

    def connect(self) -> bool:
        """
        Open the video stream once.

        Returns:
            bool: True when the capture is ready, False on failure.
        """
        if self.reconnect_limit_reached():
            return False

        try:
            self.start()
            if self._capture_is_ready():
                return True
            self.__logger.error(f"Capture opened but is not ready: {self.__video_stream}")
        except Exception as e:
            self.__logger.error(f"Connection attempt failed: {e}")

        self._release_capture()
        self.__reconnect_count += 1
        if self.reconnect_limit_reached():
            self.__logger.error(
                f"Video stream connection limit reached ({self.__max_reconnect_attempts}): {self.__video_stream}"
            )
        return False

    def connect_with_retries(self, delay_sec: float | None = None) -> bool:
        """
        Try to open the stream within the configured attempt budget.

        Args:
            delay_sec: Pause between failed attempts.

        Returns:
            bool: True when connected.
        """
        pause = self.DEFAULT_RECONNECT_DELAY_SEC if delay_sec is None else delay_sec
        while not self.reconnect_limit_reached():
            if self.connect():
                return True
            if not self.reconnect_limit_reached():
                time.sleep(pause)
        return False

    def reconnect_limit_reached(self) -> bool:
        """Whether the configured connection attempt limit has been exhausted."""
        return self.__reconnect_count >= self.__max_reconnect_attempts

    def start(self) -> None:
        """
        Starts the video stream.

        Returns:
            None
        """
        try:
            if self.is_hls():
                self._release_capture()
                capture = self._open_hls_capture()
                if not capture.isOpened():
                    self.__logger.error(f"Cannot open HLS stream: {self.__video_stream}")
                    raise StreamConnectionError(f"Cannot open video stream: {self.__video_stream}")
                self.__cap = capture
                first_frame = self._warmup_hls_capture()
                try:
                    source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
                except (TypeError, ValueError):
                    source_fps = 0.0
                self.__cap = _HlsFrameGrabber(capture, first_frame, self._open_hls_capture, source_fps)
            elif self.is_stream():
                if self.__cap is not None:
                    self.__cap.stop()
                previous_options = os.environ.get('OPENCV_FFMPEG_CAPTURE_OPTIONS')
                os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = self._LIVE_FFMPEG_OPTIONS
                try:
                    self.__cap = VideoStream(self.__video_stream).start()
                finally:
                    if previous_options is None:
                        os.environ.pop('OPENCV_FFMPEG_CAPTURE_OPTIONS', None)
                    else:
                        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = previous_options
                if self.__cap is None:
                    self.__logger.error(f"Cannot open video stream: {self.__video_stream}")
                    raise StreamConnectionError(f"Cannot open video stream: {self.__video_stream}")
            else:
                self.__cap = cv2.VideoCapture(self.__video_stream)
                if self.__fps > 0:
                    self.__cap.set(cv2.CAP_PROP_FPS, self.__fps)
                if not self.__cap.isOpened():
                    self.__logger.error(f"Cannot open video stream: {self.__video_stream}")
                    raise StreamConnectionError(f"Cannot open video stream: {self.__video_stream}")
        except Exception as e:
            self.__logger.error(e)
            raise

    def stop(self) -> None:
        """
        A method to stop the video capture, if it's currently active.

        Returns:
            None
        """
        try:
            if self.__cap is not None:
                self._release_capture()
            else:
                print("Stream is not active.")
        except Exception as e:
            self.__logger.error(f"An error occurred while stopping the video stream: {e}")
            raise

    def get_frame(self) -> cv2.Mat:
        """
        A method to retrieve a frame using the 'cap' attribute.

        Returns:
            frame: A frame from the video stream
        """
        # if self.__cap is None:
        #    raise StreamConnectionError("Video stream is not active. Start the stream first.")

        frame = None
        if self.__cap is None and not self.reconnect_limit_reached():
            self.reconnect()

        if self.__cap is not None:
            if self.is_hls() or self.is_stream():
                frame = self.__cap.read()
            else:
                ret, frame = self.__cap.read()
                if not ret:
                    self.__logger.error("Failed to grab frame")

            if frame is None and not self.reconnect_limit_reached():
                self.__logger.error("Failed to grab frame or frame is None")
                self.reconnect()

            if frame is not None and frame is not self.__fps_frame:
                self.__fps_frame = frame
                self.calculate_fps()

            if self.__frame_interval > 0:
                time.sleep(self.__frame_interval)  # Add delay to control FPS

        return frame

    def reconnect(self) -> None:
        """
        Reconnects to the video stream

        Returns:
            None
        """
        if self.reconnect_limit_reached():
            return

        self.__logger.warning("Attempting to reconnect to video stream...")

        self._release_capture()
        time.sleep(self.DEFAULT_RECONNECT_DELAY_SEC)

        if self.connect():
            self.__logger.info("Reconnected to video stream successfully")

    def is_hls(self) -> bool:
        """
        Check if the source is an HTTP Live Streaming playlist (.m3u8).

        Returns:
            bool: True for HLS URLs, False otherwise
        """
        return self.__is_hls

    @staticmethod
    def _detect_hls(video_stream: str) -> bool:
        path = video_stream.lower().split('?', 1)[0]
        return path.endswith('.m3u8')

    def is_stream(self) -> bool:
        """
        Check if the video stream is a valid stream by verifying if it starts with common protocols.

        Returns:
            bool: True if the video stream is a valid stream, False otherwise
        """
        return isinstance(self.__video_stream, str) and self.__video_stream.lower().startswith(
            ('rtsp://', 'rtmp://', 'http://', 'https://', 'tcp://'))

    def _open_hls_capture(self) -> cv2.VideoCapture:
        previous_options = os.environ.get('OPENCV_FFMPEG_CAPTURE_OPTIONS')
        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = self._HLS_FFMPEG_OPTIONS
        try:
            return cv2.VideoCapture(
                self.__video_stream,
                cv2.CAP_FFMPEG,
                [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self._HLS_OPEN_TIMEOUT_MSEC],
            )
        finally:
            if previous_options is None:
                os.environ.pop('OPENCV_FFMPEG_CAPTURE_OPTIONS', None)
            else:
                os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = previous_options

    def _warmup_hls_capture(self):
        deadline = time.time() + self._HLS_WARMUP_TIMEOUT_SEC
        while time.time() < deadline:
            ret, frame = self.__cap.read()
            if ret and frame is not None:
                return frame
            time.sleep(self._HLS_READ_RETRY_DELAY_SEC)

        self.__logger.error(f"HLS warmup timed out: {self.__video_stream}")
        raise StreamConnectionError(f"Cannot open video stream: {self.__video_stream}")

    def _read_hls_frame(self):
        for _ in range(self._HLS_READ_RETRIES):
            ret, frame = self.__cap.read()
            if ret and frame is not None:
                return frame
            time.sleep(self._HLS_READ_RETRY_DELAY_SEC)
        return None

    def _release_capture(self) -> None:
        if self.__cap is None:
            return

        if self.is_hls():
            self.__cap.release()
        elif self.is_stream():
            self.__cap.stop()
        else:
            self.__cap.release()
        self.__cap = None

    def _capture_is_ready(self) -> bool:
        if self.__cap is None:
            return False
        if self.is_hls() or not self.is_stream():
            return self.__cap.isOpened()
        return True

    def get_actual_fps(self) -> float:
        """
        A method to get the actual calculated FPS.

        Returns:
            float: The actual calculated FPS
        """
        return self.__actual_fps

    def get_fps(self) -> float:
        """
        A method to get the FPS of the video stream.

        Returns:
            float: The FPS of the video stream
        """
        return self.__fps

    def calculate_fps(self) -> None:
        """
        Update camera FPS from new source frames only.

        The counting loop polls the latest buffer many times per frame. Counting
        every poll reports the poll rate, not the camera rate.
        """
        self.__fps_count += 1
        now = time.monotonic()
        span = now - self.__last_frame_time
        if span < 0.5:
            return
        self.__actual_fps = self.__fps_count / span
        self.__fps_count = 0
        self.__last_frame_time = now

    def get_reconnect_count(self) -> int:
        """
        Returns the number of reconnect attempts.
        """
        return self.__reconnect_count

    def reset_reconnect_count(self) -> None:
        """
        Resets the reconnect attempt count after a successful connection.
        """
        self.__reconnect_count = 0
