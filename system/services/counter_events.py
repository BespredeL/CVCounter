# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Socket.IO-backed implementation of the counter event sink."""

from __future__ import annotations

from system.managers.notification_manager import NotificationManager


class NotificationEventSink:
    """
    Maps counter events onto the Socket.IO event names the browser listens to.

    The counter emits `{location}_count` for live counts, `{name}_event` for
    status changes and `{location}_notification` for toasts; those suffixes are
    added by NotificationManager and must not change.
    """

    def __init__(self, notifier: NotificationManager) -> None:
        """
        Args:
            notifier (NotificationManager): Already configured notifier for one location.
        """
        self.notifier = notifier

    def notify(self, message: str, kind: str) -> None:
        """Push a toast-style message to the UI."""
        self.notifier.notify(message, kind)

    def status(self, state: str) -> None:
        """Report a lifecycle state for this counter's location."""
        self.notifier.event('counter_status', {'status': state, 'location': self.notifier.location})

    def counts(self, payload: dict) -> None:
        """Broadcast a live counts payload for this counter's location."""
        self.notifier.emit(f'{self.notifier.location}_count', payload)
