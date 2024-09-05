# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 05.09.2024
# Website: https://bespredel.name

from datetime import datetime
from functools import lru_cache
import mysql.connector
import json
from system.Logger import Logger


class DatabaseManager:
    __conn = None
    __logger = None
    __prefix = None

    def __init__(self, host, user, password, database, prefix=''):
        # Log error
        self.__logger = Logger("errors.log")
        self.__prefix = prefix

        # Connection
        self.connect(host, user, password, database)

        # Create table if it does not exist
        if self.check_connection():
            self.create_table()

    """
    Destructor method for the class. Closes the connection and cursor.
    """

    def __del__(self):
        pass
        #if self.__conn is not None:
        #    self.__conn.close()

    """
    Connect to the database.

    Parameters:
        self (object): The instance of the class.

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
            # self.__logger.log_error(str(e))
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
        try:
            if not self.check_connection():
                self.__conn.connect()

            with self.__conn.cursor() as db_cursor:
                sql_query = f"SELECT * FROM {self.__prefix}cvcounter WHERE active = 1 AND location = %s AND name = %s"
                db_cursor.execute(sql_query, (location, name,))
                db_select_result = db_cursor.fetchone()

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if db_select_result is not None:
                    sql_query = (
                        f"UPDATE {self.__prefix}cvcounter "
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
                        f"INSERT INTO {self.__prefix}cvcounter (active, location, name, item_count, source_count, defects_count, "
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
        try:
            if not self.__conn.is_connected():
                self.__conn.connect()

            with self.__conn.cursor() as db_cursor:
                sql_query = f"SELECT * FROM {self.__prefix}cvcounter WHERE active = 1 AND location = %s AND name = %s"
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
                        f"UPDATE {self.__prefix}cvcounter "
                        "SET parts = %s, created_at = %s, updated_at = %s "
                        "WHERE id = %s")
                    sql_val = (new_parts, now, now, db_select_result[0])
                    db_cursor.execute(sql_query, sql_val)
                    self.__conn.commit()
                    result = True
                else:
                    sql_query = (
                        f"INSERT INTO {self.__prefix}cvcounter (active, location, name, parts, created_at, updated_at) "
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
        name (str): The name of the count.

    Returns:
        None
    """

    def close_current_count(self, location):
        location = str(location)
        result = False
        try:
            if not self.__conn.is_connected():
                self.__conn.connect()

            with self.__conn.cursor() as db_cursor:
                sql_query = f"SELECT * FROM {self.__prefix}cvcounter WHERE active = 1 AND location = %s"
                db_cursor.execute(sql_query, (location,))
                db_select_result = db_cursor.fetchone()

                if db_select_result:
                    sql_query = f"UPDATE {self.__prefix}cvcounter SET active = %s WHERE id = %s"
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

    Raises:
        mysql.connector.Error: If there is an error executing the database query.
    """

    def get_current_count(self, key=''):
        key = str(key)
        result = None
        try:
            with self.__conn.cursor() as db_cursor:
                sql_query = f"SELECT * FROM {self.__prefix}cvcounter WHERE active = 1 AND name = %s"
                db_cursor.execute(sql_query, (key,))
                db_select_result = db_cursor.fetchone()

            result = db_select_result[3]

        except mysql.connector.Error as error:
            self.__logger.log_error(str(error))
            # self.logger.log_exception()

        return result

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
