# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

import ast
import copy
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, Optional, Union

from system.utils.config_validator import validate_config
from system.utils.exception_handler import ConfigError, ConfigNotFoundError, InvalidConfigError
from system.utils.paths import project_root_from_config_path, resolve_project_path, set_project_root, \
    ensure_storage_layout
from system.utils.logger import Logger

""" Global variable to store the configuration data. """
config = None


class ConfigManager:
    _instance: Optional['ConfigManager'] = None
    _init_path: Optional[str] = None
    _config = None

    def __new__(cls, config_path: Union[str, Path]) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            if not os.path.isabs(config_path):
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                config_path = os.path.join(project_root, config_path)
            cls._instance._config_path = str(config_path)
            cls._instance.project_root = project_root_from_config_path(str(config_path))
            set_project_root(cls._instance.project_root)
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
            InvalidConfigError: If the configuration file contains invalid JSON or validation fails.
        """
        try:
            with open(self._config_path, 'r', encoding='utf-8') as config_file:
                config_data = json.load(config_file)
                if not isinstance(config_data, dict):
                    raise InvalidConfigError("Configuration must be a JSON object")

                from system.utils.camera_schema import align_full_config
                aligned_data, changed = align_full_config(config_data)
                if changed:
                    config_data = aligned_data
                    try:
                        with open(self._config_path, 'w', encoding='utf-8') as config_file_w:
                            json.dump(config_data, config_file_w, indent=4, ensure_ascii=False)
                    except Exception:
                        pass
                else:
                    config_data = aligned_data

                # Validate configuration
                validate_config(config_data, self._config_path, raise_on_error=True)

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

    @staticmethod
    def _split_form_key(key: str, current_config: Dict[str, Any]) -> list[str]:
        """
        Split a flattened form key into configuration path segments,
        preserving identifiers containing hyphens (e.g. detection location IDs, usernames).
        """
        detections = current_config.get('detections')
        if isinstance(detections, dict) and key.startswith('detections-'):
            rest = key[len('detections-'):]
            for loc in sorted(detections.keys(), key=len, reverse=True):
                if rest == loc:
                    return ['detections', loc]
                if rest.startswith(f"{loc}-"):
                    sub_key = rest[len(f"{loc}-"):]
                    return ['detections', loc] + sub_key.split('-')

        users = current_config.get('users')
        if isinstance(users, dict) and key.startswith('users-'):
            username = key[len('users-'):]
            return ['users', username]

        return key.split('-')

    def save_from_request(self, form_data: Dict[str, Any]) -> None:
        """
        Saves the config from the request

        Args:
            form_data (dict): The form data.

        Returns:
            None

        Raises:
            InvalidConfigError: If the merged configuration fails validation.
            ConfigError: If the configuration cannot be saved.
        """
        previous_config = copy.deepcopy(self._config)
        try:
            current_config = self.read_config()

            # Pre-process structured class form entries
            # e.g. detections-<loc>-classes-<id>-name and detections-<loc>-classes-<id>-enabled
            structured_classes = {}
            for key in list(form_data.keys()):
                if '-classes-' in key:
                    parts = self._split_form_key(key, current_config)
                    if len(parts) >= 3 and parts[-3] == 'classes' and parts[-1] in ('name', 'enabled'):
                        prefix_path = tuple(parts[:-3])
                        cls_id = str(parts[-2])
                        if prefix_path not in structured_classes:
                            structured_classes[prefix_path] = {}
                        if cls_id not in structured_classes[prefix_path]:
                            structured_classes[prefix_path][cls_id] = {'name': '', 'enabled': False}
                        if parts[-1] == 'name':
                            structured_classes[prefix_path][cls_id]['name'] = str(form_data[key])
                        elif parts[-1] == 'enabled':
                            val = form_data[key]
                            is_on = (val in (True, 'true', 'on', '1', 1) if not isinstance(val, str) else val.lower() in ('true', 'on', '1'))
                            structured_classes[prefix_path][cls_id]['enabled'] = is_on

            for key, value in form_data.items():
                keys = self._split_form_key(key, current_config)
                if keys and keys[0] == 'detections' and keys[-1] in (
                        'counting_area', 'counting_area_color', 'counting_areas'
                ):
                    continue

                if keys and len(keys) >= 3 and keys[-3] == 'classes' and keys[-1] in ('name', 'enabled'):
                    continue

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

                if keys and keys[-1] == 'socketio_transports':
                    if isinstance(value, str):
                        if ',' in value:
                            value = [x.strip().strip("'\"") for x in value.split(',') if x.strip()]
                        elif value.strip():
                            value = [value.strip().strip("'\"")]
                    if isinstance(value, (list, tuple)):
                        value = [str(x) for x in value if str(x).strip()]
                    elif isinstance(value, str) and value:
                        value = [value]
                    elif not value:
                        value = ['polling', 'websocket']

                if keys and keys[-1] == 'options' and 'custom_fields' in keys:
                    if isinstance(value, str):
                        try:
                            parsed_opts = json.loads(value)
                            if isinstance(parsed_opts, list):
                                value = [str(x).strip() for x in parsed_opts if str(x).strip()]
                            else:
                                raise ValueError()
                        except Exception:
                            lines = [x.strip() for x in value.replace('\r\n', '\n').split('\n') if x.strip()]
                            if len(lines) == 1 and ',' in lines[0]:
                                lines = [x.strip() for x in lines[0].split(',') if x.strip()]
                            value = lines
                    elif isinstance(value, (list, tuple)):
                        value = [str(x).strip() for x in value if str(x).strip()]

                current_level[keys[-1]] = value

            # Apply structured classes
            for prefix_path, classes_dict in structured_classes.items():
                target = current_config
                for part in prefix_path:
                    target = target.setdefault(part, {})
                target['classes'] = classes_dict

            # Clean up non-select options and sync renamed field keys in custom_fields
            def _clean_and_sync_custom_fields(cf_dict):
                if not isinstance(cf_dict, dict):
                    return
                for fname, fcfg in list(cf_dict.items()):
                    if isinstance(fcfg, dict):
                        ftype = fcfg.get('type')
                        if ftype != 'select' and 'options' in fcfg:
                            fcfg.pop('options', None)
                        new_name = fcfg.get('name')
                        if new_name and new_name != fname and isinstance(new_name, str) and re.match(r'^[a-zA-Z0-9_]+$', new_name):
                            cf_dict[new_name] = cf_dict.pop(fname)

            if 'form' in current_config and isinstance(current_config['form'], dict):
                _clean_and_sync_custom_fields(current_config['form'].get('custom_fields'))
            if 'detections' in current_config and isinstance(current_config['detections'], dict):
                for cam in current_config['detections'].values():
                    if isinstance(cam, dict):
                        _clean_and_sync_custom_fields(cam.get('custom_fields'))

            from system.utils.camera_schema import align_full_config
            current_config, _ = align_full_config(current_config)

            validate_config(current_config, self._config_path, raise_on_error=True)
            self._config = current_config
            try:
                self.save_config()
            except Exception:
                self._config = previous_config
                raise
        except InvalidConfigError:
            self._config = previous_config
            raise
        except ConfigError:
            self._config = previous_config
            raise
        except Exception as e:
            self._config = previous_config
            logging.error(f"Error saving configuration: {str(e)}")
            raise ConfigError(f"Failed to save configuration: {str(e)}")

    def resolve_path(self, relative_path: Optional[str]) -> Optional[str]:
        """
        Resolve a project-relative path from config.json.
        
        Args:
            relative_path (Optional[str]): The relative path to resolve.

        Returns:
            Optional[str]: The resolved path
        """
        return resolve_project_path(relative_path, self.project_root)

    def reload_config(self, validate: bool = True) -> None:
        """
        Reloads the configuration file from disk.

        Args:
            validate (bool): Whether to validate the configuration after reloading. Defaults to True.

        Returns:
            None
        """
        try:
            # Temporarily disable validation if requested
            if not validate:
                # Read without validation
                with open(self._config_path, 'r', encoding='utf-8') as config_file:
                    config_data = json.load(config_file)
                    if not isinstance(config_data, dict):
                        raise InvalidConfigError("Configuration must be a JSON object")
                    self._config = config_data
            else:
                self._config = self.read_config()
        except ConfigError as e:
            logging.error(f"Error reloading configuration: {str(e)}")
            raise


# ------------------------------------------------------------------
# Initialize config
# ------------------------------------------------------------------

def init_config(config_path: str = "config/config.json") -> ConfigManager:
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
        ensure_storage_layout(config.project_root)
        Logger.configure_from_config(config)
    return config
