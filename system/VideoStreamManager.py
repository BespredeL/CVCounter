# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.03.2024
# Updated: 20.11.2024
# Website: https://bespredel.name

import time
import cv2
from imutils.video import VideoStream
from system.Logger import Logger


class VideoStreamManager:
    def __init__(self, video_stream, video_fps):
        # Init logger
        self.__logger = Logger()

        if not video_stream:
            self.__logger.error("A video stream source is required")
            raise ValueError("A video stream source is required")

        self.__video_stream = video_stream
        self.__cap = None
        self.__fps = video_fps  # Default FPS
        self.__actual_fps = 0  # Calculated FPS based on frame intervals
        self.__last_frame_time = time.time()  # Time of the last frame capture
        self.__frame_interval = 1 / self.__fps if video_fps > 0 else 0  # Interval between frames based on FPS

    """
    Get the video stream source.
    
    Parameters:
        None
    
    Returns:
        str: The video stream source
    """

    @property
    def video_stream(self):
        return self.__video_stream

    """
    Get the video capture object.
    
    Parameters:
        None
    
    Returns:
        cv2.VideoCapture: The video capture object
    """

    @property
    def cap(self):
        return self.__cap

    """
    Starts the video stream.

    Parameters:
        None
        
    Returns:
        None
    """

    def start(self):
        try:
            # Check if the source is a streaming URL or a local video/camera
            if self.is_stream():
                if self.__cap is not None:
                    self.__cap.stop()
                self.__cap = VideoStream(self.__video_stream).start()
                if self.__cap is None:
                    self.__logger.error(f"Cannot open video stream: {self.__video_stream}")
                    raise ValueError(f"Cannot open video stream: {self.__video_stream}")
            else:
                self.__cap = cv2.VideoCapture(self.__video_stream)
                if self.__fps > 0:
                    self.__cap.set(cv2.CAP_PROP_FPS, self.__fps)
                if not self.__cap.isOpened():
                    self.__logger.error(f"Cannot open video stream: {self.__video_stream}")
                    raise ValueError(f"Cannot open video stream: {self.__video_stream}")
        except Exception as e:
            self.__logger.error(e)

    """
    A method to stop the video capture, if it's currently active.
    
    Parameters:
        None
    
    Returns:
        None
    """

    def stop(self):
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

    """
    A method to retrieve a frame using the 'cap' attribute.
    
    Parameters:
        None
    
    Returns:
        frame: A frame from the video stream
    """

    def get_frame(self):
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

    """
    Reconnects to the video stream

    Parameters:
        None

    Returns:
        None
    """

    def reconnect(self):
        self.__logger.error("Attempting to reconnect to video stream...")
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

    """
    Check if the video stream is a valid stream by verifying if it starts with common protocols.

    Parameters:
        None

    Returns:
        bool: True if the video stream is a valid stream, False otherwise
    """

    def is_stream(self):
        return isinstance(self.__video_stream, str) and self.__video_stream.lower().startswith(
            ('rtsp://', 'rtmp://', 'http://', 'https://', 'tcp://'))

    """
    A method to get the actual calculated FPS.
    
    Parameters:
        None
    
    Returns:
        float: The actual calculated FPS
    """

    def get_actual_fps(self):
        return self.__actual_fps

    """
    A method to get the FPS of the video stream.
    
    Parameters:
        None
    
    Returns:
        int: The FPS of the video stream
    """

    def get_fps(self):
        return self.__fps

    """
    A method to calculate the actual FPS based on time intervals between frames.
    
    Parameters:
        None
    
    Returns:
        None
    """

    def calculate_fps(self):
        current_time = time.time()
        time_difference = current_time - self.__last_frame_time
        self.__actual_fps = 1 / time_difference if time_difference > 0 else 0
        self.__last_frame_time = current_time

    """
    A method to encode the frame.

    Parameters:
        frame: The frame to encode
        quality: The quality of the encoded frame
        ext: The extension of the encoded frame

    Returns:
        frame_encoded: The encoded frame
    """

    @staticmethod
    def encoding_frame(frame, quality=95, ext="jpg"):
        ext = ext if ext.startswith(".") else "." + ext
        ret, frame_encoded = cv2.imencode(ext, frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ret:
            print("Failed to encode frame")
            raise ValueError("Failed to encode frame")
        return frame_encoded

    """
    Resizes the frame.
    
    Parameters:
        frame: The frame to resize
        width: The width of the resized frame
        height: The height of the resized frame
    
    Returns:
        frame: The resized frame
    """

    @staticmethod
    def resize_frame(frame, scale_percent=70):
        width = int(frame.shape[1] * scale_percent / 100)
        height = int(frame.shape[0] * scale_percent / 100)
        return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
