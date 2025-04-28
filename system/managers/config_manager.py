# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 28.04.2025
# Website: https://bespredel.name

import ast
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from system.utils.exception_handler import ConfigError, ConfigNotFoundError, InvalidConfigError

config = None


class ConfigManager:
    _instance: Optional['ConfigManager'] = None
    _init_path: Optional[str] = None
    _config = None

    def __new__(cls, config_path: Union[str, Path]) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
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
            ConfigNotFoundError: If the configuration file doesn't exist.
            InvalidConfigError: If the configuration file contains invalid JSON.
        """
        try:
            with open(self._config_path, 'r', encoding='utf-8') as config_file:
                config_data = json.load(config_file)
                if not isinstance(config_data, dict):
                    raise InvalidConfigError("Configuration must be a JSON object")
                return config_data
        except FileNotFoundError:
            raise ConfigNotFoundError(f"Configuration file '{self._config_path}' does not exist")
        except json.JSONDecodeError as e:
            raise InvalidConfigError(f"Invalid JSON in configuration file: {str(e)}")

    def get(self, keys: str, default: Optional[Any] = None) -> Any:
        """
        Returns a value from the config

        Args:
            keys (str): The path to the value.
            default (Optional[Any]): The default value if the value is not found.

        Returns:
            Any: The value.
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
            value (Any): The value.

        Returns:
            None
        """
        keys_list = keys.split('.')
        val = self._config
        for key in keys_list[:-1]:
            val = val.setdefault(key, {})
        val[keys_list[-1]] = value

    def delete(self, keys: str) -> None:
        """
        Deletes a value from the config.

        Args:
            keys (str): The path to the value.

        Returns:
            None
        """
        keys_list = keys.split('.')
        val = self._config
        try:
            for key in keys_list[:-1]:
                val = val[key]
            del val[keys_list[-1]]
        except (KeyError, TypeError):
            raise KeyError(f"Key '{keys}' not found in configuration")

    def save_config(self) -> None:
        """
        Save the current configuration to file.

        Returns:
            None
        """
        try:
            with open(self._config_path, 'w', encoding='utf-8') as config_file:
                json.dump(self._config, config_file, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error saving configuration: {str(e)}")
            raise ConfigError(f"Failed to save configuration: {str(e)}")

    def save_from_request(self, form_data: Dict[str, Any]) -> None:
        """
        Saves the config from the request

        Args:
            form_data (dict): The form data.

        Returns:
            None
        """
        try:
            current_config = self.read_config()

            for key, value in form_data.items():
                keys = key.split('-')
                current_level = current_config

                for part in keys[:-1]:
                    current_level = current_level.setdefault(part, {})

                if isinstance(value, str):
                    try:
                        parsed_value = ast.literal_eval(value)
                        if isinstance(parsed_value, (list, dict, int, float, bool)):
                            value = parsed_value
                    except (ValueError, SyntaxError):
                        pass
                    if isinstance(value, str) and value.lower() in ['true', 'false', 'on', 'off']:
                        value = value.lower() in ['true', 'on']
                current_level[keys[-1]] = value

            self._config = current_config
            self.save_config()
        except Exception as e:
            logging.error(f"Error saving configuration: {str(e)}")
            raise ConfigError(f"Failed to save configuration: {str(e)}")

    def reload_config(self) -> None:
        """
        Reloads the configuration file from disk.

        Returns:
            None
        """
        try:
            self._config = self.read_config()
        except ConfigError as e:
            logging.error(f"Error reloading configuration: {str(e)}")
            raise


def init_config(config_path: str = "config.json") -> ConfigManager:
    """
    Initializes the global configuration instance.

    Args:
        config_path (str): Path to the configuration file

    Returns:
        ConfigManager: Configuration instance
    """
    global config
    if config is None:
        config = ConfigManager(config_path)
        config.read_config()
    return config
