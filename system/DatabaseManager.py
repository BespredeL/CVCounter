# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 05.09.2024
# Website: https://bespredel.name

import json
from datetime import datetime
from functools import lru_cache

import mysql.connector

from system.Logger import Logger


class DatabaseManager:
    """
    Database manager.

    Args:
        host (str): Host name.
        user (str): Username.
        password (str): Password.
        database (str): Database name.
        prefix (str, optional): Prefix. Defaults to ''.
    """

    def __init__(self, host, user, password, database, prefix=''):
        self.__logger = Logger("errors.log")
        self.__prefix = prefix
        self.__conn = None
        self.connect(host, user, password, database)

        if self.check_connection():
            self.create_table()

    """
    Connect to the database.

    Parameters:
        self (object): The instance of the class.
        host (str): Host name.
        user (str): Username.
        password (str): Password.
        database (str): Database name.

    Returns:
        None
    """

    def connect(self, host, user, password, database):
        try:
            self.__conn = mysql.connector.connect(
                host=str(host),
                user=str(user),
                password=str(password),
                database=str(database),
            )
        except (mysql.connector.Error, Exception) as e:
            self.__conn = None
            self.__logger.log_exception()

    """
    Check the connection to the database.

    Parameters:
        self (object): The instance of the class.

    Returns:
        bool: True if the connection is successful, False otherwise.
    """

    def check_connection(self):
        if self.__conn is None:
            return False
        try:
            self.__conn.ping(reconnect=True, attempts=3, delay=5)
            return True
        except mysql.connector.Error as error:
            self.__logger.log_error(str(error))
            return False

    """
    Create a tables if it does not already exist in the database. 

    Parameters:
        None

    Returns:
        None
    """

    def create_table(self):
        try:
            with self.__conn.cursor() as cursor:
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.__prefix}cvcounter (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        active TINYINT(1) DEFAULT 1,
                        location VARCHAR(255) NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        item_count INT DEFAULT 0,
                        source_count INT DEFAULT 0,
                        defects_count INT DEFAULT 0,
                        correct_count INT DEFAULT 0,
                        parts TEXT DEFAULT NULL,
                        created_at TIMESTAMP NOT NULL,
                        updated_at TIMESTAMP NOT NULL
                    )
                """)
                self.__conn.commit()
        except mysql.connector.Error as error:
            self.__logger.log_error(str(error))

    """
    Execute query.

    Parameters:
        query (str): The query to be executed.
        params (dict, optional): The parameters to be used in the query. Defaults to None.

    Returns:
        object: The result of the query.
    """

    def execute_query(self, query, params=None):
        try:
            if not self.check_connection():
                self.connect()
            with self.__conn.cursor() as cursor:
                cursor.execute(query, params)
                self.__conn.commit()
                return cursor
        except mysql.connector.Error as error:
            self.__logger.log_error(str(error))
            self.__logger.log_exception()
        return None

    """
    Saves the result to the database.

    Parameters:
        location (str): The location of the image.
        name (str): The name of the image.
        item_count (int): The count value item to be saved.
        source_count (int): The count value source to be saved.
        defects_count (int): The count value defects to be saved.
        correct_count (int): The count value correct to be saved.
        active (int): The status of the image.

    Returns:
        None
    """

    def save_result(self, location, name, item_count=0, source_count=0, defects_count=0, correct_count=0, active=1):
        result = False
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.execute_query(
            f"SELECT * FROM {self.__prefix}cvcounter WHERE active = 1 AND location = %s AND name = %s", (location, name))
        if cursor:
            db_select_result = cursor.fetchone()
            if db_select_result:
                query = (f"UPDATE {self.__prefix}cvcounter "
                         "SET active = %s, location = %s, name = %s, item_count = %s, source_count = %s, defects_count = %s, "
                         "correct_count = %s, created_at = %s, updated_at = %s "
                         "WHERE id = %s")
                values = (active, location, name, item_count, source_count, defects_count, correct_count, now, now, db_select_result[0])
            else:
                query = (f"INSERT INTO {self.__prefix}cvcounter (active, location, name, item_count, source_count, defects_count, "
                         "correct_count, created_at, updated_at) "
                         "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)")
                values = (active, location, name, item_count, source_count, defects_count, correct_count, now, now)
            result = self.execute_query(query, values) is not None
        return result

    """
    Saves part the result to the database.

    Parameters:
        location (str): The location of the image.
        name (str): The name of the image.
        current_count (int): The count value current to be saved. Default is 0.
        total_count (int): The count value total to be saved. Default is 0.
        defects_count (int): The count value defects to be saved. Default is 0.
        correct_count (int): The count value correct to be saved. Default is 0.

    Returns:
        None
    """

    def save_part_result(self, location, name, current_count=0, total_count=0, defects_count=0, correct_count=0):
        result = False
        cursor = self.execute_query(
            f"SELECT * FROM {self.__prefix}cvcounter WHERE active = 1 AND location = %s AND name = %s", (location, name))
        if cursor:
            db_select_result = cursor.fetchone()
            parts = json.loads(db_select_result[8]) if db_select_result and db_select_result[8] else []
            parts.append({
                'current': current_count,
                'total': total_count,
                'defects': defects_count,
                'correct': correct_count,
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            parts = sorted(parts, key=lambda x: x['created_at'], reverse=True)
            new_parts = json.dumps(parts)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if db_select_result:
                query = (f"UPDATE {self.__prefix}cvcounter SET parts = %s, created_at = %s, updated_at = %s WHERE id = %s")
                values = (new_parts, now, now, db_select_result[0])
            else:
                query = (f"INSERT INTO {self.__prefix}cvcounter (active, location, name, parts, created_at, updated_at) "
                         "VALUES (%s, %s, %s, %s, %s, %s)")
                values = (1, location, name, new_parts, now, now)
            result = self.execute_query(query, values) is not None
        return result

    """
    Closes the current count for a specific location and name.

    Parameters:
        location (str): The location of the count.
        name (str): The name of the count.

    Returns:
        None
    """

    def close_current_count(self, location):
        result = False
        cursor = self.execute_query(
            f"SELECT * FROM {self.__prefix}cvcounter WHERE active = 1 AND location = %s", (location,))
        if cursor:
            db_select_result = cursor.fetchone()
            if db_select_result:
                result = self.execute_query(
                    f"UPDATE {self.__prefix}cvcounter SET active = %s WHERE id = %s", (0, db_select_result[0])) is not None
        return result

    """
    Retrieves the current count for a given key from the database.

    Parameters:
        key (str): The key to use for retrieving the count. Default is an empty string.

    Returns:
        int: The current count for the given key.

    Raises:
        mysql.connector.Error: If there is an error executing the database query.
    """

    def get_current_count(self, key=''):
        cursor = self.execute_query(
            f"SELECT * FROM {self.__prefix}cvcounter WHERE active = 1 AND name = %s", (key,))
        return cursor.fetchone()[3] if cursor else None

    """
    Retrieves items from the database.

    Parameters:
        None

    Returns:
        A list of items retrieved from the database.
    """

    @lru_cache(maxsize=128)
    def get_items(self):
        try:
            return None

        except mysql.connector.Error as error:
            self.__logger.log_error(str(error))
            # self.logger.log_exception()
