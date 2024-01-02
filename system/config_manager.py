# -*- coding: utf-8 -*-
# ! python3

# Developed by: Alexander Kireev
# Created: 01.11.2023
# Updated: 19.12.2023
# Website: https://bespredel.name

import json


class ConfigManager:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self.read_config()

    """
    Reads the config file and returns it as a dictionary
    
    Parameters:
        None
        
    Returns:
        dict: The config file
    """

    def read_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as config_file:
                return json.load(config_file)
        except FileNotFoundError:
            raise ValueError(f"File '{self.config_path}' does not exist")

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
        val = self.config
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
        val = self.config
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
        with open(self.config_path, 'w', encoding='utf-8') as config_file:
            json.dump(self.config, config_file)
