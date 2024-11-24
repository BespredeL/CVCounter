# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 24.11.2024
# Website: https://bespredel.name

from typing import Any, Dict, Union, Optional
import ast
import json
import logging
import os
from pathlib import Path


class ConfigManager:
    _instance: Optional['ConfigManager'] = None
    _init_path: Optional[str] = None
    _config = None

    def __new__(cls, config_path: Union[str, Path]) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            # Convert relative path to absolute path relative to project root
            if not os.path.isabs(config_path):
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                config_path = os.path.join(project_root, config_path)
            cls._instance._config_path = str(config_path)
            cls._instance._config = cls._instance.read_config()
            cls._init_path = str(config_path)
        elif str(config_path) != cls._init_path:
            raise ValueError("Cannot instantiate ConfigManager with a different config path")
        return cls._instance

    def read_config(self) -> Dict[str, Any]:
        """
        Read and parse the configuration file.

        Returns:
            Dict containing the configuration data.

        Raises:
            ValueError: If the configuration file doesn't exist or is invalid JSON
        """
        try:
            with open(self._config_path, 'r', encoding='utf-8') as config_file:
                config_data = json.load(config_file)
                if not isinstance(config_data, dict):
                    raise ValueError("Configuration must be a JSON object")
                return config_data
        except FileNotFoundError:
            raise ValueError(f"Configuration file '{self._config_path}' does not exist")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {str(e)}")

    def get(self, keys: str, default: Any = None) -> Any:
        """
        Returns a value from the config

        Args:
            keys (str): The path to the value.
            default (any): The default value if the value is not found.

        Returns:
            any: The value
        """

        keys_list = keys.split('.')
        val = self._config
        try:
            for key in keys_list:
                val = val[key]
            return val
        except (KeyError, TypeError):
            return default

    def set(self, keys: str, value: Any) -> None:
        """
        Sets a value in the config

        Args:
            keys (str): The path to the value.
            value (any): The value.

        Returns:
            None
        """

        keys_list = keys.split('.')
        val = self._config
        for key in keys_list[:-1]:
            val = val.setdefault(key, {})
        val[keys_list[-1]] = value

    def save_config(self) -> None:
        """
        Save the current configuration to file.

        Returns:
            None
        """

        with open(self._config_path, 'w', encoding='utf-8') as config_file:
            json.dump(self._config, config_file, indent=4, ensure_ascii=False)

    def save_from_request(self, form_data: Dict[str, Any]) -> None:
        """
        Saves the config from the request

        Args:
            form_data (dict): The form data

        Returns:
            None
        """

        try:
            # Read current config
            current_config = self.read_config()

            for key, value in form_data.items():
                keys = key.split('-')
                current_level = current_config

                # Build nested structure
                for part in keys[:-1]:
                    if part not in current_level:
                        current_level[part] = {}
                    current_level = current_level[part]

                # Process value
                try:
                    # Try to evaluate as literal (for lists/tuples)
                    parsed_value = ast.literal_eval(str(value))
                    if isinstance(parsed_value, (list, tuple)):
                        def verify_list_integrity(lst):
                            return all(
                                verify_list_integrity(item) if isinstance(item, list)
                                else isinstance(item, int)
                                for item in lst
                            )

                        if verify_list_integrity(parsed_value):
                            value = parsed_value
                        else:
                            raise ValueError("Invalid list content")
                    else:
                        raise ValueError
                except (ValueError, SyntaxError):
                    # Process as string/number/boolean
                    if not isinstance(value, str):
                        value = str(value)

                    if value.isdigit():
                        value = int(value)
                    elif value.replace('.', '', 1).isdigit():
                        value = float(value)
                    elif value.lower() in ['true', 'false', 'on', 'off']:
                        value = value.lower() in ['true', 'on']

                current_level[keys[-1]] = value

            self._config = current_config
            self.save_config()
        except Exception as e:
            logging.error(f"Error saving configuration: {str(e)}")
            raise ValueError(f"Failed to save configuration: {str(e)}")
