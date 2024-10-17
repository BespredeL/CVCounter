# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 21.07.2024
# Website: https://bespredel.name

import ast
import json


class ConfigManager:
    _instance = None
    _init_path = None

    def __new__(cls, config_path):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._config_path = config_path
            cls._instance._config = cls._instance.read_config()
            cls._init_path = config_path
        elif config_path != cls._init_path:
            raise ValueError("Cannot instantiate ConfigManager with a different config path")
        return cls._instance

    def __init__(self, config_path):
        self._config_path = config_path
        self._config = self.read_config()

    """
    Reads the config file and returns it as a dictionary
    
    Parameters:
        None
        
    Returns:
        dict: The config file
    """

    def read_config(self):
        try:
            with open(self._config_path, 'r', encoding='utf-8') as config_file:
                return json.load(config_file)
        except FileNotFoundError:
            raise ValueError(f"Configuration file '{self._config_path}' does not exist")

    """
    Returns a value from the config

    Parameters:
        keys (str): The path to the value
        default (any): The default value if the value is not found
        
    Returns:
        any: The value
    """

    def get(self, keys, default=None):
        keys = keys.split('.')
        val = self._config
        try:
            for key in keys:
                val = val[key]
            return val
        except KeyError:
            return default

    """
    Sets a value in the config
    
    Parameters:
        keys (str): The path to the value
        value (any): The value
        
    Returns:
        None
    """

    def set(self, keys, value):
        keys = keys.split('.')
        val = self._config
        for key in keys[:-1]:
            val = val.setdefault(key, {})
        val[keys[-1]] = value

    """
    Saves the config
    
    Parameters:
        None
        
    Returns:
        None
    """

    def save_config(self):
        with open(self._config_path, 'w', encoding='utf-8') as config_file:
            json.dump(self._config, config_file)

    """
    Saves the config from the request

    Parameters:
        form_data (dict): The form data

    Returns:
        None
    """

    def save_from_request(self, form_data):
        config_data = {}

        for key in form_data:
            keys = key.split('-')
            current_level = config_data

            for part in keys[:-1]:
                if part not in current_level:
                    current_level[part] = {}
                current_level = current_level[part]

            value = form_data[key]
            try:
                value = ast.literal_eval(value)
                if not isinstance(value, (list, tuple)):
                    raise ValueError

                def verify_list_integrity(lst):
                    for item in lst:
                        if isinstance(item, list):
                            verify_list_integrity(item)
                        elif not isinstance(item, int):
                            raise ValueError

                verify_list_integrity(value)
            except (ValueError, SyntaxError):
                if not isinstance(value, str):
                    value = str(value)

                if value.isdigit():
                    value = int(value)
                elif value.replace('.', '', 1).isdigit():
                    value = float(value)
                elif value.lower() in ['on', 'off']:
                    value = value.lower() == 'on'

            current_level[keys[-1]] = value

        self._config = config_data
        self.save_config()
