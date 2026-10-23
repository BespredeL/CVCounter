# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

import os
import threading
import time
from collections import deque

import cv2
from imutils.video import VideoStream

from system.utils.exception_handler import StreamConnectionError, StreamSourceError
from system.utils.logger import Logger


class _TimedLatestReader:
    """Playout ring for RTSP. Capture is not queried from any other thread."""

    _RING = 12

    def __init__(self, src: str) -> None:
        self.stream = cv2.VideoCapture(src)
        self.frame = None
        self.stopped = False
        self._slots: list | None = None
        self._free: deque = deque()
        self._queued: deque = deque()
        self._current: int | None = None
        self._shown_seq = 0
        self.follow_shown = False
        self.capture_fps = 0.0
        self._cap_count = 0
        self._cap_tick = time.monotonic()
        self._lock = threading.Lock()
        try:
            self.stream.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        ok, frame = self.stream.read()
        if ok and frame is not None:
            self._store(frame)
        self._thread = threading.Thread(target=self._loop, name="rtsp-read", daemon=True)
        self._thread.start()

    def _ensure_slots(self, frame) -> None:
        if self._slots is not None and self._slots[0].shape == frame.shape:
            return
        self._slots = [frame.copy() for _ in range(self._RING)]
        self._free = deque(range(1, self._RING))
        self._queued = deque()
        self._current = 0
        self.frame = self._slots[0]

    def _store(self, frame) -> None:
        self._ensure_slots(frame)
        with self._lock:
            if not self._free and self._queued:
                self._free.append(self._queued.popleft())
            if not self._free:
                return
            idx = self._free.popleft()
        self._slots[idx][:] = frame
        with self._lock:
            self._queued.append(idx)
        self._cap_count += 1
        now = time.monotonic()
        span = now - self._cap_tick
        if span >= 0.5:
            self.capture_fps = self._cap_count / span
            self._cap_count = 0
            self._cap_tick = now

    def _loop(self) -> None:
        while not self.stopped:
            ok, frame = self.stream.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue
            self._store(frame)

    def read(self):
        with self._lock:
            if self._current is not None:
                self._free.append(self._current)
                self._current = None
            if self._queued:
                self._current = self._queued.popleft()
                self.frame = self._slots[self._current]
            return self.frame

    def pop(self):
        """Next queued frame, or None when playout has caught up. Does not repeat the last frame."""
        with self._lock:
            if not self._queued:
                return None
            if self._current is not None:
                self._free.append(self._current)
            self._current = self._queued.popleft()
            self.frame = self._slots[self._current]
            self._shown_seq += 1
            return self.frame

    def latest_copy(self):
        """Copy of the frame detection should use. While playout is active this is the frame on screen."""
        with self._lock:
            if self.follow_shown and self._current is not None:
                idx = self._current
            else:
                idx = self._queued[-1] if self._queued else self._current
            if idx is None:
                src = self.frame
                return None if src is None else src.copy()
            return self._slots[idx].copy()

    def stop(self) -> None:
        self.stopped = True
        try:
            self.stream.release()
        except Exception:
            pass


class VideoStreamManager:
    DEFAULT_MAX_RECONNECT_ATTEMPTS: int = 10
    DEFAULT_RECONNECT_DELAY_SEC: float = 1.0
    _HLS_FFMPEG_OPTIONS: str = 'reconnect;1|reconnect_streamed;1|reconnect_delay_max;5'
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
        self.__last_frame_time: float = time.time()  # Time of the last frame capture
        self.__frame_interval: float = 1 / self.__fps if video_fps > 0 else 0  # Interval between frames based on FPS
        self.__reconnect_count: int = 0
        self.__max_reconnect_attempts: int = max(
            1,
            int(max_reconnect_attempts or self.DEFAULT_MAX_RECONNECT_ATTEMPTS),
        )

    @property
    def video_stream(self) -> str:
        """
        Get the video stream source.

        Args:
            None

        Returns:
            str: The video stream source
        """
        return self.__video_stream

    @property
    def cap(self) -> cv2.VideoCapture:
        """
        Get the video capture object.

        Args:
            None

        Returns:
            cv2.VideoCapture: The video capture object
        """
        return self.__cap

    def connect(self) -> bool:
        """
        Open the video stream once.

        Args:
            None

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
        """
        Whether the configured connection attempt limit has been exhausted.
        
        Args:
            None

        Returns:
            bool: True if the reconnect limit has been reached, False otherwise
        """
        return self.__reconnect_count >= self.__max_reconnect_attempts

    def start(self) -> None:
        """
        Starts the video stream.

        Args:
            None

        Returns:
            None
        """
        try:
            if self.is_hls():
                self._release_capture()
                self.__cap = self._open_hls_capture()
                if not self.__cap.isOpened():
                    self.__logger.error(f"Cannot open HLS stream: {self.__video_stream}")
                    raise StreamConnectionError(f"Cannot open video stream: {self.__video_stream}")
                self._warmup_hls_capture()
            elif self.is_stream():
                if self.__cap is not None:
                    self.__cap.stop()
                self.__cap = self._open_live_stream()
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

        Args:
            None

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

        Args:
            None

        Returns:
            frame: A frame from the video stream
        """
        # if self.__cap is None:
        #    raise StreamConnectionError("Video stream is not active. Start the stream first.")

        frame = None
        if self.__cap is None and not self.reconnect_limit_reached():
            self.reconnect()

        if self.__cap is not None:
            if self.is_hls():
                frame = self._read_hls_frame()
            elif self.is_stream():
                if isinstance(self.__cap, _TimedLatestReader):
                    frame = self.__cap.latest_copy()
                else:
                    frame = self.__cap.read()
            else:
                ret, frame = self.__cap.read()
                if not ret:
                    self.__logger.error("Failed to grab frame")

            if frame is None and not self.reconnect_limit_reached():
                self.__logger.error("Failed to grab frame or frame is None")
                self.reconnect()

            self.calculate_fps()  # Calculate actual FPS

            # Only rate limit offline video files to emulate target FPS.
            # Live streams (RTSP/HLS/webcam) deliver frames in real-time;
            # sleeping on them causes buffer accumulation and growing delay.
            if self.__frame_interval > 0 and not self.is_live_source():
                time.sleep(self.__frame_interval)

        return frame

    def uses_live_queue(self) -> bool:
        return isinstance(self.__cap, _TimedLatestReader)

    def set_follow_shown(self, enabled: bool) -> None:
        if isinstance(self.__cap, _TimedLatestReader):
            self.__cap.follow_shown = enabled

    def shown_seq(self) -> int:
        if isinstance(self.__cap, _TimedLatestReader):
            return self.__cap._shown_seq
        return -1

    def pop_live_frame(self):
        """Pop the next RTSP playout frame. None when the queue is empty or this source has no queue."""
        if isinstance(self.__cap, _TimedLatestReader):
            return self.__cap.pop()
        return None

    def reconnect(self) -> None:
        """
        Reconnects to the video stream

        Args:
            None

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

        Args:
            None

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

        Args:
            None

        Returns:
            bool: True if the video stream is a valid stream, False otherwise
        """
        return isinstance(self.__video_stream, str) and self.__video_stream.lower().startswith(
            ('rtsp://', 'rtmp://', 'http://', 'https://', 'tcp://'))

    def is_live_source(self) -> bool:
        """
        Check if the video stream is a real-time live source (network stream or local device).

        Returns:
            bool: True for RTSP/HTTP/HLS or camera index, False for offline files.
        """
        if self.is_hls() or self.is_stream():
            return True
        if isinstance(self.__video_stream, int):
            return True
        if isinstance(self.__video_stream, str) and self.__video_stream.isdigit():
            return True
        return False

    def _open_live_stream(self):
        """
        Open a network stream. RTSP keeps a small playout queue so a short network pause
        does not freeze the picture. FFmpeg options stay at defaults.
        """
        source = str(self.__video_stream).lower()
        if source.startswith('rtsp://') or '/rtsp/' in source:
            return _TimedLatestReader(self.__video_stream)
        return VideoStream(self.__video_stream).start()

    def _open_hls_capture(self) -> cv2.VideoCapture:
        """
        Open an HLS capture.
        
        Args:
            None

        Returns:
            cv2.VideoCapture: The HLS capture
        """
        previous_options = os.environ.get('OPENCV_FFMPEG_CAPTURE_OPTIONS')
        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = self._HLS_FFMPEG_OPTIONS
        try:
            return cv2.VideoCapture(self.__video_stream, cv2.CAP_FFMPEG)
        finally:
            if previous_options is None:
                os.environ.pop('OPENCV_FFMPEG_CAPTURE_OPTIONS', None)
            else:
                os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = previous_options

    def _warmup_hls_capture(self) -> None:
        """
        Warm up the HLS capture.
        
        Args:
            None

        Returns:
            None
        """
        deadline = time.time() + self._HLS_WARMUP_TIMEOUT_SEC
        while time.time() < deadline:
            ret, frame = self.__cap.read()
            if ret and frame is not None:
                return
            time.sleep(self._HLS_READ_RETRY_DELAY_SEC)

        self.__logger.error(f"HLS warmup timed out: {self.__video_stream}")
        raise StreamConnectionError(f"Cannot open video stream: {self.__video_stream}")

    def _read_hls_frame(self):
        """
        Read an HLS frame.
        
        Args:
            None

        Returns:
            cv2.Mat: The HLS frame
        """
        for _ in range(self._HLS_READ_RETRIES):
            ret, frame = self.__cap.read()
            if ret and frame is not None:
                return frame
            time.sleep(self._HLS_READ_RETRY_DELAY_SEC)
        return None

    def _release_capture(self) -> None:
        """
        Release the capture.
        
        Args:
            None

        Returns:
            None
        """
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
        """
        Check if the capture is ready.
        
        Args:
            None

        Returns:
            bool: True if the capture is ready, False otherwise
        """
        if self.__cap is None:
            return False
        if self.is_hls() or not self.is_stream():
            return self.__cap.isOpened()
        return True

    def get_actual_fps(self) -> float:
        """
        A method to get the actual calculated FPS.

        Args:
            None

        Returns:
            float: The actual calculated FPS
        """
        return self.__actual_fps

    def capture_fps(self) -> float:
        """
        Frames per second arriving from the camera.

        RTSP counts frames stored by the capture thread. Other sources use the
        rate at which frames are read.
        """
        cap = self.__cap
        if isinstance(cap, _TimedLatestReader):
            return float(cap.capture_fps)
        return float(self.__actual_fps)

    def get_fps(self) -> float:
        """
        A method to get the FPS of the video stream.

        Args:
            None

        Returns:
            float: The FPS of the video stream
        """
        return self.__fps

    def calculate_fps(self) -> None:
        """
        A method to calculate the actual FPS based on time intervals between frames.

        Args:
            None

        Returns:
            None
        """
        current_time = time.time()
        time_difference = current_time - self.__last_frame_time
        self.__actual_fps = 1 / time_difference if time_difference > 0 else 0
        self.__last_frame_time = current_time

    def get_reconnect_count(self) -> int:
        """
        Returns the number of reconnect attempts.

        Args:
            None

        Returns:
            int: The number of reconnect attempts
        """
        return self.__reconnect_count

    def reset_reconnect_count(self) -> None:
        """
        Resets the reconnect attempt count after a successful connection.
        
        Args:
            None

        Returns:
            None
        """
        self.__reconnect_count = 0
