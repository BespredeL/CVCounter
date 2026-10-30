# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""DatabaseManager-backed implementation of the counter count store."""

from __future__ import annotations

import json
from typing import Any

from system.db.models.cvcounter import CVCounter


class DatabaseCountStore:
    """
    Persists counter results and serializes the active record for the UI.
    """

    def __init__(self, db_manager: Any) -> None:
        """
        Args:
            db_manager (Any): DatabaseManager instance shared by all counters.
        """
        self.db_manager = db_manager

    def get_current(self, location: str) -> dict | None:
        """
        Active record for a location as the dict the counter page expects.

        Args:
            location (str): Counter location identifier.

        Returns:
            dict | None: Serialized record, or None when nothing is active.
        """
        result: CVCounter | None = self.db_manager.get_current_count(location)
        if result is None:
            return None

        return {
            'active': result.active,
            'location': result.location,
            'total_count': result.total_count,
            'source_count': result.source_count,
            'defects_count': result.defects_count,
            'correct_count': result.correct_count,
            'parts': json.loads(result.parts) if result.parts else [],
            'custom_fields': json.loads(result.custom_fields) if result.custom_fields else [],
            'class_counts': json.loads(result.class_counts) if result.class_counts else [],
            'created_at': result.created_at.strftime("%Y-%m-%d %H:%M:%S") if result.created_at else None,
            'updated_at': result.updated_at.strftime("%Y-%m-%d %H:%M:%S") if result.updated_at else None
        }

    def save_result(self, **kwargs) -> bool:
        """Forward to DatabaseManager.save_result."""
        return self.db_manager.save_result(**kwargs)

    def save_part_result(self, **kwargs) -> bool:
        """Forward to DatabaseManager.save_part_result."""
        return self.db_manager.save_part_result(**kwargs)

    def close_current(self, location: str, class_counts: list | dict | None = None) -> bool:
        """Forward to DatabaseManager.close_current_count."""
        return self.db_manager.close_current_count(location, class_counts=class_counts)

    def close(self) -> None:
        """Close the shared database connection."""
        self.db_manager.close()
