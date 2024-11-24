# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 21.07.2024
# Updated: 24.11.2024
# Website: https://bespredel.name

class NotificationManager:
    def __init__(self, socketio: any, location: str) -> None:
        if not socketio:
            raise ValueError("socketio instance is required")

        if not isinstance(location, str):
            raise TypeError("location must be a string")

        self.socketio = socketio
        self.location = location

    def emit(self, event: str, data: any) -> None:
        """
        Emits the given event with the provided data if the socketio exists.

        Args:
            event (str): The event to emit.
            data (any): The data to emit with the event.
        """

        if self.socketio:
            self.socketio.emit(event, data)

    def notify(self, message: any, notification_type: any) -> None:
        """
        Notify the specified message with the given notification type.

        Args:
            message (any): The message to notify.
            notification_type (any): The type of notification.

        Returns:
            None
        """

        self.emit(f'{self.location}_notification', {'type': notification_type, 'message': message})

    def event(self, name: str, data: any) -> None:
        """
        Emit an event to the client.

        Args:
            name (str): The name of the event.
            data (dict): The data associated with the event.

        Returns:
            None
        """

        self.emit(f'{name}_event', {'data': data})
