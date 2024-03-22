# -*- coding: utf-8 -*-
# ! python3

# Developed by: Alexander Kireev
# Created: 01.11.2023
# Updated: 22.03.2024
# Website: https://bespredel.name

from datetime import datetime
from functools import lru_cache
import mysql.connector
import json
from system.error_logger import ErrorLogger


class DBClient:
    __conn = None
    __logger = None
    __table_name = None

    def __init__(self, host, user, password, database, table_name='cvcounters'):
        # Log error
        self.__logger = ErrorLogger("errors.log")
        self.__table_name = table_name

        # Connection
        try:
            self.__conn = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                database=database,
            )
        except mysql.connector.Error as error:
            self.__conn = None
            # self.logger.log_error(str(error))
            self.__logger.log_exception()

        # Create table if it does not exist
        if self.check_connection():
            self.create_table()

    """
    Check the connection to the database.

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
    Create a table if it does not already exist in the database. 
    """

    def create_table(self):
        try:
            with self.__conn.cursor() as cursor:
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.__table_name} (
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
    Saves the result to the database.

    Parameters:
        production_count (int): The count value production to be saved.
        defects_count (int): The count value defects to be saved.
        key (str): The key to identify the result. Defaults to an empty string.

    Returns:
        None
    """

    def save_result(self, location, name, item_count=0, source_count=0, defects_count=0, correct_count=0, active=1):
        result = False
        try:
            if not self.check_connection():
                self.__conn.connect()

            with self.__conn.cursor() as db_cursor:
                sql_query = f"SELECT * FROM {self.__table_name} WHERE active = 1 AND location = %s AND name = %s"
                db_cursor.execute(sql_query, (location, name,))
                db_select_result = db_cursor.fetchone()

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if db_select_result is not None:
                    sql_query = (
                        f"UPDATE {self.__table_name} "
                        "SET active = %s, location = %s, name = %s, item_count = %s, source_count = %s, defects_count = %s, "
                        "correct_count = %s, created_at = %s, updated_at = %s "
                        "WHERE id = %s")
                    sql_val = (active, location, name, item_count, source_count, defects_count, correct_count,
                               now, now, db_select_result[0])
                    db_cursor.execute(sql_query, sql_val)
                    self.__conn.commit()
                    result = True
                else:
                    sql_query = (
                        f"INSERT INTO {self.__table_name} (active, location, name, item_count, source_count, defects_count, "
                        "correct_count, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)")
                    sql_val = (active, location, name, item_count, source_count, defects_count, correct_count, now, now)
                    db_cursor.execute(sql_query, sql_val)
                    self.__conn.commit()
                    result = True

        except mysql.connector.Error as error:
            self.__logger.log_error(str(error))
            self.__logger.log_exception()

        return result

    """
    Saves part the result to the database.

    Parameters:
        location (str): The location of the part.
        name (str): The name of the part.
        current_count (int): The current count of the part.
        total_count (int): The total count of the part.
        defects_count (int): The count of defective parts.
        correct_count (int): The count of correct parts.
    
    Returns:
        bool: True if the result was successfully saved, False otherwise.
    """

    def save_part_result(self, location, name, current_count=0, total_count=0, defects_count=0, correct_count=0):
        result = False
        try:
            if not self.__conn.is_connected():
                self.__conn.connect()

            with self.__conn.cursor() as db_cursor:
                sql_query = f"SELECT * FROM {self.__table_name} WHERE active = 1 AND location = %s AND name = %s"
                db_cursor.execute(sql_query, (location, name,))
                db_select_result = db_cursor.fetchone()

                parts = list()
                if db_select_result is not None:
                    current_parts_json = db_select_result[8]
                    if current_parts_json is not None:
                        current_parts = json.loads(current_parts_json)
                        parts = current_parts

                parts.append(dict({
                    'current': current_count,
                    'total': total_count,
                    'defects': defects_count,
                    'correct': correct_count,
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }))

                parts = sorted(parts, key=lambda x: x['created_at'], reverse=True)
                new_parts = json.dumps(parts)

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if db_select_result is not None:
                    sql_query = (
                        f"UPDATE {self.__table_name} "
                        "SET parts = %s, created_at = %s, updated_at = %s "
                        "WHERE id = %s")
                    sql_val = (new_parts, now, now, db_select_result[0])
                    db_cursor.execute(sql_query, sql_val)
                    self.__conn.commit()
                    result = True
                else:
                    sql_query = (
                        f"INSERT INTO {self.__table_name} (active, location, name, parts, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, %s, %s)")
                    sql_val = (1, location, name, new_parts, now, now)
                    db_cursor.execute(sql_query, sql_val)
                    self.__conn.commit()
                    result = True

        except mysql.connector.Error as error:
            self.__logger.log_error(str(error))
            self.__logger.log_exception()

        return result

    """
    Closes the current count for a specific location and name.

    Parameters:
        location (str): The location of the count.

    Returns:
        bool: True if the count was successfully closed, False otherwise.
    """

    def close_current_count(self, location):
        result = False
        try:
            if not self.__conn.is_connected():
                self.__conn.connect()

            with self.__conn.cursor() as db_cursor:
                sql_query = f"SELECT * FROM {self.__table_name} WHERE active = 1 AND location = %s"
                db_cursor.execute(sql_query, (location,))
                db_select_result = db_cursor.fetchone()

                if db_select_result:
                    sql_query = f"UPDATE {self.__table_name} SET active = %s WHERE id = %s"
                    sql_val = (0, db_select_result[0])
                    db_cursor.execute(sql_query, sql_val)
                    self.__conn.commit()
                    result = True

        except mysql.connector.Error as error:
            self.__logger.log_error(str(error))
            # self.logger.log_exception()

        return result

    """
    Retrieves the current count for a given key from the database.

    Parameters:
        key (str): The key to use for retrieving the count. Default is an empty string.

    Returns:
        int: The current count for the given key.
    """

    def get_current_count(self, key=''):
        result = None
        try:
            with self.__conn.cursor() as db_cursor:
                sql_query = f"SELECT * FROM {self.__table_name} WHERE active = 1 AND name = %s"
                db_cursor.execute(sql_query, (key,))
                db_select_result = db_cursor.fetchone()

            result = db_select_result[3]

        except mysql.connector.Error as error:
            self.__logger.log_error(str(error))
            # self.logger.log_exception()

        return result

    """
    Retrieves items from the database.

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

    """
    Destructor method for the class. Closes the connection and cursor.
    """

    def __del__(self):
        pass
        # self.conn.close()
        # self.cur.close()
