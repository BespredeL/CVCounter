# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 22.01.2026
# Updated: 25.07.2026
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
        min_value=-9999999,
        max_value=9999999,
        required=True
    )

    defect_count = validator.validate_integer(
        request.form.get('defect_count'),
        'defect_count',
        min_value=0,
        max_value=9999999,
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
        min_value=-9999999,
        max_value=9999999,
        required=True
    )

    defect_count = validator.validate_integer(
        request.form.get('defect_count'),
        'defect_count',
        min_value=0,
        max_value=9999999,
        required=True
    )

    return {
        'location': validated_location,
        'correct_count': correct_count,
        'defect_count': defect_count
    }


def validate_pending_counts_request(location: str, available_locations: list[str]) -> dict[str, Any]:
    """
    Validate request data for update_pending_counts endpoint.

    Args:
        location: Location identifier
        available_locations: List of available locations

    Returns:
        dict: Validated data with keys: location, correct_count, defect_count

    Raises:
        ValidationError: If validation fails
    """
    validator = RequestValidator()

    validated_location = validator.validate_location(location, available_locations)

    if not request.form:
        raise ValidationError("Request must contain form data")

    correct_count = validator.validate_integer(
        request.form.get('correct_count'),
        'correct_count',
        min_value=-9999999,
        max_value=9999999,
        required=True
    )

    defect_count = validator.validate_integer(
        request.form.get('defect_count'),
        'defect_count',
        min_value=0,
        max_value=9999999,
        required=True
    )

    return {
        'location': validated_location,
        'correct_count': correct_count,
        'defect_count': defect_count,
    }


def _validate_polygon_points(area: Any, label: str) -> list[list[int]]:
    """
    Validate a single polygon point list.

    Args:
        area: The area to validate.
        label: The label to use for error messages.

    Returns:
        The validated area.
    """
    if not isinstance(area, list) or len(area) < 3:
        raise ValidationError(f'{label} must be a list of at least 3 points')

    validated_area: list[list[int]] = []
    for i, point in enumerate(area):
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValidationError(f'{label}[{i}] must be [x, y]')

        try:
            x, y = int(point[0]), int(point[1])
        except (TypeError, ValueError):
            raise ValidationError(f'{label}[{i}] coordinates must be integers')

        if x < 0 or y < 0:
            raise ValidationError(f'{label}[{i}] coordinates must be non-negative')

        validated_area.append([x, y])
    return validated_area


def _validate_bgr_color(color: Any, label: str = 'counting_area_color') -> list[int]:
    """
    Validate a BGR color list.

    Args:
        color: The color to validate.
        label: The label to use for error messages.

    Returns:
        The validated color.

    Raises:
        ValidationError: If validation fails.
    """
    if not isinstance(color, (list, tuple)) or len(color) != 3:
        raise ValidationError(f'{label} must be a list of 3 integers (BGR)')

    try:
        bgr = [int(color[0]), int(color[1]), int(color[2])]
    except (TypeError, ValueError):
        raise ValidationError(f'{label} values must be integers')

    if not all(0 <= c <= 255 for c in bgr):
        raise ValidationError(f'{label} values must be between 0 and 255')
    return bgr


def validate_counting_area_payload(data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate JSON payload for counting area save.

    Accepts multi-zone ``counting_areas`` and/or legacy single ``counting_area``.

    Args:
        data: Parsed JSON body.

    Returns:
        dict: Validated counting_areas plus legacy counting_area / counting_area_color.

    Raises:
        ValidationError: If validation fails.
    """
    if not isinstance(data, dict):
        raise ValidationError('Request body must be a JSON object')

    areas_raw = data.get('counting_areas')
    validated_areas: list[dict[str, Any]] = []

    if isinstance(areas_raw, list) and areas_raw:
        for index, item in enumerate(areas_raw):
            label = f'counting_areas[{index}]'
            if isinstance(item, dict):
                points = _validate_polygon_points(item.get('points'), f'{label}.points')
                color = item.get('color', data.get('counting_area_color'))
                if color is None:
                    color = [67, 211, 255]
                validated_areas.append({
                    'points': points,
                    'color': _validate_bgr_color(color, f'{label}.color'),
                })
            else:
                points = _validate_polygon_points(item, label)
                color = data.get('counting_area_color', [67, 211, 255])
                validated_areas.append({
                    'points': points,
                    'color': _validate_bgr_color(color, 'counting_area_color'),
                })
    else:
        area = data.get('counting_area')
        points = _validate_polygon_points(area, 'counting_area')
        color = data.get('counting_area_color', [67, 211, 255])
        validated_areas.append({
            'points': points,
            'color': _validate_bgr_color(color, 'counting_area_color'),
        })

    first = validated_areas[0]
    return {
        'counting_areas': validated_areas,
        'counting_area': first['points'],
        'counting_area_color': first['color'],
    }


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
