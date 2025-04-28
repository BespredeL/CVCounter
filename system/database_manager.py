# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 25.04.2025
# Website: https://bespredel.name

import json
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from system.logger import Logger
from system.db_model.base_model import Base
from system.db_model.cvcounter import CVCounter


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

    def save_result(self, location: str, total_count: int = 0, source_count: int = 0, defects_count: int = 0,
                    correct_count: int = 0, custom_fields: str = '', active: bool = True) -> bool:
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

        Returns:
            bool: True if the result was saved successfully, False otherwise.
        """
        session = self.create_session()
        try:
            result = session.query(CVCounter).filter_by(location=location, active=True).first()

            new_custom_fields = {}
            if custom_fields:
                new_custom_fields = json.loads(custom_fields if custom_fields else '{}')

            if result:
                # Обновляем существующие custom_fields
                existing_custom_fields = json.loads(result.custom_fields if result.custom_fields else '{}')
                if new_custom_fields:
                    # Объединение нового и существующего словаря
                    existing_custom_fields.update(new_custom_fields)
                    custom_fields = json.dumps(existing_custom_fields)

            if result:
                # Обновляем существующую запись
                result.active = active
                result.total_count = total_count
                result.source_count = source_count
                result.defects_count = defects_count
                result.correct_count = correct_count
                result.custom_fields = custom_fields
                result.updated_at = datetime.now()
            else:
                # Вставляем новую запись
                new_result = CVCounter(
                    active=active,
                    location=location,
                    total_count=total_count,
                    source_count=source_count,
                    defects_count=defects_count,
                    correct_count=correct_count,
                    custom_fields=custom_fields,
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
                         correct_count: int = 0) -> bool:
        """
        Saves a part result to the database.

        Args:
            location (str): The location of the result.
            current_count (int, optional): The current count. Defaults to 0.
            total_count (int, optional): The total count. Defaults to 0.
            defects_count (int, optional): The defects count. Defaults to 0.
            correct_count (int, optional): The correct count. Defaults to 0.

        Returns:
            bool: True if the result was saved successfully, False otherwise.
        """
        session = self.create_session()
        try:
            result = session.query(CVCounter).filter_by(location=location, active=True).first()
            if result:
                # Update the parts field
                parts = json.loads(result.parts) if result.parts else []
                parts.append({
                    'current': current_count,
                    'total': total_count,
                    'defects': defects_count,
                    'correct': correct_count,
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                parts = sorted(parts, key=lambda x: x['created_at'], reverse=True)
                result.parts = json.dumps(parts)
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

    def close_current_count(self, location: str) -> bool:
        """
        Closes the current counter for the specified location.

        Args:
            location (str): The location of the counter to close.

        Returns:
            bool: True if the counter was closed successfully, False otherwise.
        """
        session = self.create_session()
        try:
            result = session.query(CVCounter).filter_by(location=location, active=True).first()
            if result:
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
            query = session.query(CVCounter).filter_by(location=key)
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
