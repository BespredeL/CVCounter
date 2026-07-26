# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 22.01.2026
# Website: https://bespredel.name

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from system.utils.logger import Logger
from system.db.models.base_model import Base
from system.db.models.cvcounter import CVCounter


class DatabaseManager:

    def __init__(self, uri: str, prefix: str = ''):
        """
        Database manager using SQLAlchemy.

        Args:
            uri (str): Database connection URL.
            prefix (str, optional): Table prefix. Defaults to ''.
        """
        self.__logger: Logger = Logger()
        try:
            self.__engine: any = create_engine(uri)
            self.__prefix: str = prefix
            self.__sessionmaker: any = sessionmaker(bind=self.__engine)

            # Create tables if they don't exist yet
            Base.metadata.create_all(self.__engine)
        except SQLAlchemyError as error:
            self.__logger.error(str(error))
            self.__logger.log_exception()

    def create_session(self) -> any:
        """
        Creates and returns a new session.

        Returns:
            Session: A new session.
        """
        return self.__sessionmaker()

    @staticmethod
    def _serialize_class_counts(class_counts: Optional[list | dict] = None) -> str | None:
        """Serialize class counts for Text storage."""
        if class_counts is None:
            return None
        return json.dumps(class_counts)

    def save_result(self, location: str, total_count: int = 0, source_count: int = 0, defects_count: int = 0,
                    correct_count: int = 0, custom_fields: str = '', active: bool = True,
                    class_counts: Optional[list | dict] = None) -> bool:
        """
        Saves a result to the database.

        Args:
            location (str): The location of the result.
            total_count (int, optional): The total count. Defaults to 0.
            source_count (int, optional): The source count. Defaults to 0.
            defects_count (int, optional): The defects count. Defaults to 0.
            correct_count (int, optional): The correct count. Defaults to 0.
            custom_fields (str, optional): The custom fields. Defaults to ''.
            active (bool, optional): The active status. Defaults to True.
            class_counts (list | dict, optional): Per-class totals payload.

        Returns:
            bool: True if the result was saved successfully, False otherwise.
        """
        session = self.create_session()
        try:
            result = session.query(CVCounter).filter_by(location=location, active=True).first()
            class_counts_json = self._serialize_class_counts(class_counts)

            new_custom_fields = {}
            if custom_fields:
                new_custom_fields = json.loads(custom_fields if custom_fields else '{}')

            if result:
                # Updating existing custom_fields
                existing_custom_fields = json.loads(result.custom_fields if result.custom_fields else '{}')
                if new_custom_fields:
                    # Combining new and existing vocabulary
                    existing_custom_fields.update(new_custom_fields)
                    custom_fields = json.dumps(existing_custom_fields)

            if result:
                # Updating an existing record
                result.active = active
                result.total_count = total_count
                result.source_count = source_count
                result.defects_count = defects_count
                result.correct_count = correct_count
                result.custom_fields = custom_fields
                if class_counts_json is not None:
                    result.class_counts = class_counts_json
                result.updated_at = datetime.now()
            else:
                # Insert a new record
                new_result = CVCounter(
                    active=active,
                    location=location,
                    total_count=total_count,
                    source_count=source_count,
                    defects_count=defects_count,
                    correct_count=correct_count,
                    custom_fields=custom_fields,
                    class_counts=class_counts_json,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(new_result)
            session.commit()
            return True
        except SQLAlchemyError as error:
            session.rollback()
            self.__logger.error(str(error))
            self.__logger.log_exception()
            return False
        finally:
            session.close()

    def save_part_result(self, location: str, current_count: int = 0, total_count: int = 0, defects_count: int = 0,
                         correct_count: int = 0, by_class: Optional[list | dict] = None,
                         class_counts: Optional[list | dict] = None) -> bool:
        """
        Saves a part result to the database.

        Args:
            location (str): The location of the result.
            current_count (int, optional): The current count. Defaults to 0.
            total_count (int, optional): The total count. Defaults to 0.
            defects_count (int, optional): The defects count. Defaults to 0.
            correct_count (int, optional): The correct count. Defaults to 0.
            by_class (list | dict, optional): Per-class counts for this batch.
            class_counts (list | dict, optional): Session-level per-class totals.

        Returns:
            bool: True if the result was saved successfully, False otherwise.
        """
        session = self.create_session()
        try:
            result = session.query(CVCounter).filter_by(location=location, active=True).first()
            if result:
                # Update the parts field
                parts = json.loads(result.parts) if result.parts else []
                part_entry = {
                    'current': current_count,
                    'total': total_count,
                    'defects': defects_count,
                    'correct': correct_count,
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                if by_class is not None:
                    part_entry['by_class'] = by_class
                parts.append(part_entry)
                parts = sorted(parts, key=lambda x: x['created_at'], reverse=False)
                result.parts = json.dumps(parts)
                if class_counts is not None:
                    result.class_counts = self._serialize_class_counts(class_counts)
                result.updated_at = datetime.now()
                session.commit()
                return True
            return False
        except SQLAlchemyError as error:
            session.rollback()
            self.__logger.error(str(error))
            self.__logger.log_exception()
            return False
        finally:
            session.close()

    def close_current_count(self, location: str, class_counts: Optional[list | dict] = None) -> bool:
        """
        Closes the current counter for the specified location.

        Args:
            location (str): The location of the counter to close.
            class_counts (list | dict, optional): Final per-class totals to persist.

        Returns:
            bool: True if the counter was closed successfully, False otherwise.
        """
        session = self.create_session()
        try:
            result = session.query(CVCounter).filter_by(location=location, active=True).first()
            if result:
                if class_counts is not None:
                    result.class_counts = self._serialize_class_counts(class_counts)
                result.active = False
                result.updated_at = datetime.now()
                session.commit()
                return True
            return False
        except SQLAlchemyError as error:
            session.rollback()
            self.__logger.error(str(error))
            return False
        finally:
            session.close()

    def get_current_count(self, key: str = '') -> CVCounter | None:
        """
        Returns the current counter for the given key.

        Args:
            key (str, optional): The key. Defaults to ''.

        Returns:
            CVCounter: The current counter.
        """
        session = self.create_session()
        try:
            result = session.query(CVCounter).filter_by(active=True, location=key).first()
            return result if result else None
        except SQLAlchemyError as error:
            self.__logger.error(str(error))
            return None
        finally:
            session.close()

    def get_count(self, rec_id: int) -> CVCounter | None:
        """
        Returns the count for the given id.

        Args:
            rec_id (int): The record id.

        Returns:
            CVCounter: The count.
        """
        session = self.create_session()
        try:
            result = session.query(CVCounter).filter_by(id=rec_id).first()
            return result if result else None
        except SQLAlchemyError as error:
            self.__logger.error(str(error))
            return None
        finally:
            session.close()

    def get_paginated(self, key: str = '', page: int = 1, per_page: int = 10) -> dict | None:
        """
        Returns all counters for the given key.

        Args:
            key (str, optional): The key. Defaults to ''.
            page (int, optional): The page number. Defaults to 1.
            per_page (int, optional): The number of records per page. Defaults to 10.

        Returns:
            list: A list of counters.
        """
        session = self.create_session()
        try:
            query = session.query(CVCounter).filter_by(location=key).order_by(CVCounter.created_at.desc())
            total = query.count()  # Getting the total number of records
            results = query.offset((page - 1) * per_page).limit(per_page).all()  # Applying offset and limit

            return {
                'total': total,
                'page': page,
                'per_page': per_page,
                'results': results,
                'has_next': page * per_page < total,  # Checking if there is a next page
                'has_prev': page > 1  # Checking if there is a previous page
            }
        except SQLAlchemyError as error:
            self.__logger.error(f"Error retrieving counters for key '{key}': {str(error)}")
            return None  # Return None on error
        finally:
            session.close()

    def close(self) -> None:
        """
        Closes all database connections and releases resources.
        
        This method should be called when the application is shutting down
        to properly close all database connections.
        
        Returns:
            None
        """
        try:
            if hasattr(self, '_DatabaseManager__engine'):
                self.__engine.dispose()
                self.__logger.info("Database connections closed successfully")
        except Exception as e:
            self.__logger.error(f"Error closing database connections: {e}")
