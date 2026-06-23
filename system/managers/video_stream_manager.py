# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.03.2024
# Updated: 23.06.2026
# Website: https://bespredel.name

import os
import time

import cv2
from imutils.video import VideoStream

from system.utils.exception_handler import StreamConnectionError, StreamSourceError
from system.utils.logger import Logger

_HLS_FFMPEG_OPTIONS = 'reconnect;1|reconnect_streamed;1|reconnect_delay_max;5'
_HLS_WARMUP_TIMEOUT_SEC = 15.0
_HLS_READ_RETRIES = 5
_HLS_READ_RETRY_DELAY_SEC = 0.2


class VideoStreamManager:
    def __init__(self, video_stream: str, video_fps: float) -> None:
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
        self.__reconnect_count: int = 0  # Count of reconnect attempts

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

    def start(self) -> None:
        """
        Starts the video stream.

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
                self.__cap = VideoStream(self.__video_stream).start()
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
        if self.__cap is not None:
            if self.is_hls():
                frame = self._read_hls_frame()
            elif self.is_stream():
                frame = self.__cap.read()
            else:
                ret, frame = self.__cap.read()
                if not ret:
                    self.__logger.error("Failed to grab frame")

            if frame is None:
                self.__logger.error("Failed to grab frame or frame is None")
                self.reconnect()

            self.calculate_fps()  # Calculate actual FPS

            if self.__frame_interval > 0:
                time.sleep(self.__frame_interval)  # Add delay to control FPS

        return frame

    def reconnect(self) -> None:
        """
        Reconnects to the video stream

        Returns:
            None
        """
        self.__logger.warning("Attempting to reconnect to video stream...")

        self._release_capture()

        time.sleep(3)
        self.__reconnect_count += 1

        try:
            self.start()

            if self._capture_is_ready():
                self.__logger.info("Reconnected to video stream successfully")
                # self.reset_reconnect_count()
            else:
                self.__logger.error("Failed to reconnect to video stream")
        except Exception as e:
            self.__logger.error(f"Error during reconnect attempt: {e}")

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
        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = _HLS_FFMPEG_OPTIONS
        try:
            return cv2.VideoCapture(self.__video_stream, cv2.CAP_FFMPEG)
        finally:
            if previous_options is None:
                os.environ.pop('OPENCV_FFMPEG_CAPTURE_OPTIONS', None)
            else:
                os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = previous_options

    def _warmup_hls_capture(self) -> None:
        deadline = time.time() + _HLS_WARMUP_TIMEOUT_SEC
        while time.time() < deadline:
            ret, frame = self.__cap.read()
            if ret and frame is not None:
                return
            time.sleep(_HLS_READ_RETRY_DELAY_SEC)

        self.__logger.error(f"HLS warmup timed out: {self.__video_stream}")
        raise StreamConnectionError(f"Cannot open video stream: {self.__video_stream}")

    def _read_hls_frame(self):
        for _ in range(_HLS_READ_RETRIES):
            ret, frame = self.__cap.read()
            if ret and frame is not None:
                return frame
            time.sleep(_HLS_READ_RETRY_DELAY_SEC)
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
        A method to calculate the actual FPS based on time intervals between frames.

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
        """
        return self.__reconnect_count

    def reset_reconnect_count(self) -> None:
        """
        Resets the reconnect attempt count after a successful connection.
        """
        self.__reconnect_count = 0
