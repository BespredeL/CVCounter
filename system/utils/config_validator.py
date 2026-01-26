# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 22.01.2026
# Updated: 22.01.2026
# Website: https://bespredel.name

import os
from typing import Any, Dict, List, Optional

from system.utils.exception_handler import InvalidConfigError


class ConfigValidator:
    """Validator for application configuration."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self, config: Dict[str, Any], config_path: Optional[str] = None) -> tuple[bool, List[str], List[str]]:
        """
        Validate the entire configuration.

        Args:
            config (dict): Configuration dictionary to validate
            config_path (str, optional): Path to config file for relative path validation

        Returns:
            tuple: (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        # Validate top-level sections
        self._validate_general(config.get('general', {}))
        self._validate_server(config.get('server', {}))
        self._validate_users(config.get('users', {}))
        self._validate_db(config.get('db', {}), config_path)
        self._validate_form(config.get('form', {}))
        self._validate_detection_default(config.get('detection_default', {}), config_path)
        self._validate_detections(config.get('detections', {}), config_path)

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings

    def _validate_general(self, general: Dict[str, Any]) -> None:
        """
        Validate general configuration section.

        Args:
            general (dict): General configuration section

        Returns:
            None
        """

        if not general:
            self.errors.append("Section 'general' is required")
            return

        # Validate debug
        if 'debug' not in general:
            self.warnings.append("'general.debug' not set, defaulting to False")
        elif not isinstance(general['debug'], bool):
            self.errors.append("'general.debug' must be a boolean")

        # Validate log_path
        if 'log_path' in general:
            log_path = general['log_path']
            if not isinstance(log_path, str):
                self.errors.append("'general.log_path' must be a string")
            elif log_path:
                # Check if directory exists or can be created
                log_dir = os.path.dirname(log_path) or '.'
                if not os.path.exists(log_dir) and not os.access(os.path.dirname(log_dir) or '.', os.W_OK):
                    self.warnings.append(f"Log directory '{log_dir}' does not exist and may not be writable")

        # Validate log_level
        if 'log_level' in general:
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if general['log_level'] not in valid_levels:
                self.errors.append(f"'general.log_level' must be one of: {', '.join(valid_levels)}")

        # Validate default_language
        if 'default_language' in general:
            if not isinstance(general['default_language'], str):
                self.errors.append("'general.default_language' must be a string")
            elif general['default_language'] not in ['ru', 'en']:
                self.warnings.append(f"Unknown language '{general['default_language']}', expected 'ru' or 'en'")

    def _validate_server(self, server: Dict[str, Any]) -> None:
        """
        Validate server configuration section.

        Args:
            server (dict): Server configuration section

        Returns:
            None
        """

        if not server:
            self.errors.append("Section 'server' is required")
            return

        # Validate host
        if 'host' not in server:
            self.warnings.append("'server.host' not set, defaulting to '0.0.0.0'")
        elif not isinstance(server['host'], str):
            self.errors.append("'server.host' must be a string")

        # Validate port
        if 'port' in server:
            port = server['port']
            if not isinstance(port, int):
                self.errors.append("'server.port' must be an integer")
            elif not (1 <= port <= 65535):
                self.errors.append("'server.port' must be between 1 and 65535")

        # Validate allowed_origins
        if 'allowed_origins' in server:
            origins = server['allowed_origins']
            if isinstance(origins, str):
                # Single origin as string
                if not origins.startswith(('*', 'http://', 'https://')):
                    self.warnings.append(f"'server.allowed_origins' should start with '*', 'http://' or 'https://': {origins}")
            elif isinstance(origins, list):
                # Multiple origins as list
                for origin in origins:
                    if not isinstance(origin, str):
                        self.errors.append("'server.allowed_origins' list items must be strings")
                    elif not origin.startswith(('*', 'http://', 'https://')):
                        self.warnings.append(f"Origin should start with '*', 'http://' or 'https://': {origin}")
            else:
                self.errors.append("'server.allowed_origins' must be a string or a list of strings")

    def _validate_users(self, users: Dict[str, Any]) -> None:
        """
        Validate users configuration section.

        Args:
            users (dict): Users configuration section

        Returns:
            None
        """

        if not users:
            self.warnings.append("No users defined in configuration. Authentication will not work.")

        for username, password_hash in users.items():
            if not isinstance(username, str) or not username:
                self.errors.append(f"Invalid username in users section: {username}")
            if not isinstance(password_hash, str) or not password_hash:
                self.errors.append(f"Invalid password hash for user '{username}'")
            elif not password_hash.startswith(('pbkdf2:', 'scrypt:', 'argon2:')):
                self.warnings.append(f"Password hash for user '{username}' may not be in a recognized format")

    def _validate_db(self, db: Dict[str, Any], config_path: Optional[str] = None) -> None:
        """
        Validate database configuration section.

        Args:
            db (dict): Database configuration section
            config_path (str, optional): Path to config file for relative path validation

        Returns:
            None
        """

        if not db:
            self.errors.append("Section 'db' is required")
            return

        # Validate uri
        if 'uri' not in db:
            self.warnings.append("'db.uri' not set, will use in-memory database")
        elif not isinstance(db['uri'], str):
            self.errors.append("'db.uri' must be a string")
        elif db['uri'].startswith('sqlite:///'):
            # Extract path for SQLite
            db_path = db['uri'].replace('sqlite:///', '')
            if db_path and db_path != ':memory:':
                # Resolve relative paths
                if config_path and not os.path.isabs(db_path):
                    db_path = os.path.join(os.path.dirname(config_path), db_path)
                db_dir = os.path.dirname(db_path) or '.'
                if db_dir and not os.path.exists(db_dir):
                    try:
                        os.makedirs(db_dir, exist_ok=True)
                    except OSError:
                        self.warnings.append(f"Database directory '{db_dir}' cannot be created")

        # Validate prefix
        if 'prefix' in db and not isinstance(db['prefix'], str):
            self.errors.append("'db.prefix' must be a string")

    def _validate_form(self, form: Dict[str, Any]) -> None:
        """
        Validate form configuration section.

        Args:
            form (dict): Form configuration section

        Returns:
            None
        """

        if 'custom_fields' in form:
            custom_fields = form['custom_fields']
            if not isinstance(custom_fields, dict):
                self.errors.append("'form.custom_fields' must be a dictionary")
            else:
                for field_name, field_config in custom_fields.items():
                    if not isinstance(field_config, dict):
                        self.errors.append(f"'form.custom_fields.{field_name}' must be a dictionary")
                        continue

                    # Validate required fields
                    if 'name' not in field_config:
                        self.errors.append(f"'form.custom_fields.{field_name}' missing 'name' field")
                    if 'label' not in field_config:
                        self.errors.append(f"'form.custom_fields.{field_name}' missing 'label' field")
                    if 'type' not in field_config:
                        self.errors.append(f"'form.custom_fields.{field_name}' missing 'type' field")

                    # Validate type
                    if 'type' in field_config:
                        valid_types = ['text', 'textarea', 'date', 'datetime-local', 'select', 'number']
                        if field_config['type'] not in valid_types:
                            self.warnings.append(f"Unknown field type '{field_config['type']}' in '{field_name}'")

                    # Validate options for select type
                    if field_config.get('type') == 'select':
                        if 'options' not in field_config:
                            self.errors.append(f"'form.custom_fields.{field_name}' of type 'select' missing 'options'")
                        elif not isinstance(field_config['options'], list):
                            self.errors.append(f"'form.custom_fields.{field_name}.options' must be a list")

    def _validate_detection_default(self, detection_default: Dict[str, Any], config_path: Optional[str] = None) -> None:
        """
        Validate detection_default configuration section.

        Args:
            detection_default (dict): Detection default configuration section
            config_path (str, optional): Path to config file for relative path validation

        Returns:
            None
        """

        if not detection_default:
            self.warnings.append("Section 'detection_default' not found, some detections may fail")
            return

        self._validate_detection_config(detection_default, 'detection_default', config_path)

    def _validate_detections(self, detections: Dict[str, Any], config_path: Optional[str] = None) -> None:
        """
        Validate detections configuration section.

        Args:
            detections (dict): Detections configuration section
            config_path (str, optional): Path to config file for relative path validation

        Returns:
            None
        """

        if not detections:
            self.warnings.append("No detections configured")

        for location, detection_config in detections.items():
            if not isinstance(location, str) or not location:
                self.errors.append(f"Invalid detection location name: {location}")
                continue

            if not isinstance(detection_config, dict):
                self.errors.append(f"Detection '{location}' must be a dictionary")
                continue

            # Validate label
            if 'label' not in detection_config:
                self.warnings.append(f"Detection '{location}' missing 'label', using location name")

            # Validate detection-specific config
            self._validate_detection_config(detection_config, f"detections.{location}", config_path)

    def _validate_detection_config(self, config: Dict[str, Any], prefix: str, config_path: Optional[str] = None) -> None:
        """
        Validate a single detection configuration.

        Args:
            config (dict): Detection configuration section
            prefix (str): Prefix for error messages
            config_path (str, optional): Path to config file for relative path validation

        Returns:
            None
        """

        # Validate model_type
        if 'model_type' in config:
            if config['model_type'] not in ['yolo']:
                self.warnings.append(f"'{prefix}.model_type' is '{config['model_type']}', only 'yolo' is currently supported")

        # Validate weights_path
        if 'weights_path' in config:
            weights_path = config['weights_path']
            if not isinstance(weights_path, str):
                self.errors.append(f"'{prefix}.weights_path' must be a string")
            elif weights_path:
                # Resolve relative paths
                if config_path and not os.path.isabs(weights_path):
                    weights_path = os.path.join(os.path.dirname(config_path), weights_path)
                if not os.path.exists(weights_path):
                    self.warnings.append(f"Model weights file not found: '{weights_path}'")

        # Validate confidence
        if 'confidence' in config:
            confidence = config['confidence']
            if not isinstance(confidence, (int, float)):
                self.errors.append(f"'{prefix}.confidence' must be a number")
            elif not (0.0 <= confidence <= 1.0):
                self.errors.append(f"'{prefix}.confidence' must be between 0.0 and 1.0")

        # Validate iou
        if 'iou' in config:
            iou = config['iou']
            if not isinstance(iou, (int, float)):
                self.errors.append(f"'{prefix}.iou' must be a number")
            elif not (0.0 <= iou <= 1.0):
                self.errors.append(f"'{prefix}.iou' must be between 0.0 and 1.0")

        # Validate device
        if 'device' in config:
            device = config['device']
            if not isinstance(device, int):
                self.errors.append(f"'{prefix}.device' must be an integer")
            elif device < 0:
                self.warnings.append(f"'{prefix}.device' is {device}, negative values may cause issues")

        # Validate counting_area
        if 'counting_area' in config:
            counting_area = config['counting_area']
            if not isinstance(counting_area, list):
                self.errors.append(f"'{prefix}.counting_area' must be a list")
            elif len(counting_area) < 3:
                self.errors.append(f"'{prefix}.counting_area' must have at least 3 points")
            else:
                for i, point in enumerate(counting_area):
                    if not isinstance(point, list) or len(point) != 2:
                        self.errors.append(f"'{prefix}.counting_area[{i}]' must be a list of 2 numbers")
                    elif not all(isinstance(coord, (int, float)) for coord in point):
                        self.errors.append(f"'{prefix}.counting_area[{i}]' coordinates must be numbers")

        # Validate counting_area_color
        if 'counting_area_color' in config:
            color = config['counting_area_color']
            if not isinstance(color, list) or len(color) != 3:
                self.errors.append(f"'{prefix}.counting_area_color' must be a list of 3 integers (RGB)")
            elif not all(isinstance(c, int) and 0 <= c <= 255 for c in color):
                self.errors.append(f"'{prefix}.counting_area_color' values must be integers between 0 and 255")

        # Validate recording
        if 'recording' in config:
            recording = config['recording']
            if not isinstance(recording, dict):
                self.errors.append(f"'{prefix}.recording' must be a dictionary")
            else:
                if 'enable' in recording and not isinstance(recording['enable'], bool):
                    self.errors.append(f"'{prefix}.recording.enable' must be a boolean")
                if 'path' in recording:
                    path = recording['path']
                    if not isinstance(path, str):
                        self.errors.append(f"'{prefix}.recording.path' must be a string")
                    elif path:
                        # Resolve relative paths
                        if config_path and not os.path.isabs(path):
                            path = os.path.join(os.path.dirname(config_path), path)
                        if not os.path.exists(path):
                            try:
                                os.makedirs(path, exist_ok=True)
                            except OSError:
                                self.warnings.append(f"Recording directory '{path}' cannot be created")


def validate_config(config: Dict[str, Any], config_path: Optional[str] = None, raise_on_error: bool = True) -> tuple[
    bool, List[str], List[str]]:
    """
    Validate configuration and optionally raise exception on errors.

    Args:
        config (dict): Configuration dictionary to validate
        config_path (str, optional): Path to config file for relative path validation
        raise_on_error (bool): If True, raise InvalidConfigError on validation errors

    Returns:
        tuple: (is_valid, errors, warnings)

    Raises:
        InvalidConfigError: If validation fails and raise_on_error is True
    """

    validator = ConfigValidator()
    is_valid, errors, warnings = validator.validate(config, config_path)

    # Try to log warnings, but don't fail if logger is not available
    if warnings:
        try:
            # Import Logger locally to avoid circular dependency
            from system.utils.logger import Logger
            logger = Logger()
            for warning in warnings:
                logger.warning(f"Config validation warning: {warning}")
        except Exception:
            # Logger might not be available yet, just print to console
            import sys
            for warning in warnings:
                print(f"Config validation warning: {warning}", file=sys.stderr)

    if not is_valid and raise_on_error:
        error_message = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
        raise InvalidConfigError(error_message, errors={'validation_errors': errors})

    return is_valid, errors, warnings
