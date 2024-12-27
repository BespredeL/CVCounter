# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.03.2024
# Updated: 26.12.2024
# Website: https://bespredel.name

import time

import cv2
from imutils.video import VideoStream

from system.exception_handler import FrameEncodingError, StreamConnectionError, StreamSourceError
from system.logger import Logger


class VideoStreamManager:
    def __init__(self, video_stream: str, video_fps: float) -> None:
        # Init logger
        self.__logger: Logger = Logger()

        if not video_stream:
            self.__logger.error("A video stream source is required")
            raise StreamSourceError("A video stream source is required")

        self.__video_stream: str = video_stream
        self.__cap: cv2.VideoCapture | VideoStream = None
        self.__fps: float = video_fps  # Default FPS
        self.__actual_fps: float = 0  # Calculated FPS based on frame intervals
        self.__last_frame_time: float = time.time()  # Time of the last frame capture
        self.__frame_interval: float = 1 / self.__fps if video_fps > 0 else 0  # Interval between frames based on FPS

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
            # Check if the source is a streaming URL or a local video/camera
            if self.is_stream():
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
                if self.is_stream():
                    self.__cap.stop()
                else:
                    self.__cap.release()
                self.__cap = None
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
            if self.is_stream():
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
        if self.is_stream():
            self.__cap.stop()
        else:
            self.__cap.release()

        time.sleep(3)
        self.start()
        if (not self.is_stream() and self.__cap.isOpened()) or (self.is_stream() and self.__cap is not None):
            self.__logger.info("Reconnected to video stream successfully")
        else:
            self.__logger.error("Failed to reconnect to video stream")

    def is_stream(self) -> bool:
        """
        Check if the video stream is a valid stream by verifying if it starts with common protocols.

        Returns:
            bool: True if the video stream is a valid stream, False otherwise
        """
        return isinstance(self.__video_stream, str) and self.__video_stream.lower().startswith(
            ('rtsp://', 'rtmp://', 'http://', 'https://', 'tcp://'))

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

    @staticmethod
    def encoding_frame(frame: cv2.Mat, quality: int = 95, ext: str = "jpg") -> bytes:
        """
        A method to encode the frame.

        Args:
            frame: The frame to encode
            quality: The quality of the encoded frame
            ext: The extension of the encoded frame

        Returns:
            frame_encoded: The encoded frame
        """
        ext = ext if ext.startswith(".") else "." + ext
        ret, frame_encoded = cv2.imencode(ext, frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ret:
            raise FrameEncodingError("Failed to encode frame")
        return frame_encoded

    @staticmethod
    def resize_frame(frame: cv2.Mat, scale_percent: int = 70) -> cv2.Mat:
        """
        Resizes the frame.

        Args:
            frame: The frame to resize
            scale_percent: The scale percentage of the resized frame

        Returns:
            frame: The resized frame
        """
        width = int(frame.shape[1] * scale_percent / 100)
        height = int(frame.shape[0] * scale_percent / 100)
        return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
