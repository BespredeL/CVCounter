# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 03.12.2025
# Updated: 03.06.2026
# Website: https://bespredel.name

import json

from flask import Blueprint, abort, render_template
from flask import current_app, g
from markupsafe import escape

from system.utils.i18n import trans as translate
from system.utils.validators import ValidationError, validate_report_list_request

reports_bp = Blueprint('reports', __name__)


def get_app_context():
    """Get application context from g or current_app.
    
    Returns:
        dict: Application context
    """
    if not hasattr(g, 'app_context'):
        g.app_context = current_app.config.get('APP_CONTEXT')
    return g.app_context


@reports_bp.route('/reports')
def reports() -> str:
    """
    Display the main reports page.
    
    Returns:
        str: Rendered HTML template with reports overview
    """
    context = get_app_context()
    locations_dict = context['locations_dict']

    return render_template(
        'reports/index.html',
        object_counters=locations_dict
    )


@reports_bp.route('/reports/<string:location>')
def report_list(location: str = None) -> str:
    """
    Display paginated list of reports for a specific location.
    
    Args:
        location (str): The identifier for the detection location
    
    Returns:
        str: Rendered HTML template with paginated reports list
    """
    context = get_app_context()
    locations = context['locations']
    locations_dict = context['locations_dict']
    db_manager = context['db_manager']

    try:
        # Validate location
        if location is None:
            abort(404, translate('Page not found'))

        location = str(escape(location))
        if location not in locations:
            abort(404, translate('Page not found'))

        # Validate page number
        validated_data = validate_report_list_request()
        r_page = validated_data['page']
        per_page = 10

        pagination = db_manager.get_paginated(location, r_page, per_page)

        if pagination is None:
            abort(404, translate('Page not found'))

        items = pagination['results']
        current_page = pagination['page']
        total_items = pagination['total']
        total_pages = (total_items + per_page - 1) // per_page

        return render_template(
            'reports/list.html',
            object_counters=locations_dict,
            items=items,
            location=location,
            current_page=current_page,
            total_pages=total_pages,
            json=json
        )
    except ValidationError as e:
        abort(400, str(e))
    except Exception as e:
        from system.utils.logger import Logger
        Logger().error(f"Error in report_list: {e}")
        abort(500, "Internal server error")


@reports_bp.route('/reports/<string:location>/<int:report_id>')
def report_show(location: str, report_id: int) -> str:
    """
    Display detailed view of a specific report.
    
    Args:
        location (str): The identifier for the detection location
        report_id (int): The report ID
    
    Returns:
        str: Rendered HTML template with report details
    """
    context = get_app_context()
    db_manager = context['db_manager']

    counter = db_manager.get_count(report_id)

    if counter is None:
        abort(404, translate('Page not found'))

    return render_template(
        'reports/show.html',
        location=location,
        counter=counter,
        json=json
    )
