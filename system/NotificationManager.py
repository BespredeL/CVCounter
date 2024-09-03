# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 21.07.2024
# Updated: 03.09.2024
# Website: https://bespredel.name

class NotificationManager:
    def __init__(self, socketio, location):
        if not socketio:
            raise ValueError("socketio instance is required")

        if not isinstance(location, str):
            raise TypeError("location must be a string")

        self.socketio = socketio
        self.location = location

    """
    Emits the given event with the provided data if the socketio exists.

    Parameters:
        event (str): The event to emit.
        data (any): The data to emit with the event.
    """

    def emit(self, event, data):
        if self.socketio:
            self.socketio.emit(event, data)

    """
    Notify the specified message with the given notification type.

    Parameters:
        message (any): The message to notify.
        notification_type (any): The type of notification.

    Returns:
        None
    """

    def notify(self, message, notification_type):
        self.emit(f'{self.location}_notification', {'type': notification_type, 'message': message})

    """
    Emit an event to the client.

    Parameters:
        key (str): The name of the event.
        data (dict): The data associated with the event.

    Returns:
        None
    """

    def event(self, name, data):
        self.emit(f'{name}_event', {'data': data})
