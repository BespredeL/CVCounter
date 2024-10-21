# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.03.2024
# Updated: 21.10.2024
# Website: https://bespredel.name

import time
import cv2
from imutils.video import VideoStream


class VideoStreamManager:
    def __init__(self, video_stream):
        if not video_stream:
            raise ValueError("A video stream source is required")

        self.__video_stream = video_stream
        self.__cap = None
        self.__fps = 30

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
                self.__fps = 30
            else:
                self.__cap = cv2.VideoCapture(self.__video_stream)
                if not self.__cap.isOpened():
                    raise ValueError(f"Cannot open video stream: {self.__video_stream}")

                # Getting the frame rate (FPS) for video files
                self.__fps = self.__cap.get(cv2.CAP_PROP_FPS)
                if self.__fps == 0:
                    self.__fps = 30
        except Exception as e:
            print(f"An error occurred while starting the video stream: {e}")

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
            print(f"An error occurred while stopping the video stream: {e}")

    """
    Check if the video stream is a valid stream by verifying if it starts with common protocols.
    
    Parameters:
        None
    
    Returns:
        bool: True if the video stream is a valid stream, False otherwise
    """

    def is_stream(self):
        return (isinstance(self.__video_stream, str)
                and self.__video_stream.lower().startswith(('rtsp://', 'rtmp://', 'http://', 'https://', 'tcp://')))

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
                    print("Failed to grab frame")
        return frame

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
    Reconnects to the video stream
    
    Parameters:
        None
    
    Returns:
        None
    """

    def reconnect(self):
        self.stop()
        time.sleep(5)
        print("Reconnecting to video stream...")
        self.start()
        print("Reconnected to video stream")

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
