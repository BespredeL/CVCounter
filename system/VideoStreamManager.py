# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 26.03.2024
# Updated: 03.09.2024
# Website: https://bespredel.name

import time

from imutils.video import VideoStream


class VideoStreamManager:
    def __init__(self, video_stream):
        if not video_stream:
            raise ValueError("A video stream source is required")

        self.__video_stream = video_stream
        self.__cap = None

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
            if self.is_stream():
                if self.__cap is not None:
                    self.__cap.stop()
                self.__cap = VideoStream(self.__video_stream).start()
            else:
                self.__cap = VideoStream(self.__video_stream).start()
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
            if self.is_stream() and self.__cap is not None:
                self.__cap.stop()
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
        return not (isinstance(self.__video_stream, str)
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
            frame = self.__cap.read()
        return frame

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
