# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 22.01.2026
# Updated: 03.06.2026
# Website: https://bespredel.name

import json
from typing import Any, Optional
from flask import abort, request
from werkzeug.exceptions import BadRequest

from system.utils.logger import Logger


class ValidationError(Exception):
    """Custom exception for validation errors."""

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.field = field


class RequestValidator:
    """Utility class for validating request data."""

    def __init__(self):
        self.logger = Logger()

    @staticmethod
    def validate_integer(value: Any, field_name: str, min_value: Optional[int] = None,
                         max_value: Optional[int] = None, required: bool = True) -> int:
        """
        Validate and convert a value to integer.
        
        Args:
            value: Value to validate
            field_name: Name of the field for error messages
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            required: Whether the field is required
        
        Returns:
            int: Validated integer value
        
        Raises:
            ValidationError: If validation fails
        """
        if value is None or value == '':
            if required:
                raise ValidationError(f"Field '{field_name}' is required", field_name)
            return 0

        try:
            int_value = int(value)
        except (ValueError, TypeError):
            raise ValidationError(f"Field '{field_name}' must be an integer", field_name)

        if min_value is not None and int_value < min_value:
            raise ValidationError(
                f"Field '{field_name}' must be at least {min_value}", field_name
            )

        if max_value is not None and int_value > max_value:
            raise ValidationError(
                f"Field '{field_name}' must be at most {max_value}", field_name
            )

        return int_value

    @staticmethod
    def validate_string(value: Any, field_name: str, max_length: Optional[int] = None,
                        required: bool = True, allow_empty: bool = True) -> str:
        """
        Validate and convert a value to string.
        
        Args:
            value: Value to validate
            field_name: Name of the field for error messages
            max_length: Maximum allowed length
            required: Whether the field is required
            allow_empty: Whether empty strings are allowed
        
        Returns:
            str: Validated string value
        
        Raises:
            ValidationError: If validation fails
        """
        if value is None:
            if required:
                raise ValidationError(f"Field '{field_name}' is required", field_name)
            return ""

        str_value = str(value).strip()

        if not allow_empty and str_value == "":
            if required:
                raise ValidationError(f"Field '{field_name}' cannot be empty", field_name)
            return ""

        if max_length is not None and len(str_value) > max_length:
            raise ValidationError(
                f"Field '{field_name}' must be at most {max_length} characters", field_name
            )

        return str_value

    @staticmethod
    def validate_json_string(value: Any, field_name: str, required: bool = False) -> dict:
        """
        Validate and parse a JSON string.
        
        Args:
            value: JSON string to validate
            field_name: Name of the field for error messages
            required: Whether the field is required
        
        Returns:
            dict: Parsed JSON object
        
        Raises:
            ValidationError: If validation fails
        """
        if value is None or value == '':
            if required:
                raise ValidationError(f"Field '{field_name}' is required", field_name)
            return {}

        if not isinstance(value, str):
            raise ValidationError(f"Field '{field_name}' must be a string", field_name)

        try:
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValidationError(f"Field '{field_name}' must be a JSON object", field_name)
            return parsed
        except json.JSONDecodeError as e:
            raise ValidationError(f"Field '{field_name}' contains invalid JSON: {str(e)}", field_name)

    @staticmethod
    def validate_location(location: str, available_locations: list[str]) -> str:
        """
        Validate that location exists in available locations.
        
        Args:
            location: Location identifier to validate
            available_locations: List of available location identifiers
        
        Returns:
            str: Validated location identifier
        
        Raises:
            ValidationError: If validation fails
        """
        if not location:
            raise ValidationError("Location is required", "location")

        if location not in available_locations:
            raise ValidationError(
                f"Location '{location}' is not available", "location"
            )

        return location

    @staticmethod
    def validate_page_number(page: Any, field_name: str = "page") -> int:
        """
        Validate page number for pagination.
        
        Args:
            page: Page number to validate
            field_name: Name of the field for error messages
        
        Returns:
            int: Validated page number (minimum 1)
        
        Raises:
            ValidationError: If validation fails
        """
        if page is None:
            return 1

        try:
            page_int = int(page)
        except (ValueError, TypeError):
            raise ValidationError(f"Field '{field_name}' must be an integer", field_name)

        if page_int < 1:
            return 1

        return page_int


def validate_save_count_request(location: str, available_locations: list[str]) -> dict[str, Any]:
    """
    Validate request data for save_count endpoint.
    
    Args:
        location: Location identifier
        available_locations: List of available locations
    
    Returns:
        dict: Validated data with keys: location, correct_count, defect_count, custom_fields
    
    Raises:
        ValidationError: If validation fails
    """
    validator = RequestValidator()

    # Validate location
    validated_location = validator.validate_location(location, available_locations)

    # Validate form data
    if not request.form:
        raise ValidationError("Request must contain form data")

    # Validate counts (must be non-negative integers)
    correct_count = validator.validate_integer(
        request.form.get('correct_count'),
        'correct_count',
        min_value=0,
        required=True
    )

    defect_count = validator.validate_integer(
        request.form.get('defect_count'),
        'defect_count',
        min_value=0,
        required=True
    )

    # Validate custom_fields (optional JSON string)
    custom_fields_str = request.form.get('custom_fields', '')
    custom_fields = validator.validate_json_string(custom_fields_str, 'custom_fields', required=False)

    return {
        'location': validated_location,
        'correct_count': correct_count,
        'defect_count': defect_count,
        'custom_fields': json.dumps(custom_fields) if custom_fields else ""
    }


def validate_reset_count_current_request(location: str, available_locations: list[str]) -> dict[str, Any]:
    """
    Validate request data for reset_count_current endpoint.
    
    Args:
        location: Location identifier
        available_locations: List of available locations
    
    Returns:
        dict: Validated data with keys: location, correct_count, defect_count
    
    Raises:
        ValidationError: If validation fails
    """
    validator = RequestValidator()

    # Validate location
    validated_location = validator.validate_location(location, available_locations)

    # Validate form data
    if not request.form:
        raise ValidationError("Request must contain form data")

    # Validate counts (must be non-negative integers)
    correct_count = validator.validate_integer(
        request.form.get('correct_count'),
        'correct_count',
        min_value=0,
        required=True
    )

    defect_count = validator.validate_integer(
        request.form.get('defect_count'),
        'defect_count',
        min_value=0,
        required=True
    )

    return {
        'location': validated_location,
        'correct_count': correct_count,
        'defect_count': defect_count
    }


def validate_counting_area_payload(data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate JSON payload for counting area save.

    Args:
        data: Parsed JSON body.

    Returns:
        dict: Validated counting_area and optional counting_area_color (BGR).

    Raises:
        ValidationError: If validation fails.
    """
    if not isinstance(data, dict):
        raise ValidationError('Request body must be a JSON object')

    area = data.get('counting_area')
    if not isinstance(area, list) or len(area) < 3:
        raise ValidationError('counting_area must be a list of at least 3 points')

    validated_area: list[list[int]] = []
    for i, point in enumerate(area):
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValidationError(f'counting_area[{i}] must be [x, y]')

        try:
            x, y = int(point[0]), int(point[1])
        except (TypeError, ValueError):
            raise ValidationError(f'counting_area[{i}] coordinates must be integers')

        if x < 0 or y < 0:
            raise ValidationError(f'counting_area[{i}] coordinates must be non-negative')

        validated_area.append([x, y])

    result: dict[str, Any] = {'counting_area': validated_area}

    if 'counting_area_color' in data and data['counting_area_color'] is not None:
        color = data['counting_area_color']
        if not isinstance(color, (list, tuple)) or len(color) != 3:
            raise ValidationError('counting_area_color must be a list of 3 integers (BGR)')

        try:
            bgr = [int(color[0]), int(color[1]), int(color[2])]
        except (TypeError, ValueError):
            raise ValidationError('counting_area_color values must be integers')

        if not all(0 <= c <= 255 for c in bgr):
            raise ValidationError('counting_area_color values must be between 0 and 255')

        result['counting_area_color'] = bgr

    return result


def validate_report_list_request() -> dict[str, Any]:
    """
    Validate request data for report_list endpoint.
    
    Returns:
        dict: Validated data with key: page
    
    Raises:
        ValidationError: If validation fails
    """
    validator = RequestValidator()

    page = validator.validate_page_number(request.args.get('page', 1))

    return {
        'page': page
    }
