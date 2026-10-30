# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Vocabulary the counting core uses to talk to the web and storage layers."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CountingEventSink(Protocol):
    """
    Outward events of a running counter.

    The core never names a transport; the production implementation maps these
    onto Socket.IO event names already consumed by the browser.
    """

    def notify(self, message: str, kind: str) -> None:
        """Push a toast-style message to the UI."""
        ...

    def status(self, state: str) -> None:
        """Report a lifecycle state such as started, stopped, paused, error, collection."""
        ...

    def counts(self, payload: dict) -> None:
        """Broadcast a live counts payload."""
        ...


@runtime_checkable
class CountStore(Protocol):
    """
    Persistence of counter results.

    Counting methods take the same keyword arguments as DatabaseManager; only
    ``get_current`` differs, because the core wants the record already
    serialized rather than as an ORM object.
    """

    def get_current(self, location: str) -> dict | None:
        """Active record for a location, already serialized for the UI."""
        ...

    def save_result(self, **kwargs) -> bool:
        """Persist the accumulated counts for a location."""
        ...

    def save_part_result(self, **kwargs) -> bool:
        """Append a partial (current-batch) result for a location."""
        ...

    def close_current(self, location: str, class_counts: list | dict | None = None) -> bool:
        """Close the active record for a location."""
        ...

    def close(self) -> None:
        """Release the underlying connection."""
        ...