# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""The objects the running application shares between requests and counter threads."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flask_socketio import SocketIO

    from system.core.object_counter import ObjectCounter
    from system.managers.config_manager import ConfigManager
    from system.managers.database_manager import DatabaseManager
    from system.managers.thread_manager import ThreadManager


@dataclass
class AppRuntime:
    """
    Runtime singletons built once by ``create_app()``.

    Replaces the ``app_context`` dict that used to be passed around under
    ``current_app.config['APP_CONTEXT']``. The subscript, ``get`` and ``in``
    forms are kept so the existing readers keep working while they are moved
    onto attribute access; they only accept the field names below, so a typo
    raises instead of inventing a key.

    Attributes:
        config (ConfigManager): The loaded configuration manager
        locations (list[str]): Configured detection locations
        locations_dict (dict[str, str]): Location key to label mapping
        db_manager (DatabaseManager): The database manager
        object_counters (dict[str, ObjectCounter]): Live counters by location
        thread_manager (ThreadManager): Counter thread owner
        lock (Lock): Guards counter and thread creation
        users (dict[str, Any]): Configured web users
        socketio (SocketIO): The Socket.IO server
        socketio_transports (list[str]): Engine.IO transports in use
        socketio_upgrade (bool): Whether Socket.IO upgrade is allowed
    """

    config: ConfigManager
    locations: list[str]
    locations_dict: dict[str, str]
    db_manager: DatabaseManager
    object_counters: dict[str, ObjectCounter] = field(default_factory=dict)
    thread_manager: ThreadManager | None = None
    lock: Lock = field(default_factory=Lock)
    users: dict[str, Any] = field(default_factory=dict)
    socketio: SocketIO | None = None
    socketio_transports: list[str] = field(default_factory=list)
    socketio_upgrade: bool = True

    def __getitem__(self, key: str) -> Any:
        """
        Read a field the way the old context dict was read.

        Args:
            key (str): A field name of this runtime

        Returns:
            Any: The value stored in that field
        """
        if key not in self.__dataclass_fields__:
            raise KeyError(key)
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        """
        Write a field the way refresh_app_context() used to write the dict.

        Args:
            key (str): A field name of this runtime
            value (Any): The new value for that field

        Returns:
            None
        """
        if key not in self.__dataclass_fields__:
            raise KeyError(key)
        setattr(self, key, value)

    def __contains__(self, key: object) -> bool:
        """
        Report whether a name is a runtime field.

        Args:
            key (object): The name to look up

        Returns:
            bool: True when the name is a field of this runtime
        """
        return key in self.__dataclass_fields__

    def get(self, key: str, default: Any = None) -> Any:
        """
        Read a field, falling back like the old dict.get() did.

        Args:
            key (str): A field name of this runtime
            default (Any): Value returned when the name is not a field

        Returns:
            Any: The field value, or default
        """
        try:
            return self[key]
        except KeyError:
            return default

